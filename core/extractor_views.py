

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db.models import Max
from django.urls import reverse
import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from core.models import ExtractorPaper, ExtractorBlock, ExtractorBlockImage
from utils.extract_docx import extract_blocks_from_docx

from core.models import ExtractorPaper, ExtractorBlock, ExtractorUserBox, ExtractorTestPaper, ExtractorTestItem
from core import qualification_registry
from core.models import Qualification
# from core.qualification_registry import get_qualification_meta  # Not available, using alternative

# Import utility functions (assuming they exist in utils)
from .utils.extractor import (
    annotate_paper_questions,
    classify_blocks_llm,
    suggest_boxes_for_paper,
    convert_emf_images,
    list_modules,
    bank_counts,
    pick_random_for_qnums,
    build_test_from_boxes,
    boxes_for_ids_preserve_order,
    paper_to_markdown,
    classify_blocks_with_markdown,
    delimit_rubric_sections,
    gadzira_suggest_boxes,
)

def paper_view(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    blocks = paper.blocks.select_related().prefetch_related("images").order_by("order_index")
    boxes = list(paper.user_boxes.order_by("-created_at"))
    
    # Heuristic: detect question starts by numbering or the word 'Question', capture marks
    q_headers = {}
    q_re = re.compile(r"^(?:question\s*)?(\d+(?:[\.\)\-]\d+)*\.?|\d+)(?:\s*[:\-\.]|\))?\s*",
                      re.IGNORECASE)
    marks_re = re.compile(r"(\d+)\s*marks?", re.IGNORECASE)
    for b in blocks:
        t = (b.text or "").strip()
        if not t:
            continue
        # Match common forms: 'Question 1.1', '1.', '1.1.2', '1)'
        m = q_re.match(t)
        if m:
            qnum_raw = m.group(1).rstrip('.-')
            mm = marks_re.search(t)
            marks = mm.group(1) if mm else None
            label = f"Question {qnum_raw}"
            if marks:
                label += f" ({marks} Marks)"
            q_headers[b.id] = label

    qualification_catalog = qualification_registry.get_entries()
    module_catalog_source = qualification_registry.module_map_by_name()
    qualifications_qs = Qualification.objects.order_by("name")

    module_catalog: dict[str, list[dict[str, object]]] = {}
    for qual in qualifications_qs:
        key = qual.name
        modules = module_catalog_source.get(key) or []
        if not modules:
            # qual_meta = get_qualification_meta(key)  # Not available
            # module_map = qual_meta.get("modules", {}) if isinstance(qual_meta, dict) else {}
            module_map = {}  # Placeholder, since get_qualification_meta is not available
            if isinstance(module_map, dict):
                modules = [
                    {
                        "code": code,
                        "label": (
                            meta.get("label")
                            if isinstance(meta, dict) and meta.get("label")
                            else f"Module {code}"
                        ),
                    }
                    for code, meta in module_map.items()
                ]
        module_catalog[key] = modules or []

    for key, modules in module_catalog_source.items():
        module_catalog.setdefault(key, modules or [])

    # Determine dashboard URL based on user role (aligned with your existing system)
    user = request.user
    dashboard_url = "custom_login"  # sensible fallback if user role isn't available

    if user.is_authenticated and hasattr(user, "role"):
        role_mapping = {
            "admin": "admin_dashboard",
            "moderator": "moderator_developer",  # matches existing redirect logic
            "internal_mod": "internal_moderator_dashboard",
            "assessor_marker": "assessor_maker_dashboard",
            "external_mod": "external_moderator_dashboard",
            "assessor_dev": "assessor_developer",
            "qcto": "qcto_dashboard",
            "etqa": "etqa_dashboard",
            "learner": "student_dashboard",
            "assessment_center": "assessment_center",
            "default": "default",
        }
        dashboard_url = role_mapping.get(user.role)
        if not dashboard_url:
            dashboard_url = "admin_dashboard" if user.is_staff else "waiting_activation"
    
    # Get display name for the dashboard
    dashboard_names = {
        'admin_dashboard': 'Admin Dashboard',
        'moderator_developer': 'Moderator Developer Dashboard',
        'internal_moderator_dashboard': 'Internal Moderator Dashboard',
        'assessor_maker_dashboard': 'Assessor Marker Dashboard',
        'external_moderator_dashboard': 'External Moderator Dashboard',
        'assessor_developer': 'Assessor Developer Dashboard',
        'qcto_dashboard': 'QCTO Dashboard',
        'etqa_dashboard': 'ETQA Dashboard',
        "student_dashboard": "Student Dashboard",
        "assessment_center": "Assessment Center Dashboard",
        "default": "Default Dashboard",
        "waiting_activation": "Awaiting Activation",
        "custom_login": "Sign In",
    }
    
    dashboard_display_name = dashboard_names.get(dashboard_url, 'Dashboard')

    return render(
        request,
        "core/exam_extractor/paper.html",
        {
            "paper": paper,
            "blocks": blocks,
            "boxes": boxes,
            "q_headers": q_headers,
            "qualification_catalog": qualification_catalog,
            "module_catalog_json": json.dumps(module_catalog),
            "qualifications": qualifications_qs,
            "dashboard_url": dashboard_url,
            "dashboard_display_name": dashboard_display_name,
        },
    )

@require_POST
def create_box(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    data = request.POST
    # Auto-fill from latest detected header if fields are blank
    qnum = (data.get("question_number") or "").strip()
    marks = (data.get("marks") or "").strip()
    if not qnum or not marks:
        last_header = (
            paper.blocks.filter(is_qheader=True)
            .order_by("order_index")
            .last()
        )
        if last_header:
            if not qnum:
                qnum = last_header.detected_qnum or qnum
            if not marks:
                marks = last_header.detected_marks or marks

    content_json = data.get("content_json", "")
    content_type = data.get("content_type", "")
    parent_number = (data.get("parent_number") or "").strip()
    header_label = (data.get("header_label") or "").strip()
    case_study_label = (data.get("case_study_label") or "").strip()

    # Determine next order index for this paper
    last_order = paper.user_boxes.aggregate(m=Max("order_index")).get("m") or 0
    next_order = last_order + 1

    box = ExtractorUserBox.objects.create(
        paper=paper,
        x=float(data.get("x",0)), y=float(data.get("y",0)),
        w=float(data.get("w",0)), h=float(data.get("h",0)),
        order_index=next_order,
        question_number=qnum,
        marks=marks,
        qtype=data.get("qtype",""),
        parent_number=parent_number,
        header_label=header_label,
        case_study_label=case_study_label,
        content_type=content_type,
        content=content_json,
    )
    return JsonResponse({
        "ok": True,
        "box": {
            "id": box.id,
            "x": box.x, "y": box.y, "w": box.w, "h": box.h,
            "order_index": box.order_index,
            "question_number": box.question_number,
            "marks": box.marks,
            "qtype": box.qtype,
            "parent_number": box.parent_number,
            "header_label": box.header_label,
            "case_study_label": box.case_study_label,
            "content_type": box.content_type,
            "content": box.content,
            "created_at": box.created_at.isoformat(),
        }
    })

@require_POST
def update_box(request, paper_id, box_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    box = get_object_or_404(ExtractorUserBox, id=box_id, paper=paper)
    data = request.POST
    # Update coords and meta
    try:
        box.x = float(data.get("x", box.x))
        box.y = float(data.get("y", box.y))
        box.w = float(data.get("w", box.w))
        box.h = float(data.get("h", box.h))
    except ValueError:
        return HttpResponseBadRequest("invalid coords")
    box.question_number = (data.get("question_number") or box.question_number or "").strip()
    box.marks = (data.get("marks") or box.marks or "").strip()
    box.qtype = (data.get("qtype") or box.qtype or "").strip()
    box.parent_number = (data.get("parent_number") or box.parent_number or "").strip()
    box.header_label = (data.get("header_label") or box.header_label or "").strip()
    box.case_study_label = (data.get("case_study_label") or box.case_study_label or "").strip()

    # Update captured content if provided (front-end collects from current rect)
    if "content_json" in data:
        box.content = data.get("content_json") or ""
    if "content_type" in data:
        box.content_type = data.get("content_type") or ""
    box.save()
    return JsonResponse({
        "ok": True,
        "box": {
            "id": box.id,
            "x": box.x, "y": box.y, "w": box.w, "h": box.h,
            "order_index": box.order_index,
            "question_number": box.question_number,
            "marks": box.marks,
            "qtype": box.qtype,
            "parent_number": box.parent_number,
            "header_label": box.header_label,
            "case_study_label": box.case_study_label,
            "content_type": box.content_type,
            "content": box.content,
            "created_at": box.created_at.isoformat(),
        }
    })

def autoclassify(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    # Lightweight heuristics + existing LLM tagger
    annotate_paper_questions(paper)
    include_instr = bool(request.GET.get("include_instructions"))
    classify_blocks_llm(paper, include_instructions=include_instr)
    return redirect("exam_paper", paper_id=paper.id)


@require_POST
def save_system_prompt(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    prompt = (request.POST.get("system_prompt") or "").strip()
    paper.system_prompt = prompt
    paper.save(update_fields=["system_prompt"])
    return redirect("exam_paper", paper_id=paper.id)


@require_POST
def save_paper_meta(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    paper.module_name = (request.POST.get("module_name") or "").strip()
    paper.paper_number = (request.POST.get("paper_number") or "").strip()
    paper.paper_letter = (request.POST.get("paper_letter") or "").strip()
    # optional title override
    if "title" in request.POST:
        paper.title = (request.POST.get("title") or paper.title or "").strip()
    paper.save(update_fields=["module_name", "paper_number", "paper_letter", "title"])
    return redirect("exam_paper", paper_id=paper.id)


def ai_draw_blocks(request, paper_id):
    """Return AI/heuristic suggestions for blocks to draw as boxes.

    Response: { ok: true, items: [ { block_ids:[], question_number:"", marks:"", qtype:"", has_table:bool, has_image:bool } ] }
    """
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    items, strategy = suggest_boxes_for_paper(paper)
    return JsonResponse({"ok": True, "items": items, "strategy": strategy})


def gadzira_draw_blocks(request, paper_id):
    """Return suggestions driven purely by YAML heuristics."""
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    items, strategy = gadzira_suggest_boxes(paper)
    return JsonResponse({"ok": True, "items": items, "strategy": strategy})

@require_POST
def delete_box(request, paper_id, box_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    box = get_object_or_404(ExtractorUserBox, id=box_id, paper=paper)
    box.delete()
    return JsonResponse({"ok": True, "deleted": box_id})


def convert_emf(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    summary = convert_emf_images(paper)
    # Support JSON for async; otherwise redirect back
    if request.headers.get("Accept", "").lower().startswith("application/json") or request.GET.get("json"):
        return JsonResponse({"ok": True, "summary": summary})
    return redirect("exam_paper", paper_id=paper.id)


def bank_info(request, paper_id):
    """Return JSON with modules and optional counts for a selected module."""
    _ = get_object_or_404(ExtractorPaper, id=paper_id)  # existence
    module = request.GET.get("module")
    data = {"modules": list_modules()}
    # Include this paper's base boxes (question only) with their content
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    base = list(
        paper.user_boxes.filter(qtype__in=["question", "question_part"])
            .order_by("order_index")
            .values("id", "order_index", "question_number", "marks", "content_type", "content")
    )
    data["base"] = base
    if module:
        data["counts"] = bank_counts(module)
    return JsonResponse({"ok": True, **data})


@require_POST
def randomize_test(request, paper_id):
    """Build a randomized test using question_numbers from this paper and a selected module."""
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    module = (request.POST.get("module_name") or paper.module_name or "").strip()
    if not module:
        return HttpResponseBadRequest("module_name required")

    # Base question_numbers on this paper's saved boxes in order, question only
    qnums = list(
        paper.user_boxes.filter(qtype__in=["question", "question_part"]).order_by("order_index").values_list("question_number", flat=True)
    )
    # Allow override via POST qnums (comma-separated)
    if request.POST.get("qnums"):
        qnums = [q.strip() for q in request.POST.get("qnums", "").split(",") if q.strip()]
    if not qnums:
        return HttpResponseBadRequest("no question_numbers found")

    # If explicit box_ids provided, use them as-is in order
    box_ids_csv = request.POST.get("box_ids")
    if box_ids_csv:
        try:
            ids = [int(x) for x in box_ids_csv.split(",") if x.strip().isdigit()]
        except ValueError:
            return HttpResponseBadRequest("invalid box_ids")
        boxes = boxes_for_ids_preserve_order(ids)
    else:
        boxes = pick_random_for_qnums(module, qnums)
    title = request.POST.get("title") or f"Randomized Test - {module}"
    test = build_test_from_boxes(module, title, boxes)
    test_url = reverse("exam_view_test", args=[test.id])
    return JsonResponse({"ok": True, "test_id": test.id, "test_url": test_url})


def bank_preview(request, paper_id):
    """Return a randomized preview selection for the chosen module, without persisting.

    Response: { items: [ { question_number, marks, box_id, content_type, content } ] }
    """
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    module = (request.GET.get("module_name") or paper.module_name or "").strip()
    if not module:
        return HttpResponseBadRequest("module_name required")
    qnums = list(
        paper.user_boxes.filter(qtype__in=["question", "question_part"]).order_by("order_index").values_list("question_number", flat=True)
    )
    picks = pick_random_for_qnums(module, qnums)
    items = [
        {
            "question_number": b.question_number,
            "marks": b.marks,
            "box_id": b.id,
            "content_type": b.content_type,
            "content": b.content,
        }
        for b in picks
    ]
    return JsonResponse({"ok": True, "items": items})


def mbalaka_markdown(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    md = paper_to_markdown(paper)
    return JsonResponse({"ok": True, "markdown": md}) if request.headers.get("Accept","" ).startswith("application/json") else (
        render(request, "core/exam_extractor/markdown.html", {"paper": paper, "markdown": md})
    )


@require_POST
def mbalaka_classify(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    summary = classify_blocks_with_markdown(paper)
    if request.headers.get("Accept","" ).startswith("application/json"):
        return JsonResponse({"ok": True, "summary": summary})
    return redirect("exam_paper", paper_id=paper.id)


def delimit_rubric(request, paper_id):
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    summary = delimit_rubric_sections(paper)
    if request.headers.get("Accept","" ).startswith("application/json") or request.GET.get("json"):
        return JsonResponse({"ok": True, "summary": summary})
    return redirect("exam_paper", paper_id=paper.id)


def get_box(request, paper_id, box_id):
    """Return the latest box JSON (coords + meta) from DB.

    Useful when client state is lost; allows JS to repopulate datasets.
    """
    paper = get_object_or_404(ExtractorPaper, id=paper_id)
    box = get_object_or_404(ExtractorUserBox, id=box_id, paper=paper)
    return JsonResponse({
        "ok": True,
        "box": {
            "id": box.id,
            "x": box.x, "y": box.y, "w": box.w, "h": box.h,
            "order_index": box.order_index,
            "question_number": box.question_number,
            "marks": box.marks,
            "qtype": box.qtype,
            "parent_number": box.parent_number,
            "header_label": box.header_label,
            "case_study_label": box.case_study_label,
            "content_type": box.content_type,
            "content": box.content,
            "created_at": box.created_at.isoformat(),
        }
    })


def view_test(request, test_id):
    test = get_object_or_404(ExtractorTestPaper, id=test_id)
    items = list(test.items.order_by("order_index"))
    return render(request, "core/exam_extractor/test.html", {"test": test, "items": items})

def upload_view(request):
    if request.method == "POST" and request.FILES.get("docx"):
        docx_file = request.FILES["docx"]
        paper = ExtractorPaper.objects.create(original_file=docx_file, title=docx_file.name)
        
        # Extract XML-native blocks
        with transaction.atomic():
            blocks = extract_blocks_from_docx(paper.original_file.path, paper=paper)
            # Persist in order
            for i, b in enumerate(blocks):
                block = ExtractorBlock.objects.create(
                    paper=paper,
                    order_index=i,
                    block_type=b["type"],
                    xml=b.get("xml", ""),
                    text=b.get("text", "")
                )
                for img_path in b.get("images", []):
                    ExtractorBlockImage.objects.create(block=block, image=img_path)
        
        # Optional: run auto classify in background-ish (here: inline call)
        # classify_blocks_llm(paper)  # keep it manual for now; see endpoint below
        
        return redirect("exam_paper", paper_id=paper.id)
    
    return render(request, "core/exam_extractor/upload.html")
