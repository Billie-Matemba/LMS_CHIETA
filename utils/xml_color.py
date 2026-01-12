from __future__ import annotations

from lxml import etree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _is_disabled(val: str | None) -> bool:
    if val is None:
        return False
    val = str(val).strip().lower()
    return val in {"0", "false", "off", "no"}


def extract_color_attrs(rpr: etree._Element | None) -> dict:
    if rpr is None:
        return {}

    payload: dict[str, str] = {}
    color = rpr.find("w:color", namespaces=NS)
    if color is not None and not _is_disabled(color.get(f"{{{NS['w']}}}val")):
        val = color.get(f"{{{NS['w']}}}val")
        if val:
            payload["color"] = val

    highlight = rpr.find("w:highlight", namespaces=NS)
    if highlight is not None and not _is_disabled(highlight.get(f"{{{NS['w']}}}val")):
        val = highlight.get(f"{{{NS['w']}}}val")
        if val:
            payload["highlight"] = val

    shading = rpr.find("w:shd", namespaces=NS)
    if shading is not None:
        fill = shading.get(f"{{{NS['w']}}}fill")
        if fill and not _is_disabled(fill):
            payload["shading"] = fill
    return payload
