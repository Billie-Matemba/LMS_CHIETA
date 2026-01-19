"""
mbalaka.py — Markdown conversion + LLM-aided classification helper is not used, but this is a provisional module....Don't stress about this.

Goals
- Convert a Paper to compact, readable Markdown to give the LLM better context.
- Optionally call local Ollama to classify blocks using the Markdown context.
"""
from __future__ import annotations

import os
import re
import json
from typing import List, Dict, Any, Optional

from django.conf import settings

from core.models import ExtractorPaper, ExtractorBlock
from .question_detect import detect_in_any_line

_Q11_RE = re.compile(r"^\d+\.\d+", re.IGNORECASE)
_INSTR_LEAD_RE = re.compile(r"^\d+\.\s+", re.IGNORECASE)


def _md_escape(text: str) -> str:
    if not text:
        return ""
    # Minimal escape; leave most punctuation for readability
    return text.replace("\r", "").strip()


def _images_md(block: ExtractorBlock) -> str:
    parts = []
    for img in block.images.all():
        try:
            url = img.image.url
        except Exception:
            continue
        parts.append(f"![image]({url})")
    return "\n".join(parts)


def _table_md(html: str) -> str:
    # Cheap fallback: keep HTML inside fenced block when tables are complex
    html = (html or "").strip()
    if not html:
        return ""
    return f"\n```html\n{html}\n```\n"


def paper_to_markdown(paper: ExtractorPaper) -> str:
    blocks = list(paper.blocks.prefetch_related("images").order_by("order_index"))
    md: List[str] = []
    title = paper.title or os.path.basename(paper.original_file.name)
    md.append(f"# {title}")
    meta = []
    if paper.module_name:
        meta.append(f"Module: {paper.module_name}")
    if paper.paper_number or paper.paper_letter:
        meta.append(f"Paper: {(paper.paper_number or '').strip()} {(paper.paper_letter or '').strip()}")
    if meta:
        md.append("\n".join(meta))

    # Instructions until first 1.1-like header. Within that region, pick lines like '1. text'
    md.append("\n## Instructions")
    in_instruction = True
    for b in blocks:
        text = (b.text or "").strip()
        if in_instruction and _Q11_RE.match(text):
            in_instruction = False
            md.append("\n## Questions")
        if in_instruction:
            if _INSTR_LEAD_RE.match(text):
                md.append(f"- {_md_escape(text)}")
            elif b.block_type == "table":
                md.append(_table_md(text))
            else:
                # keep compact prose
                if text:
                    md.append(_md_escape(text))
                imgs = _images_md(b)
                if imgs:
                    md.append(imgs)
        else:
            # Question region: add headers when detected
            det = detect_in_any_line(text)
            if det:
                qn, marks = det
                hdr = f"### Question {qn}"
                if marks:
                    hdr += f" ({marks} marks)"
                md.append(hdr)
            if b.block_type == "table":
                md.append(_table_md(text))
            elif text:
                md.append(_md_escape(text))
            imgs = _images_md(b)
            if imgs:
                md.append(imgs)

    return "\n\n".join([seg for seg in md if seg is not None]) + "\n"


def _ollama_classify_with_md(paper: ExtractorPaper, markdown: str) -> Optional[List[Dict[str, Any]]]:
    """Ask Ollama to classify blocks given Markdown context.

    Returns a list of per-block updates: {id, block_type, is_qheader, detected_qnum, detected_marks}
    """
    import requests

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "llama3:latest")
    url = f"{host}/api/chat"

    # Provide a minimal block index for reference
    blk_index = [
        {
            "id": b.id,
            "order": b.order_index,
            "type": b.block_type,
            "text": (b.text or "")[:200],
        }
        for b in paper.blocks.order_by("order_index")
    ]

    sys = (paper.system_prompt or "").strip() or (
        "You are an exam paper analyzer. Classify each block id as one of: "
        "question_header, question, instruction, case_study, rubric, cover_page, table, image, heading, paragraph. "
        "Also detect question numbers and marks when present. Respond with strict JSON."
    )
    user = (
        "Given the markdown version of the paper and the block index, return a JSON array where each entry is "
        "{id, block_type, is_qheader, detected_qnum, detected_marks}. "
        "Use the provided ids from the block index."
    )

    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": user + "\n\n# BlockIndex\n" + json.dumps(blk_index) + "\n\n# Markdown\n" + markdown},
    ]
    try:
        resp = requests.post(url, json={"model": model, "messages": messages, "stream": False}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content") or data.get("response") or ""
        if not content:
            return None
        # Extract first JSON array/object
        start = content.find("[")
        if start == -1:
            start = content.find("{")
        if start == -1:
            return None
        body = content[start:].strip().rstrip("`")
        parsed = json.loads(body)
        items = parsed if isinstance(parsed, list) else parsed.get("items")
        if not isinstance(items, list):
            return None
        norm = []
        for it in items:
            try:
                norm.append({
                    "id": int(it.get("id")),
                    "block_type": (it.get("block_type") or "").strip(),
                    "is_qheader": bool(it.get("is_qheader")),
                    "detected_qnum": (it.get("detected_qnum") or "").strip(),
                    "detected_marks": (it.get("detected_marks") or "").strip(),
                })
            except Exception:
                continue
        return norm
    except Exception:
        return None


def classify_blocks_with_markdown(paper: ExtractorPaper) -> Dict[str, Any]:
    """Generate Markdown and try LLM-based classification; fall back to no-op.

    Returns summary { updated: int, had_llm: bool, md_len: int }
    """
    md = paper_to_markdown(paper)
    updates = _ollama_classify_with_md(paper, md)
    updated = 0
    if updates:
        # Apply updates to DB
        by_id = {b.id: b for b in paper.blocks.all()}
        for u in updates:
            b = by_id.get(u.get("id"))
            if not b:
                continue
            fields = []
            bt = (u.get("block_type") or "").strip()
            if bt and bt != b.block_type:
                b.block_type = bt; fields.append("block_type")
            if "is_qheader" in u and bool(u["is_qheader"]) != b.is_qheader:
                b.is_qheader = bool(u["is_qheader"]); fields.append("is_qheader")
            dq = (u.get("detected_qnum") or "").strip()
            if dq != (b.detected_qnum or ""):
                b.detected_qnum = dq; fields.append("detected_qnum")
            dm = (u.get("detected_marks") or "").strip()
            if dm != (b.detected_marks or ""):
                b.detected_marks = dm; fields.append("detected_marks")
            if fields:
                b.save(update_fields=fields)
                updated += 1
    return {"updated": updated, "had_llm": bool(updates), "md_len": len(md)}