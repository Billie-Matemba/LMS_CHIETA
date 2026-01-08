"""
Auto Draw Blocks: Suggests grouped question regions for a paper.

Design goals
- Use robust heuristics to group blocks into question chunks starting at headers.
- Classify each chunk with a coarse qtype and note presence of images/tables.
- Prepare results for client-side drawing: provide involved block IDs and metadata.
- Optionally leverage per-paper `system_prompt` to guide an LLM in future.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
import os, json, re
import logging
import requests

try:
    from google import generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    genai = None

from core.models import ExtractorPaper as Paper, ExtractorBlock as Block
from .question_detect import detect_in_any_line

logger = logging.getLogger(__name__)
_PREFACE_TYPES = {"cover_page", "instruction", "rubric"}


def _merge_preface_instructions(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge consecutive instruction-style suggestions before the first numbered question."""
    if not items:
        return items
    idx = 0
    preface: List[Dict[str, Any]] = []
    cover_prefix: List[Dict[str, Any]] = []

    if items and (items[0].get("qtype") or "").lower() == "cover_page":
        cover_prefix.append(items[0])
        idx = 1

    while idx < len(items):
        entry = items[idx]
        qnum = (entry.get("question_number") or "").strip()
        if qnum:
            break
        qtype = (entry.get("qtype") or "").lower()
        if qtype and qtype not in (_PREFACE_TYPES | {"heading", "paragraph"}):
            break
        preface.append(entry)
        idx += 1

    if len(preface) <= 1:
        return cover_prefix + preface + items[idx:]

    block_ids: List[int] = []
    has_table = False
    has_image = False
    for entry in preface:
        block_ids.extend(entry.get("block_ids") or [])
        has_table = has_table or bool(entry.get("has_table"))
        has_image = has_image or bool(entry.get("has_image"))

    merged = {
        "block_ids": block_ids,
        "question_number": "0",
        "marks": "0",
        "qtype": "instruction",
        "has_table": has_table,
        "has_image": has_image,
        "parent_number": "",
        "header_label": "Instructions",
        "case_study_label": "",
    }
    remainder = items[idx:]
    return cover_prefix + [merged] + remainder


def _postprocess_suggestions(items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not items:
        return []
    work = _merge_preface_instructions(list(items))

    for i, entry in enumerate(work):
        qtype = (entry.get("qtype") or "").lower()
        qnum = (entry.get("question_number") or "").strip()

        normalize_as_instruction = False
        if i == 0 and not qnum:
            normalize_as_instruction = True
        if qnum.isdigit() and 1 <= int(qnum) <= 12 and qtype not in _PREFACE_TYPES:
            normalize_as_instruction = True

        if normalize_as_instruction:
            entry["qtype"] = "instruction"
            qtype = "instruction"
            qnum = "0"

        if qtype in _PREFACE_TYPES:
            entry["question_number"] = qnum or "0"
            entry["marks"] = (entry.get("marks") or "0").strip() or "0"
            entry["parent_number"] = entry.get("parent_number") or ""
            entry["header_label"] = entry.get("header_label") or (
                "Instructions" if qtype == "instruction" else "Cover Page"
            )
        else:
            entry["question_number"] = qnum
            entry["marks"] = (entry.get("marks") or "").strip()

    return work


def _guess_qtype(texts: List[str]) -> str:
    t = "\n".join(texts).lower()
    # Simple instruction cues
    if any(k in t for k in ["instruction", "read all instructions", "read the following instructions", "answer all questions"]):
        return "instruction"
    # Default to question
    return "question"


def build_default_system_prompt() -> str:
    return (
        "You are an exam paper analyzer. Your job is to segment the paper into question blocks. "
        "Each question block starts at a detectable question header. question headers start from 1.1, some are nested in tables should be found regardless.(e.g., '' main question header (1.1)', sub questionsn (1.1.1, 1.1.2, 1.1.3, 1.1.4, 1.1.5, 1.16), 2.1.1, 2.1. '2.3'). "
        "Include all supporting content that belongs to the question such as paragraphs, images, and tables "
        "until the next peer question header. Capture whether the block contains images and/or tables. "
        "Output should preserve the question number and optionally the marks if stated."
        "constructive response, and other types of questions should be classified as questions."
        "ensure 1. are not classified as questions only 1.1 the 1. letter are instructuions"
    )


def _ollama_suggest(paper: Paper, blocks: List[Block]) -> Optional[List[Dict[str, Any]]]:
    """Call local Ollama (if available) to propose question regions.

    Returns None on failure. Expects Ollama at OLLAMA_HOST (default http://localhost:11434)
    and OLLAMA_MODEL env (default 'llama3:latest').
    """
    try:
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        model = os.environ.get("OLLAMA_MODEL", "llama3:latest")
        url = f"{host.rstrip('/')}/api/chat"
        # Prepare a concise document snapshot to keep prompt small
        items = []
        for b in blocks:
            txt = (b.text or "").strip()
            if len(txt) > 800:
                txt = txt[:800] + "…"
            items.append({
                "id": b.id,
                "type": b.block_type,
                "has_image": (b.block_type == "image") or b.images.exists(),
                "has_table": (b.block_type == "table"),
                "text": txt,
            })

        sys_prompt = (paper.system_prompt or build_default_system_prompt()).strip()
        user_req = (
            "Given the following ordered blocks from an exam paper, group them into question regions. "
            "A region starts at a question header and includes supporting blocks (paragraphs, images, tables) until the next header. "
            "Return strict JSON only in this schema: {\n  \"items\": [ {\n    \"block_ids\": [int...],\n    \"question_number\": string,\n    \"marks\": string,\n    \"qtype\": one of ['constructed','mcq','case_study','table_q','image_q']\n  } ... ]\n}. "
            "Use block IDs exactly as provided. Prefer contiguous ranges."
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_req + "\nBlocks JSON:\n" + json.dumps(items, ensure_ascii=False)},
        ]
        payload = {"model": model, "messages": messages, "stream": False}
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content") or data.get("response") or ""
        if not content:
            return None
        # Extract JSON payload
        start = content.find('{')
        if start == -1:
            start = content.find('[')
        if start == -1:
            return None
        json_text = content[start:]
        # Trim potential trailing code fences
        json_text = json_text.strip().rstrip('`')
        parsed = json.loads(json_text)
        items_out = parsed.get("items") if isinstance(parsed, dict) else parsed
        if not isinstance(items_out, list):
            return None
        # Normalize entries and ensure block_ids are in given list
        valid_ids = {b.id for b in blocks}
        out: List[Dict[str, Any]] = []
        for it in items_out:
            b_ids = [i for i in (it.get("block_ids") or []) if i in valid_ids]
            if not b_ids:
                continue
            out.append({
                "block_ids": b_ids,
                "question_number": (it.get("question_number") or "").strip(),
                "marks": (it.get("marks") or "").strip(),
                "qtype": (it.get("qtype") or "constructed").strip(),
                "has_table": any(next((bb for bb in blocks if bb.id == i and (bb.block_type == 'table')), None) for i in b_ids),
                "has_image": any(next((bb for bb in blocks if bb.id == i and ((bb.block_type == 'image') or bb.images.exists())), None) for i in b_ids),
            })
        return out or None
    except Exception as ex:
        logger.warning("Ollama suggest failed: %s", ex)
        return None


