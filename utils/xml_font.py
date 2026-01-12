from __future__ import annotations

"""
Font/run helpers extracted from WordprocessingML.

These helpers stay outside the main extractor so we can extend styling logic
without destabilising the core parsing workflow.
"""

from lxml import etree

from .xml_color import extract_color_attrs

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _is_enabled(elem: etree._Element | None) -> bool:
    """Return True when a formatting element enables the style."""
    if elem is None:
        return False
    val = elem.get(f"{{{NS['w']}}}val")
    if val is None:
        return True
    val = str(val).strip().lower()
    return val not in {"0", "false", "off", "no"}


def extract_run_style(run_elem: etree._Element) -> dict:
    """
    Convert a single <w:r> element into a serialisable dict describing its text
    and basic styling (bold/italics/underline + colors).
    """
    text = "".join(t.text or "" for t in run_elem.findall(".//w:t", namespaces=NS))
    if not text:
        return {}

    rpr = run_elem.find("w:rPr", namespaces=NS)
    payload: dict[str, object] = {"text": text}

    if rpr is not None:
        payload["is_bold"] = _is_enabled(rpr.find("w:b", namespaces=NS))
        payload["is_italic"] = _is_enabled(rpr.find("w:i", namespaces=NS))
        payload["is_underline"] = _is_enabled(rpr.find("w:u", namespaces=NS))
        rstyle = rpr.find("w:rStyle", namespaces=NS)
        if rstyle is not None:
            val = rstyle.get(f"{{{NS['w']}}}val")
            if val:
                payload["style"] = val
        payload.update(extract_color_attrs(rpr))
    else:
        payload["is_bold"] = False
        payload["is_italic"] = False
        payload["is_underline"] = False

    return payload


def extract_runs(element: etree._Element | None) -> list[dict]:
    """Return a list of run-style dicts for the supplied XML element."""
    if element is None:
        return []
    runs = []
    for run in element.findall(".//w:r", namespaces=NS):
        info = extract_run_style(run)
        if info:
            runs.append(info)
    return runs


def extract_runs_from_xml(xml_snippet: str | bytes | None) -> list[dict]:
    """
    Convenience helper when only the XML string is available.
    If parsing fails, an empty list is returned.
    """
    if not xml_snippet:
        return []
    try:
        elem = etree.fromstring(xml_snippet.encode("utf-8") if isinstance(xml_snippet, str) else xml_snippet)
    except Exception:
        return []
    return extract_runs(elem)
