import json
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from randomise_paper_with_memo_crud import (
    MemoManager, MemoRandomiser, MemoGenerator, process_randomisation_form
)
from core.models import Paper, Qualification, ExamNode, PaperMemo, QuestionMemo

# ...existing views...

@require_http_methods(["POST"])
def randomise_paper_with_memo(request):
    """
    Handle memo randomisation form submission
    Creates randomised paper and saves memos to database
    """
    try:
        paper_id = request.POST.get('paper_id')
        qualification_id = request.POST.get('qualification_id')
        
        # Process form
        randomised_paper, paper_memo, message = process_randomisation_form(
            request, paper_id, qualification_id
        )
        
        messages.success(request, message)
        return redirect('assessor_developer')
        
    except Exception as e:
        messages.error(request, f"Randomisation failed: {str(e)}")
        return redirect('assessor_developer')


@require_http_methods(["GET"])
def view_paper_memo(request, paper_id: str):
    """
    Display paper memo in HTML
    """
    paper = get_object_or_404(Paper, id=paper_id)
    
    try:
        paper_memo = paper.memo
        html_content = MemoGenerator.generate_html_memo(paper_memo)
        return HttpResponse(html_content, content_type='text/html')
    except:
        return render(request, '404.html', {'message': 'No memo found for this paper'})


@require_http_methods(["GET"])
def download_paper_memo_pdf(request, paper_id: str):
    """
    Download paper memo as PDF
    """
    paper = get_object_or_404(Paper, id=paper_id)
    
    try:
        paper_memo = paper.memo
        pdf_bytes = MemoGenerator.generate_pdf_memo(paper_memo)
        
        if not pdf_bytes:
            messages.error(request, "PDF generation not available")
            return redirect('view_paper', paper_id=paper_id)
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{paper.name}_memo.pdf"'
        return response
        
    except Exception as e:
        messages.error(request, f"PDF download failed: {str(e)}")
        return redirect('view_paper', paper_id=paper_id)


def view_paper(request, paper_id: str):
    """
    Main paper view - shows paper with memo tab
    """
    paper = get_object_or_404(Paper, id=paper_id)
    nodes = paper.nodes.all().order_by('order_index')
    
    # Check if memo exists
    has_memo = hasattr(paper, 'memo') and paper.memo is not None
    
    context = {
        'paper': paper,
        'nodes': nodes,
        'has_memo': has_memo,
        'qualification': paper.qualification,
    }
    
    return render(request, 'assessor/view_paper.html', context)


@login_required
def assessor_developer(request):
    """Assessor developer dashboard with viewpools + memo randomisation"""
    
    # Get papers and qualifications for memo randomisation tab
    papers = Paper.objects.all().order_by('-created_at')
    qualifications = Qualification.objects.all()
    
    # Get selected paper from query params
    selected_paper_id = request.GET.get('paper_id')
    selected_paper = None
    nodes = []
    
    if selected_paper_id:
        try:
            selected_paper = Paper.objects.get(id=selected_paper_id)
            nodes = selected_paper.nodes.all().order_by('order_index')
        except Paper.DoesNotExist:
            pass
    
    context = {
        'papers': papers,
        'qualifications': qualifications,
        'selected_paper': selected_paper,
        'nodes': nodes,
    }
    
    return render(request, 'assessor/assessor_developer.html', context)


@login_required
def randomised_papers_list(request):
    """List all randomised papers with memo management"""
    # Get papers that have a parent (indicating they're randomised)
    randomised_papers = Paper.objects.filter(
        parent_paper__isnull=False
    ).order_by('-created_at')
    
    context = {
        'papers': randomised_papers,
        'total_count': randomised_papers.count(),
    }
    
    return render(request, 'assessor/randomised_papers_list.html', context)


