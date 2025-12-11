# Assessment Workflow (Admin Upload → Student Write → Marking)

This manual describes the end-to-end flow of a paper that is uploaded by an
administrator, written by learners, and then marked/moderated. Use it as a
reference when onboarding new administrators, moderators or developers.

> Key views/templates referenced below live in `core/views.py` and the
> `core/templates/core/*` tree.

## 1. Admin Upload Phase

### Upload form
- **View**: `upload_assessment` (`core/views.py:3281`)
- **Template**: `core/assessor-developer/upload_assessment.html`

An administrator selects:
1. Qualification/module metadata.
2. DOCX question paper (required).
3. DOCX/PDF memo (required for admin uploads).
4. Optional comments.

The view validates both files, stores them under `assessments/` and
`assessments/memos/`, and creates an `Assessment` record with
`paper_type='admin_upload'`. If extraction succeeds, the paper is parsed into a
`Paper` + `ExamNode` tree for downstream editing.

### ETQA / moderation prerequisites
- Admin uploads use the legacy `memo` field (not `memo_file`).
- For later forwarding, ensure the assessment has the correct qualification and
  that the memo is attached; otherwise moderators will block progression.

## 2. Randomized Snapshot & Memo Prep (optional)

If the paper is randomized, the staff interface at
`/assessor-developer/randomized/<assessment_id>/` (see `assessor_randomized_snapshot`
view) allows editors to tweak blocks, upload randomized memos, and forward to
moderators. The new cover-page fallback, memo enforcement, and visual block
editor ensure the output looks identical to the uploaded paper when exported.

When the assessor/memo developer clicks **Forward to Moderator**, the assessment
status changes to “Submitted to Moderator” and the moderator dashboard picks it
up automatically.

## 3. Learner Experience

### Assignment release
Once an assessment is ready (admin upload or randomized), it can be released to
students. Learners see available assessments on their dashboard and click
**Write Exam**.

### Writing the exam
- **View**: `write_exam` or `write_paper_simple` (`core/views.py:4587` / `4921`)
- **Template**: `core/student/write_exam.html`

Highlights:
- Learner must have a `student_number` and matching qualification.
- The view builds either the legacy `GeneratedQuestion` list or the modern
  `ExamNode` tree (`node_sequence`). Questions display with images/tables exactly
  as captured.
- Answers are posted via form fields named `answer_node_<ExamNode.id>`.

### Submission
- **View**: `submit_exam` (`core/views.py:4685`) or `submit_paper_simple`

Flow:
1. Validate duplicates (one submission per learner per assessment).
2. Persist old-pipeline `ExamAnswer` rows when relevant.
3. Collect new-pipeline answers into an array (`answers_data`).
4. Create an `ExamSubmission` record, generate a PDF copy of the attempt using
   `core/student/exam_pdf_template.html`, and store it on the submission.
5. Send success/auto-save responses (JSON for Ajax or flash messages otherwise).

This ensures moderators and markers can download exactly what the learner saw.

## 4. Marking & Moderation

### Marker dashboard
- **View**: `assessor_maker_dashboard` (`core/views.py:5127`)
- **Template**: `core/assessor/mark_exam.html`

Available to roles `assessor_marker`, `internal_mod`, `external_mod`. The page
lists:
- Registered learners (online and offline).
- All `ExamSubmission` entries, with links to the uploaded learner script, memo,
  and metadata.
- Filtering helpers to slice by paper/assessment.

Markers download the learner’s PDF, grade it offline or upload mark sheets, and
can forward outcomes back up the chain (moderator → ETQA → QCTO) using the
status controls that ship with the assessment records.

### Status progression summary
1. **Draft** – after upload/randomization.
2. **Submitted to Moderator** – once memo is ready and forwarded.
3. **Approved**, **Submitted to ETQA/QCTO**, etc. – via action buttons in the
   assessor & moderator dashboards.
4. **Released to students** – once signed off, enabling learner access.

## 5. Offline / Assessment Center Support (optional)

The same views support CSV register uploads and offline PDF submissions. See:
- `upload_student_register` and
- `upload_offline_exam_submission` (near `core/views.py:5202` and `5411`)
for details on how centers batch-upload learner rosters and scanned scripts.

## Troubleshooting Tips
- **Missing memo when forwarding**: ensure admin uploads use the `memo` field,
  while randomized copies rely on `memo_file`. The view enforces this and shows
  clear error messages.
- **Learner cannot access exam**: check `assessment.status == "Released to
  students"` and matching qualification.
- **PDF generation failure**: The submission still saves, but a warning is shown.
  Inspect server logs for `xhtml2pdf` errors.
- **Cover page missing**: For randomized papers, the cover fallback in the
  snapshot view ensures the cover reuses the bank’s ExtractorUserBox payload.
  Verify `selected_boxes` on the paper contains a `cover_page` entry.

By following this pipeline, every paper uploaded by admin staff travels through
editing, randomization, memo capture, learner delivery, and marking with the
required checks and audit trails. Refer back to the view names above when
extending or debugging any section of the workflow.
