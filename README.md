# CHIETA LMS Randomization Pipeline

This repository contains the end-to-end pipeline that ingests Word assessments, extracts structural content, allows manual curation with a lasso tool, and produces randomized snapshots that can be reviewed and forwarded through the CHIETA workflow.

## High-Level Flow

1. **Admin upload & extraction** (`core/views.py:783-864`)

   - Admin uploads a DOCX via the Administrator Dashboard.
   - `extract_docx` produces a manifest of blocks; `save_robust_manifest_to_db` writes them to `ExamNode` records tied to a new `Paper`.
   - An `Assessment` row (paper_type `admin_upload`) is created for the paper.

2. **Advanced pipeline curation** (`core/views.py:1628-2045` + `lasso.js`)

   - The Assessor Developer opens the Advanced View, which hydrates an `ExtractorPaper` and existing `ExtractorUserBox` records.
   - The lasso tool lets users draw, edit, or AI-suggest boxes; metadata (question numbers, marks, module info) is persisted via AJAX endpoints in `core/extractor_views.py`.

3. **Snapshot creation & review** (`core/views.py:2218-2534`, `core/views.py:1246-1602`)

   - `randomize_paper_structure_view` or the Save New Randomized Snapshot button builds a randomized `Paper` from the curated block pool (`build_randomized_structure_from_pool`).
   - Each snapshot is stored as a randomized `Paper` plus an `Assessment` with `paper_type='randomized'`.
   - The assessor reviews snapshots at `/assessor-developer/randomized/<assessment_id>/`, can refresh them, delete/convert individual blocks, and forward to ETQA/QCTO.

4. **Downstream flows**
   - Snapshots are visible in the Captured Snapshots section of `/assessor-developer/` (`core/views.py:1200-1243`).
   - Once validated, they progress through moderator, ETQA, and QCTO dashboards using the normal `Assessment` lifecycle.

## Data Model Cheat Sheet

All models live in `core/models.py` unless noted.

- **Paper** (`core/models.py:533-554`)

  - `name`: Label for the paper (randomized names get `(... Randomized)` suffix).
  - `qualification`: FK to the qualification.
  - `is_randomized`: Boolean flag; differentiates originals vs snapshots.
  - `structure_json`: Stores reconstruction metadata. Randomization payload includes:
    ```json
    {
      "randomization": {
        "module_name": "Maintenance Planner",
        "module_number": "1A",
        "status": "paired",
        "allowed_letters": ["A", "B"],
        "snapshot_pool_used": true,
        "snapshot_pool_size": 87,
        "source": "snapshot_pool",
        "last_refreshed": "2025-09-27T19:05:42.537165+00:00",
        "base_paper_id": 8,
        "base_assessment_id": 3,
        "base_extractor_id": 14
      }
    }
    ```
  - `total_marks`: Sum of question marks for reporting.
  - `created_by`: User who owns the paper.

- **Assessment** (`core/models.py:195-319`)

  - `paper`: String label shown in queues.
  - `paper_type`: `'admin_upload'` or `'randomized'`.
  - `paper_link`: FK to the actual `Paper`.
  - `module_name` / `module_number`: metadata surfaced in dashboards & banks.
  - `extractor_paper`: Links to the advanced pipeline representation.
  - Status fields (`status`, `forward_to_moderator`, ETQA/QCTO flags) drive workflow.

- **ExamNode** (`core/models.py:570-605`)

  - Represents each structural block (question, instruction, table, image, text).
  - `order_index` controls display order. Parent/child relationships allow sub-questions.

- **ExtractorPaper & ExtractorUserBox** (`core/chieta_extractor/models.py`)
  - `ExtractorPaper`: Master record for the scanned document inside the advanced tool.
  - `ExtractorUserBox`: Persisted lasso boxes; important fields include `qtype`, `question_number`, `parent_number`, `marks`, `header_label`, `case_study_label`, coordinates, and serialized `content`.

## Key Views & Responsibilities

| View                             | Location             | Purpose                                                                                                  |
| -------------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------- |
| `admin_dashboard`                | `core/views.py:819`  | Upload DOCX, run extractor, seed `Paper`/`Assessment`.                                                   |
| `assessor_developer`             | `core/views.py:1206` | Lists assessments, shows snapshot dropdown, links to advanced view.                                      |
| `assessor_developer_paper`       | `core/views.py:1628` | Opens the advanced pipeline (lasso UI).                                                                  |
| `assessor_randomized_snapshot`   | `core/views.py:1246` | Central snapshot review & editing hub. Supports refresh, new snapshot, delete/convert block, forwarding. |
| `randomize_paper_structure_view` | `core/views.py:2417` | One-off snapshot creation from an original paper.                                                        |
| `save_blocks_view`               | `core/views.py:2063` | Persists `ExtractorUserBox` content into `ExamNode` when required.                                       |

## Critical Front-End Scripts