def _strip_code_fences(payload: str) -> str:
    cleaned = payload.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip("` \n")
    if cleaned.endswith("```"):
        cleaned = cleaned[: -3]
    return cleaned.strip()


def _gemini_suggest(paper: Paper, blocks: List[Block]) -> Optional[List[Dict[str, Any]]]:
    """Call Gemini (if configured) to propose question regions."""
    if not blocks or not genai:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model_name = (
        os.getenv("GEMINI_DRAW_MODEL")
        or os.getenv("GEMINI_MODEL")
        or "models/gemini-2.0-flash"
    )

    try:
        genai.configure(api_key=api_key)
    except Exception as ex:  # pragma: no cover - defensive
        logger.warning("Gemini configure failed: %s", ex)
        return None

    serialised_blocks = []
    lookup: Dict[int, Block] = {}
    for idx, block in enumerate(blocks, start=1):
        lookup[block.id] = block
        text = (block.text or "").strip()
        if len(text) > 600:
            text = text[:600] + "…"
        serialised_blocks.append(
            {
                "id": block.id,
                "order": idx,
                "type": block.block_type,
                "text": text,
                "has_table": block.block_type == "table",
                "has_image": (block.block_type == "image") or block.images.exists(),
                "detected_qnum": (block.detected_qnum or "").strip(),
                "detected_marks": (block.detected_marks or "").strip(),
            }
        )

    system_prompt = (paper.system_prompt or build_default_system_prompt()).strip()
    instructions = (
        "Group the provided ordered blocks into contiguous question regions. "
        "Each region starts where a numbered question header appears (e.g. 1.1, 1.1.1). "
        "Include the supporting content (paragraphs, tables, figures) that belongs to the question "
        "until the next peer header. Return ONLY strict JSON:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "block_ids": [list of ints],\n'
        '      "question_number": "1.1",\n'
        '      "marks": "10",\n'
        '      "qtype": "constructed|case_study|instruction|table_q|image_q",\n'
        '      "has_table": true/false,\n'
        '      "has_image": true/false\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Use block IDs exactly as provided and prefer contiguous ranges."
    )

    try:
        payload = f"{system_prompt}\n\n{instructions}\n\nBlocks JSON:\n{json.dumps(serialised_blocks, ensure_ascii=False)}"
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(payload)
        raw = getattr(response, "text", "") or ""
        cleaned = _strip_code_fences(raw)
        parsed = json.loads(cleaned)
    except Exception as ex:
        logger.warning("Gemini suggest failed: %s", ex)
        return None

    items = parsed.get("items") if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        return None

    valid_ids = set(lookup.keys())
    results: List[Dict[str, Any]] = []
    for entry in items:
        raw_ids = entry.get("block_ids") or entry.get("blocks") or entry.get("ids") or []
        block_ids: List[int] = []
        for raw_id in raw_ids:
            try:
                block_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if block_id in valid_ids:
                block_ids.append(block_id)
        if not block_ids:
            continue

        has_table = entry.get("has_table")
        if has_table is None:
            has_table = any(lookup[i].block_type == "table" for i in block_ids)
        has_image = entry.get("has_image")
        if has_image is None:
            has_image = any(
                (lookup[i].block_type == "image") or lookup[i].images.exists()
                for i in block_ids
            )
        qtype = (entry.get("qtype") or "").strip() or (
            "table_q" if has_table else ("image_q" if has_image else "constructed")
        )

        results.append(
            {
                "block_ids": block_ids,
                "question_number": (entry.get("question_number") or "").strip(),
                "marks": (entry.get("marks") or "").strip(),
                "qtype": qtype,
                "has_table": bool(has_table),
                "has_image": bool(has_image),
                "parent_number": (entry.get("parent_number") or "").strip(),
                "header_label": (entry.get("header_label") or "").strip(),
                "case_study_label": (entry.get("case_study_label") or "").strip(),
            }
        )

    return results or None


