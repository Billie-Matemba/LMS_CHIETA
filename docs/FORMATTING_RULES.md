# Exam Paper Formatting Rules

These guidelines describe how question headings should look before running the “Actual Numbering” automation (`core/templates/core/exam_extractor/paper.html`). Following them keeps the auto-detected question number, parent number, and marks accurate.

## Numbering
- **Required prefix** – Start each question or sub-question with a numeric code such as `1`, `1.1`, `2.1.3`, etc. Parentheses and punctuation are fine (`1.1.1)`, `(2.3 -`, `3.2:`). Prefix words like `Question`, `Q`, or `Item` are also accepted (`Question 1.1.2` behaves the same as `1.1.2`).
- **Spacing** – Whitespace (including non-breaking spaces) at the beginning is ignored, so `1.1    Question text` is treated the same as `1.1 Question text`.
- **Parent detection** – The parent of `1.1.1` is obtained by trimming the last segment (`1.1`). Therefore `1.1.2` automatically links to `1.1`, `2.1.4` links to `2.1`, etc. Ensure intermediate parents exist; otherwise children have nowhere to attach.
- **Marks-only blocks** – Lines that contain nothing but `(10 marks)` (or similar) are treated as part of the preceding question and not as new headings. If a heading has no text, add a short description (e.g., `1.1.1 Calculation (10 marks)`).

## Marks
- **Match rule** – Marks are detected when the surrounding text contains a number followed by `mark` or `marks`, e.g., `(10 marks)`, `- 5 marks`, `Total 125 Marks`. If that pattern is missing, we fall back to numbers that appear next to the word “Total” (e.g., `Total = 25`).
- **Sources** – We first use any existing `data-marks` attribute from the block. Otherwise we scan the numbered block plus trailing content (paragraphs, tables, etc.) until the next numbered heading. If still missing, we inspect tables for rows that contain the word “Total” (in the row label) and grab the numeric value from that row.
- **Not detected** – Phrases without the literal pattern (e.g., `ten marks`, `Grade A`, `Total: ____`) are ignored. Include the numeric form `(<number> marks)` near the heading or inside the supporting table.

## Tables & Grades
- Tables render exactly as captured. If a question’s mark allocation lives inside a table, ensure one of the cells contains the `(<number> marks)` text; otherwise fill the marks manually when saving the suggestion.
- Grade labels such as `Grade A / B / C` are not interpreted as marks. Add the numeric value alongside them (e.g., `Grade A (75 marks)`).

## Troubleshooting
1. **Missing marks** – Open the saved block’s “Content → View” modal and confirm the literal `(<number> mark/marks)` text exists. If not, edit the paper or enter the marks manually.
2. **Wrong parent** – Make sure there are no numbering gaps. For example, if you have `2.1.1`, ensure a `2.1` heading appears earlier in the document.
3. **Runaway capture** – If the automation keeps gluing everything into a single block, the next heading’s number probably isn’t recognized. Create a fresh line for the heading so the number is the first token (or prefixed by `Question/Q/Item`).
4. **Tables with totals** – Totals that only show `Total = ____` (without the final numeric value) won’t be parsed. Add the actual number, e.g., `Total = 25 marks`.

Following these conventions minimizes manual cleanup after running Actual Numbering.