- **`lasso.js`** (`chieta_LMS/Chieta_Paper_Extractor/exam_extractor/static/exam_extractor/lasso.js`)

  - Handles drag-to-select, box editing, AI suggestions, and metadata editing for blocks.
  - Publishes events to backend endpoints for create/update/delete.
  - Provides lightweight toast notifications, spinner overlay, and LLM status indicator.

- **Snapshot Node Partial** (`core/templates/core/assessor-developer/_snapshot_node.html`)
  - Renders each block in the snapshot view, including new inline actions:
    - `Delete` ? POST `action=delete_node`.
    - `Mark Instruction` / `Mark Question` ? POST `action=convert_node` with target type.
  - Uses recursive inclusion so every child block inherits the same controls.

## Using the Pipeline

1. **Upload the source paper**

   - Navigate to `/administrator/` and upload the DOCX with the appropriate qualification and action button (Moderator/ETQA).
   - Verify extraction stats in the success toast.

2. **Curate blocks in the advanced pipeline**

   - From `/assessor-developer/`, click Open Advanced View next to the assessment.
   - Draw or edit lasso boxes, assign question numbers, marks, and metadata.
   - Use Save metadata or AI suggestions to build a clean pool.

3. **Create randomized snapshots**

   - Back on `/assessor-developer/`, pick the assessment and choose `Randomize` (legacy) or visit an existing snapshot and click **Save New Randomized Snapshot**.
   - The system clones the structure, pulls matching boxes from the pool, and stores a new `Paper`/`Assessment` pair. The banner on the snapshot page confirms the new EISA ID and pool coverage.

4. **Clean up the snapshot**

   - On the snapshot page:
     - Remove stray instructions/questions with **Delete**.
     - Convert instructions/questions to keep cover materials at the top.
     - Use **Update Snapshot Structure** after tweaking the pool to re-materialize content.

5. **Forward or archive**
   - Use the action buttons to forward to ETQA/QCTO or release to learners once the snapshot is approved.

## Tips & Conventions

- **Consistent numbering**: Randomization relies on matching `question_number` and `parent_number` between the blueprint and the captured boxes. Make sure all sources for a module share the same numbering scheme to maximize pool hits.
- **Structure JSON**: Any custom metadata should live under `Paper.structure_json['randomization']` to keep downstream views in sync.
- **Testing snapshots**: After each Save New Randomized Snapshot, verify the console log `SNAPSHOT SAVED: ` to confirm pool size and mark totals.
- **Module metadata**: Even though `Paper` no longer stores `module_name`/`paper_letter`, the information is preserved in `Assessment.module_name`/`module_number` and the randomization payload.
- **Qualification registry**: Use `core/config/qualifications.yaml` (synced via `core/qualification_registry.py`) as the single source of truth for qualification names, SAQA IDs, and module codes.

## Recently Added Enhancements

- Snapshot actions: delete or convert any block directly from the review page (`core/views.py:1328-1436`, `_snapshot_node.html`).
- Success banner & dropdown sort ensure new snapshots appear immediately (`core/views.py:1532-1599`, `core/templates/core/assessor-developer/randomized_snapshot.html`).
- Randomization metadata fallbacks prevent crashes when originals lack module fields (`core/views.py:2431-2491`).
- **Memo-first editing** (Dec 2025): the snapshot view now has a Paper/Memo toggle. Keep it in **Memo** mode when uploading an answer key:
  1. Review the captured block (tables/images stay intact).
  2. Click **Add Corresponding Question Block**. The block’s current text becomes the stored `QuestionMemo`; the block itself stays editable so you can blank out learner text manually.
  3. Switch to **Paper** mode only when you need to hand-type memo text via the textarea.
  Download the learner paper via the standard buttons or append `?variant=memo` to get the memo pack generated from those saved `QuestionMemo` entries.

Keep this README close when onboarding new teammatesthe files referenced above are the main surfaces youll touch when adjusting the randomization pipeline or the advanced extraction tooling.

#####################################################################################

# how to run the application

1. Open your terminal in the project’s root directory and run the following commands:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# For Windows:
venv\Scripts\activate

2.
Create a Database in pgAdmin

Open pgAdmin.

Create a new PostgreSQL database (e.g., chieta_lms_db).

Note down the database name, user, password, host, and port — you’ll need them in the next steps.

3.

Update Database Settings in the First settings.py

Navigate to:

core/settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_database_name',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

4.
Update Database Settings in the Second settings.py

Navigate to the second settings file which just under rebuild_docx_from_json.py

Repeat the same process as in Step 3 — ensure the same database configuration is applied here as well.

5.
Run Migrations

Apply the database migrations to create necessary tables:

python manage.py makemigrations
python manage.py migrate

6.

Create a Superuser

Create an admin (superuser) account to access the Django admin panel:

python manage.py createsuperuser


Follow the prompts to set up your username, email, and password.

Please go to pg admin and change the users default status from learner to admin will fix this later. The created user will be under the custom_user table

7.

Run the Server and Log In

Start the Django development server:

python manage.py runserver
###############################
```