def suggest_boxes_for_paper(paper: Paper) -> Tuple[List[Dict[str, Any]], str]:
    """
    Returns a tuple: (suggestions, strategy).
    Suggestions look like:
    [
      {
        'block_ids': [int, ...],       # contiguous region from header to next header-1
        'question_number': '1.1',
        'marks': '10',
        'qtype': 'constructed'|'mcq'|'case_study'|'table_q'|'image_q',
        'has_table': bool,
        'has_image': bool,
      }, ...
    ]

    Strategy indicates which backend produced the suggestions: 'gemini', 'ollama', or 'heuristic'.
    """
    # Ensure there is a system prompt to store on the paper for future use
    if not (paper.system_prompt or "").strip():
        paper.system_prompt = build_default_system_prompt()
        paper.save(update_fields=["system_prompt"])

    blocks = list(paper.blocks.order_by("order_index").prefetch_related("images"))

    # Try Gemini first for best quality, then Ollama, then heuristics.
    gemini_suggestions = _gemini_suggest(paper, blocks)
    if gemini_suggestions:
        return _postprocess_suggestions(gemini_suggestions), "gemini"
    ollama_suggestions = _ollama_suggest(paper, blocks)
    if ollama_suggestions:
        return _postprocess_suggestions(ollama_suggestions), "ollama"
    suggestions: List[Dict[str, Any]] = []

    cur_ids: List[int] = []
    cur_texts: List[str] = []
    cur_has_tbl = False
    cur_has_img = False
    cur_qnum = None
    cur_marks = None

    saw_any_header = False

    def flush():
        if not cur_ids:
            return
        # If we haven't seen any header yet and no question number, treat as cover page
        if not saw_any_header and not cur_qnum:
            qtype = "cover_page"
        else:
            qtype = _guess_qtype(cur_texts)
        suggestions.append(
            {
                "block_ids": list(cur_ids),
                "question_number": cur_qnum or "",
                "marks": cur_marks or "",
                "qtype": qtype,
                "has_table": bool(cur_has_tbl),
                "has_image": bool(cur_has_img),
            }
        )

    for b in blocks:
        text = (b.text or "").strip()
        det = detect_in_any_line(text)
        if det:
            # New header -> flush previous
            if cur_ids:
                flush()
                cur_ids.clear(); cur_texts.clear(); cur_has_tbl = False; cur_has_img = False
            num, marks = det
            cur_qnum = num
            cur_marks = marks or ""
            saw_any_header = True
        # Accumulate current
        cur_ids.append(b.id)
        if text:
            cur_texts.append(text)
        if b.block_type == "table":
            cur_has_tbl = True
        if b.block_type == "image" or b.images.exists():
            cur_has_img = True

    # tail
    flush()

    # Filter out degenerate suggestions (no qnum and very small set)
    cleaned: List[Dict[str, Any]] = []
    for s in suggestions:
        if not s.get("question_number") and len(s.get("block_ids", [])) <= 1:
            continue
        cleaned.append(s)

    return _postprocess_suggestions(cleaned), "heuristic"
