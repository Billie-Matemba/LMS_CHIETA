# Randomized Snapshot Workflow

This document explains how the **Randomized Snapshot** page works after the
recent memo workflow, cover-page rendering and block editor improvements.
It is intended for developers who need to reason about the forwarding
pipeline or extend the UI/logic safely.

> Key entry points:
> - View: `core/views.py:2275` (`assessor_randomized_snapshot`)
> - Template: `core/templates/core/assessor-developer/randomized_snapshot.html`
> - Block partial: `core/templates/core/assessor-developer/_snapshot_node.html`

## Page lifecycle

1. **Request** – `assessor_randomized_snapshot` loads the requested randomized
   assessment and checks permissions (creator, staff, or matching qualification).
2. **Context building** – the view rebuilds `node_tree` from `ExamNode` records,
   adds memo lookups, and injects snapshot metadata (pool info, module details,
   statuses, etc.).
3. **Cover & memo safeguards** – additional context flags ensure the cover page
   is rendered from the captured bank even if the stored node lost its images,
   and enforce that a memo exists before forwarding to a moderator.
4. **Rendering** – the template renders page stats, memo upload controls, the
   cover/instruction block (with previews), and the editable question list.
5. **POST actions** – form submissions (delete node, save node, add memo,
   upload memo, forward to moderator, open pipeline) are handled centrally in
   the view with redirects to keep the UI fresh.

## Cover page fidelity

Because cover nodes often have empty `content` fields once edited, the view now
maps each cover block back to its captured `ExtractorUserBox`. The template
falls back to those payloads when rendering, so cover images remain visible even
after refreshes (`_snapshot_node.html`). This is handled transparently and does
not affect question nodes.

## Memo enforcement & forwarding

Randomized assessments require a memo before moderators can act. The view
(`core/views.py:2391-2457`) derives the `has_memo`/`can_forward_to_moderator`
flags used by the template to:

- Display upload/replace controls with friendly status badges.
- Disable the “Forward to Moderator” button until a memo is uploaded.
- Persist the memo file on upload with file-type validation.

Once forwarded, the action handler updates status/timestamps and sets
`forward_to_moderator` so the workflow progresses consistently.

## Editing workflow

### Inline editing

- Each block includes inputs for number, marks, memo content and notes.
- Editable spans (`.editable-block`) update a hidden JSON payload so the raw
  `ExamNode.content` can be saved without diving into JSON by default.

### Full block editor

The **Full Block Editor** button launches `#rawBlockModal` which now supports
two modes:

1. **JSON Mode** – textarea showing the raw content array.
2. **Visual Block Mode** – renders each structured block in a “card” with
   editable text areas, table HTML, or image previews (captions plus thumbnail
   gallery).

Key helper functions:

- `serializeNodeContent` – walks inline editable spans and reconstructs the JSON.
- `openRawEditor` – populates the modal with either serialized inline data or
  the last-saved JSON payload.
- `renderBlockEditorPanel` – builds the new visual layout, with a thumbnail
  preview for images/figures (including base64, URL or media-path references).
- `writeRawEditorToField` – syncs modal edits back into the hidden form fields.

### Saving from the modal

The modal footer now exposes three actions:

| Button              | Purpose                                                                 |
|---------------------|--------------------------------------------------------------------------|
| **Use Inline Editor** | Switch back to inline mode without altering stored JSON.                |
| **Use This JSON**     | Persist the edited payload into the form (raw mode) but keep the modal open. |
| **Save Block**        | Persist the payload, set the action to `save_node_content`, submit the block form, and close the modal. |

This guarantees edits made inside the modal get written to the database even if
no inline fields were touched.

## Moderator-ready output

When blocks are saved (inline or via modal) they update the underlying
`ExamNode` and memo tables. The randomized PDF/Word downloads (`download_randomized_pdf`)
pull from the same nodes, so the forwarded paper and memo retain consistent
formatting. The cover fallback logic ensures exported PDFs still display the
original cover page assets.

## Deployment notes

- No schema changes were required; everything happens at the view/template/JS layer.
- Static assets (Bootstrap) are loaded from CDN, so no additional bundling is needed.
- If new block types appear, extend `renderBlockEditorPanel`/`collectBlockEditorPayload`
  to keep the visual editor in sync.

For further tweaks, search for “memo” in `core/views.py` and “block-editor” in
`core/templates/core/assessor-developer/randomized_snapshot.html` to find the
relevant sections quickly.
