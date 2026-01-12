from __future__ import annotations

from html import escape
from copy import deepcopy
from typing import Iterable


HEX_CHARS = set("0123456789abcdefABCDEF")


def _normalize_hex(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("#"):
        body = text[1:]
        if body and all(ch in HEX_CHARS for ch in body):
            return f"#{body}"
        return text
    if all(ch in HEX_CHARS for ch in text) and len(text) in {3, 6, 8}:
        return f"#{text[:6]}"
    return text


def runs_to_html(runs: list[dict] | None, fallback_text: str = "") -> str:
    """Render Word run payloads to HTML spans preserving styling."""
    if not runs:
        return escape(fallback_text or "")

    parts: list[str] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        text = str(run.get("text") or "")
        if text == "":
            continue
        styles: list[str] = []
        color = _normalize_hex(run.get("color"))
        if color:
            styles.append(f"color: {color}")
        highlight = _normalize_hex(run.get("highlight"))
        if highlight:
            styles.append(f"background-color: {highlight}")
        shading = _normalize_hex(run.get("shading"))
        if shading and not highlight:
            styles.append(f"background-color: {shading}")
        if run.get("is_bold"):
            styles.append("font-weight: 600")
        if run.get("is_italic"):
            styles.append("font-style: italic")
        if run.get("is_underline"):
            styles.append("text-decoration: underline")
        style_attr = f" style=\"{' ; '.join(styles)}\"" if styles else ""
        safe_text = escape(text).replace("\t", "&emsp;")
        parts.append(f"<span class=\"docx-run\"{style_attr}>{safe_text}</span>")
    output = "".join(parts)
    return output or escape(fallback_text or "")


def summarize_runs_text(runs: list[dict] | None) -> str:
    if not runs:
        return ""
    return "".join(str(run.get("text") or "") for run in runs).strip()


def keep_bold_runs(runs: list[dict] | None) -> list[dict]:
    if not runs:
        return []
    return [run for run in runs if isinstance(run, dict) and run.get("is_bold")]


def table_cell_html(text: str | None, runs: list[dict] | None) -> str:
    content = runs_to_html(runs, text or "") if runs else escape(text or "")
    return f"<span class=\"docx-cell\">{content}</span>"


def render_table_html(rows: list[list[str]] | None, cell_runs: list | None = None) -> str:
    if not rows:
        return "<div class='text-muted'><em>[Empty table]</em></div>"
    header = rows[0] if len(rows) > 1 else None
    body = rows[1:] if header else rows
    out: list[str] = ["<div class='table-responsive'><table class='table table-bordered table-sm mb-2'>"]
    if header:
        out.append("<thead><tr>")
        for idx, cell in enumerate(header):
            runs = None
            if cell_runs and cell_runs and len(cell_runs) > 0:
                header_runs_row = cell_runs[0]
                if isinstance(header_runs_row, list) and idx < len(header_runs_row):
                    runs = header_runs_row[idx]
            out.append(f"<th>{table_cell_html(cell, runs)}</th>")
        out.append("</tr></thead>")
    out.append("<tbody>")
    for r_index, row in enumerate(body, start=1 if header else 0):
        out.append("<tr>")
        for c_index, cell in enumerate(row):
            runs = None
            if cell_runs and r_index < len(cell_runs):
                row_runs = cell_runs[r_index]
                if isinstance(row_runs, list) and c_index < len(row_runs):
                    runs = row_runs[c_index]
            out.append(f"<td>{table_cell_html(cell, runs)}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


TEXT_BLOCK_TYPES = {"question_text", "paragraph", "text", "instruction", "heading", "case_study"}


def _clone_block(block: dict) -> dict:
    try:
        return deepcopy(block)
    except Exception:
        return dict(block)


def summarize_text_from_blocks(blocks: Iterable[dict]) -> str:
    parts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if (block.get("type") or "").lower() in TEXT_BLOCK_TYPES:
            txt = str(block.get("text") or "").strip()
            if txt:
                parts.append(txt)
    return " ".join(parts).strip()


def strip_non_bold_from_blocks(blocks: list[dict] | None) -> list[dict]:
    if not blocks:
        return []
    cleaned: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        clone = _clone_block(block)
        btype = (clone.get("type") or "").lower()
        if btype in TEXT_BLOCK_TYPES:
            original_runs = clone.get("runs")
            if original_runs:
                runs = keep_bold_runs(original_runs)
                clone["runs"] = runs
                clone["text"] = summarize_runs_text(runs)
            else:
                clone["text"] = clone.get("text", "")
        elif btype == "table":
            rows = clone.get("rows") or []
            cell_runs = clone.get("cell_runs") or []
            if not cell_runs:
                clone["rows"] = rows
                cleaned.append(clone)
                continue
            new_rows = []
            new_cell_runs = []
            for r_index, row in enumerate(rows):
                new_row: list[str] = []
                new_run_row: list[list[dict]] = []
                for c_index, cell in enumerate(row):
                    runs = []
                    if r_index < len(cell_runs):
                        row_runs = cell_runs[r_index]
                        if isinstance(row_runs, list) and c_index < len(row_runs):
                            runs = keep_bold_runs(row_runs[c_index])
                    new_run_row.append(runs)
                    new_row.append(summarize_runs_text(runs))
                new_rows.append(new_row)
                new_cell_runs.append(new_run_row)
            clone["rows"] = new_rows
            clone["cell_runs"] = new_cell_runs
        cleaned.append(clone)
    return cleaned


def strip_non_bold_from_node(node: dict | None) -> dict | None:
    if not isinstance(node, dict):
        return node
    copy_node = _clone_block(node)
    content = copy_node.get("content")
    if isinstance(content, list):
        updated_blocks = strip_non_bold_from_blocks(content)
        copy_node["content"] = updated_blocks
        copy_node["text"] = summarize_text_from_blocks(updated_blocks)
    children = copy_node.get("children")
    if isinstance(children, list):
        copy_node["children"] = [
            strip_non_bold_from_node(child) or child for child in children
        ]
    return copy_node


def strip_non_bold_from_manifest_nodes(nodes: list[dict] | None) -> list[dict]:
    if not nodes:
        return []
    return [strip_non_bold_from_node(node) or node for node in nodes]