@login_required
def randomised_paper_memo_crud(request, paper_id: str):
    """CRUD interface for managing memos on a randomised paper"""
    paper = get_object_or_404(Paper, id=paper_id)
    nodes = paper.nodes.filter(node_type='question').order_by('order_index')
    
    # Get or create memo for this paper
    paper_memo, created = PaperMemo.objects.get_or_create(
        paper=paper,
        defaults={'created_by': request.user}
    )
    
    # Build memo dict for easy lookup in template
    memos = {}
    for q_memo in paper_memo.questions.all():
        memos[q_memo.exam_node_id] = {
            'content': q_memo.content,
            'notes': q_memo.notes,
            'id': q_memo.id
        }
    
    context = {
        'paper': paper,
        'parent_paper': paper.parent_paper,
        'nodes': nodes,
        'paper_memo': paper_memo,
        'memos': memos,
    }
    
    return render(request, 'assessor/randomised_paper_memo_crud.html', context)


@login_required
@require_http_methods(["POST"])
def save_question_memo(request, paper_id: str, node_id: str):
    """Save or update memo for a specific question"""
    paper = get_object_or_404(Paper, id=paper_id)
    exam_node = get_object_or_404(ExamNode, id=node_id, paper=paper)
    
    # Get or create paper memo
    paper_memo, _ = PaperMemo.objects.get_or_create(
        paper=paper,
        defaults={'created_by': request.user}
    )
    
    # Extract data from form
    content = request.POST.get('content', '').strip()
    notes = request.POST.get('notes', '').strip()
    
    if not content:
        return JsonResponse({
            'success': False,
            'message': 'Memo content cannot be empty'
        }, status=400)
    
    # Create or update question memo
    q_memo, created = QuestionMemo.objects.update_or_create(
        paper_memo=paper_memo,
        exam_node=exam_node,
        defaults={
            'question_number': exam_node.number or 'Unknown',
            'content': content,
            'notes': notes
        }
    )
    
    action = 'Created' if created else 'Updated'
    message = f"{action} memo for Q{exam_node.number or '?'}"
    print(f"✅ {message}")
    
    return JsonResponse({
        'success': True,
        'message': message,
        'memo_id': q_memo.id
    })


@login_required
@require_http_methods(["POST"])
def convert_question_to_memo(request, paper_id: str, node_id: str):
    """
    Turn the current question block content into a memo entry.
    Stores the existing ExamNode text as the memo answer so
    assessors can blank/edit the question into a student paper.
    """
    paper = get_object_or_404(Paper, id=paper_id)
    exam_node = get_object_or_404(ExamNode, id=node_id, paper=paper)

    paper_memo, _ = PaperMemo.objects.get_or_create(
        paper=paper,
        defaults={'created_by': request.user}
    )

    existing_memo = QuestionMemo.objects.filter(
        paper_memo=paper_memo,
        exam_node=exam_node
    ).first()

    force = request.POST.get('force', 'false').lower() in ('1', 'true', 'yes', 'on')
    if existing_memo and not force:
        return JsonResponse({
            'success': False,
            'message': 'Memo already exists for this question. Pass force=1 to overwrite.'
        }, status=400)

    memo_text = request.POST.get('memo_text', exam_node.text or '').strip()
    if not memo_text:
        return JsonResponse({
            'success': False,
            'message': 'Question block has no content to convert.'
        }, status=400)

    notes = request.POST.get('notes', '').strip()
    q_memo, created = QuestionMemo.objects.update_or_create(
        paper_memo=paper_memo,
        exam_node=exam_node,
        defaults={
            'question_number': exam_node.number or str(exam_node.order_index + 1),
            'content': memo_text,
            'notes': notes
        }
    )

    action = 'Converted' if created or not existing_memo else 'Updated'
    return JsonResponse({
        'success': True,
        'message': f'{action} memo block for Q{exam_node.number or "?"}',
        'memo_id': q_memo.id,
        'memo_content': q_memo.content,
        'notes': q_memo.notes,
    })


