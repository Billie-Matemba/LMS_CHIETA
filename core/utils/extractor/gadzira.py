"""
Gadzira heuristic extractor.

This module loads a YAML configuration of CHIETA-specific question patterns
and produces block suggestions without touching an LLM. Patterns can define
keywords, regexes, capture rules, and default metadata/marks. If no pattern
matches, we fall back to the legacy suggest_boxes_for_paper pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Iterable, Tuple, Optional
import json
import logging
import os
import re

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

from core.models import ExtractorPaper as Paper, ExtractorBlock as Block
from .question_detect import detect_in_any_line

LOGGER = logging.getLogger(__name__)
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "gadzira_patterns.yaml"


@dataclass
class Pattern:
    key: str
    raw: Dict[str, object]

    @property
    def match(self) -> Dict[str, object]:
        return self.raw.get("match") or {}

    @property
    def capture(self) -> Dict[str, object]:
        return self.raw.get("capture") or {}

    @property
    def metadata(self) -> Dict[str, object]:
        return self.raw.get("metadata") or {}


def _ensure_config_file():
    if CONFIG_PATH.exists():
        return
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text("version: 1\npatterns: []\n", encoding="utf-8")
    except Exception as exc:  # pragma: no cover - io errors
        LOGGER.warning("Unable to initialise gadzira config: %s", exc)


@lru_cache(maxsize=1)
def _load_config() -> Dict[str, object]:
    _ensure_config_file()
    if not CONFIG_PATH.exists():
        return {"version": 1, "patterns": []}
    try:
        if not yaml:
            LOGGER.warning("PyYAML not installed; gadzira config ignored.")
            return {"version": 1, "patterns": []}
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError("Config root must be a mapping")
        return data
    except Exception as exc:
        LOGGER.warning("Failed to load gadzira config: %s", exc)
        return {"version": 1, "patterns": []}


def _match_block(block: Block, pattern: Pattern) -> bool:
    text = (block.text or "").lower()
    match = pattern.match
    if not match:
        return False

    keywords_any: Iterable[str] = match.get("keywords_any") or []
    if keywords_any:
        if not any(k.lower() in text for k in keywords_any):
            return False

    keywords_all: Iterable[str] = match.get("keywords_all") or []
    for kw in keywords_all:
        if kw.lower() not in text:
            return False

    header_regex = match.get("header_regex")
    if header_regex:
        try:
            if not re.search(header_regex, block.text or "", re.IGNORECASE | re.MULTILINE):
                return False
        except re.error:  # pragma: no cover
            LOGGER.warning("Invalid regex for pattern %s", pattern.key)
            return False

    block_types = match.get("block_types")
    if block_types and block.block_type not in set(block_types):
        return False

    requires_table = match.get("requires_table")
    if requires_table and block.block_type != "table":
        return False

    return True


def _resolve_question_number(meta: Dict[str, object], block: Block, default: str = "") -> str:
    raw = meta.get("question_number")
    if isinstance(raw, str):
        value = raw.strip()
    else:
        value = raw or ""
    if not value or value.lower() == "auto":
        detected = block.detected_qnum or detect_in_any_line(block.text or "")
        if isinstance(detected, tuple):
            return detected[0] or default
        return detected or default
    return value


def _resolve_marks(meta: Dict[str, object], block: Block) -> str:
    marks = meta.get("marks")
    if marks in (None, "", "auto"):
        detected = detect_in_any_line(block.text or "")
        if detected and detected[1]:
            return detected[1]
        return ""
    return str(marks)


def _stop_due_to_header(block: Block) -> bool:
    det = detect_in_any_line(block.text or "")
    return bool(det and det[0])


def _build_suggestion(blocks: List[Block], start_idx: int, pattern: Pattern, used_ids: set[int]) -> Optional[Dict[str, object]]:
    block = blocks[start_idx]
    meta = pattern.metadata or {}
    capture = pattern.capture or {}

    until_next_header = bool(capture.get("until_next_header", True))
    max_blocks = capture.get("max_blocks")
    stop_keywords = [kw.lower() for kw in (capture.get("stop_keywords") or [])]

    selected: List[Block] = []
    j = start_idx
    while j < len(blocks):
        candidate = blocks[j]
        if candidate.id in used_ids:
            break
        if j > start_idx:
            if until_next_header and _stop_due_to_header(candidate):
                break
            text_lower = (candidate.text or "").lower()
            if stop_keywords and any(kw in text_lower for kw in stop_keywords):
                break
        selected.append(candidate)
        if max_blocks and len(selected) >= int(max_blocks):
            break
        j += 1

    if not selected:
        return None

    qnum = _resolve_question_number(meta, block, default="")
    marks = _resolve_marks(meta, block)
    qtype = (meta.get("qtype") or "question").strip()
    parent_number = (meta.get("parent_number") or "").strip()
    header_label = (meta.get("header_label") or "").strip()

    block_ids = [b.id for b in selected]
    has_table = any(b.block_type == "table" for b in selected)
    has_image = any((b.block_type == "image") or b.images.exists() for b in selected)

    payload = {
        "block_ids": block_ids,
        "question_number": qnum,
        "marks": marks,
        "qtype": qtype,
        "has_table": has_table,
        "has_image": has_image,
    }
    if parent_number:
        payload["parent_number"] = parent_number
    if header_label:
        payload["header_label"] = header_label
    if meta.get("case_study_label"):
        payload["case_study_label"] = meta["case_study_label"]

    for b in selected:
        used_ids.add(b.id)

    return payload


def gadzira_suggest_boxes(paper: Paper) -> Tuple[List[Dict[str, object]], str]:
    """Return (items, strategy) for gadzira heuristics."""
    config = _load_config()
    patterns = [Pattern(pat.get("key") or f"pattern_{idx}", pat) for idx, pat in enumerate(config.get("patterns") or []) if isinstance(pat, dict)]
    blocks = list(paper.blocks.order_by("order_index").prefetch_related("images"))
    used_ids: set[int] = set()
    suggestions: List[Dict[str, object]] = []

    for idx, block in enumerate(blocks):
        if block.id in used_ids:
            continue
        for pattern in patterns:
            if _match_block(block, pattern):
                suggestion = _build_suggestion(blocks, idx, pattern, used_ids)
                if suggestion:
                    suggestions.append(suggestion)
                    collapse = pattern.metadata.get("collapse")
                    if collapse:
                        break  # allow other instructions to merge via collapse logic
                break

    strategy = "gadzira"
    if not suggestions:
        # Fallback to existing heuristic/LLM pipeline so button is still useful.
        from .auto_draw_blocks import suggest_boxes_for_paper  # pylint: disable=import-outside-toplevel

        fallback_items, fallback_strategy = suggest_boxes_for_paper(paper)
        return fallback_items, f"gadzira_fallback:{fallback_strategy}"

    return suggestions, strategy