@login_required
@require_http_methods(["POST"])
def update_question_block(request, paper_id: str, node_id: str):
    """Persist edited question/paper text back onto the ExamNode."""
    paper = get_object_or_404(Paper, id=paper_id)
    exam_node = get_object_or_404(ExamNode, id=node_id, paper=paper)

    new_text = request.POST.get('text', '').strip()
    if not new_text:
        return JsonResponse({
            'success': False,
            'message': 'Question text cannot be empty.'
        }, status=400)

    exam_node.text = new_text
    update_fields = ['text']

    content_payload = request.POST.get('content')
    if content_payload:
        try:
            exam_node.content = json.loads(content_payload)
        except Exception:
            # Fallback to storing raw string for now to avoid breaking edits
            exam_node.content = content_payload
        update_fields.append('content')

    exam_node.save(update_fields=update_fields)

    return JsonResponse({
        'success': True,
        'message': f'Updated paper block for Q{exam_node.number or "?"}'
    })


@login_required
@require_http_methods(["POST"])
def finalize_randomised_paper_memo(request, paper_id: str):
    """
    Ensure every question has a memo entry before allowing assessors
    to forward/downstream the randomised paper.
    """
    paper = get_object_or_404(Paper, id=paper_id)
    question_nodes = paper.nodes.filter(node_type='question')
    total_questions = question_nodes.count()

    try:
        paper_memo = paper.memo
        memo_count = paper_memo.questions.count()
    except PaperMemo.DoesNotExist:
        paper_memo = None
        memo_count = 0

    if memo_count < total_questions:
        return JsonResponse({
            'success': False,
            'message': f'Only {memo_count} of {total_questions} questions have memos.'
        }, status=400)

    if paper_memo:
        paper_memo.save(update_fields=['updated_at'])

    return JsonResponse({
        'success': True,
        'message': 'All memo blocks saved. You can now forward or download the memo.',
        'total_questions': total_questions,
        'memo_count': memo_count
    })


@login_required
@require_http_methods(["DELETE"])
def delete_question_memo(request, paper_id: str, node_id: str):
    """Delete memo for a specific question"""
    paper = get_object_or_404(Paper, id=paper_id)
    exam_node = get_object_or_404(ExamNode, id=node_id, paper=paper)
    
    try:
        q_memo = QuestionMemo.objects.get(
            paper_memo__paper=paper,
            exam_node=exam_node
        )
        q_number = q_memo.question_number
        q_memo.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Deleted memo for Q{q_number}'
        })
    except QuestionMemo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Memo not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def view_randomised_paper_memo(request, paper_id: str):
    """View memo in HTML format"""
    paper = get_object_or_404(Paper, id=paper_id)
    
    try:
        paper_memo = paper.memo
        html_content = MemoGenerator.generate_html_memo(paper_memo)
        return HttpResponse(html_content, content_type='text/html')
    except:
        return render(request, '404.html', {
            'message': 'No memo found for this randomised paper'
        }, status=404)


@login_required
@require_http_methods(["GET"])
def download_randomised_paper_memo_pdf(request, paper_id: str):
    """Download memo as PDF"""
    paper = get_object_or_404(Paper, id=paper_id)
    
    try:
        paper_memo = paper.memo
        pdf_bytes = MemoGenerator.generate_pdf_memo(paper_memo)
        
        if not pdf_bytes:
            messages.error(request, "PDF generation not available")
            return redirect('randomised_paper_memo_crud', paper_id=paper_id)
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{paper.name}_memo.pdf"'
        return response
        
    except Exception as e:
        messages.error(request, f"PDF download failed: {str(e)}")
        return redirect('randomised_paper_memo_crud', paper_id=paper_id)


@login_required
@require_http_methods(["POST"])
def delete_randomised_paper(request, paper_id: str):
    """Delete a randomised paper and its memos"""
    paper = get_object_or_404(Paper, id=paper_id)
    
    # Ensure it's actually a randomised paper
    if not paper.parent_paper:
        return JsonResponse({
            'success': False,
            'message': 'Can only delete randomised papers'
        }, status=400)
    
    try:
        # Delete memo if exists
        if hasattr(paper, 'memo'):
            paper.memo.delete()
        
        paper_name = paper.name
        paper.delete()
        
        messages.success(request, f"Deleted randomised paper: {paper_name}")
        return redirect('randomised_papers_list')
        
    except Exception as e:
        messages.error(request, f"Delete failed: {str(e)}")
        return redirect('randomised_papers_list')
