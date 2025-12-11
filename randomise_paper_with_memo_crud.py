"""
Randomise Paper with Memo CRUD
Handles:
  • Extracting memo data from form submission
  • Creating/updating PaperMemo and QuestionMemo records
  • Randomising questions while preserving memo associations
  • Generating memo PDFs and HTML views
"""

import json
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.models import Paper, ExamNode, PaperMemo, QuestionMemo, Qualification
from robustexamextractor import randomize_nodes, Extractor

# =============================================================================
# MODELS (Add to your models.py if not already present)
# =============================================================================
# These models should be added to core/models.py:

# class PaperMemo(models.Model):
#     """Stores memo/answer key for entire paper"""
#     id = models.CharField(max_length=40, primary_key=True, editable=False, default=uuid.uuid4)
#     paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='memo')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
#     
#     class Meta:
#         verbose_name = "Paper Memo"
#         verbose_name_plural = "Paper Memos"
#     
#     def __str__(self):
#         return f"Memo for {self.paper.name}"

# class QuestionMemo(models.Model):
#     """Stores memo/answer for individual question"""
#     id = models.CharField(max_length=40, primary_key=True, editable=False, default=uuid.uuid4)
#     paper_memo = models.ForeignKey(PaperMemo, on_delete=models.CASCADE, related_name='questions')
#     exam_node = models.OneToOneField(ExamNode, on_delete=models.CASCADE, related_name='memo')
#     question_number = models.CharField(max_length=50)
#     content = models.TextField(help_text="Memo/answer content")
#     notes = models.TextField(blank=True, help_text="Additional notes/warnings")
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     
#     class Meta:
#         verbose_name = "Question Memo"
#         ordering = ['question_number']
#     
#     def __str__(self):
#         return f"Memo Q{self.question_number}"

# =============================================================================
# CRUD Operations
# =============================================================================

class MemoManager:
    """Manages memo creation, updating, and retrieval"""
    
    @staticmethod
    def parse_memo_data(memo_json_str: str) -> Dict[str, Dict[str, str]]:
        """
        Parse memo data from form submission
        Returns: { questionId: { 'content': '...', 'notes': '...' } }
        """
        try:
            return json.loads(memo_json_str or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}
    
    @staticmethod
    @transaction.atomic
    def create_or_update_paper_memo(
        paper: Paper,
        memo_data: Dict[str, Dict[str, str]],
        user=None
    ) -> 'PaperMemo':
        """
        Create or update PaperMemo with associated QuestionMemos
        
        Args:
            paper: Paper instance
            memo_data: { questionId: { 'content': '...', 'notes': '...' } }
            user: User creating the memo
            
        Returns:
            PaperMemo instance
        """
        # Get or create PaperMemo
        paper_memo, created = PaperMemo.objects.get_or_create(
            paper=paper,
            defaults={'created_by': user}
        )
        
        # Update memo for each question
        for exam_node_id, memo_content in memo_data.items():
            try:
                exam_node = ExamNode.objects.get(id=exam_node_id)
                
                QuestionMemo.objects.update_or_create(
                    paper_memo=paper_memo,
                    exam_node=exam_node,
                    defaults={
                        'question_number': exam_node.number,
                        'content': memo_content.get('content', ''),
                        'notes': memo_content.get('notes', '')
                    }
                )
                print(f"✅ Saved memo for Q{exam_node.number}")
                
            except ExamNode.DoesNotExist:
                print(f"⚠️ ExamNode {exam_node_id} not found")
                continue
        
        return paper_memo
    
    @staticmethod
    def get_paper_memo(paper: Paper) -> Optional['PaperMemo']:
        """Retrieve memo for paper"""
        try:
            return paper.memo
        except:
            return None
    
    @staticmethod
    def get_question_memo(exam_node: ExamNode) -> Optional['QuestionMemo']:
        """Retrieve memo for specific question"""
        try:
            return exam_node.memo
        except:
            return None
    
    @staticmethod
    def delete_paper_memo(paper: Paper) -> bool:
        """Delete memo for paper and all associated question memos"""
        try:
            if hasattr(paper, 'memo'):
                paper.memo.delete()
                print(f"✅ Deleted memo for {paper.name}")
                return True
            return False
        except Exception as e:
            print(f"❌ Error deleting memo: {e}")
            return False


# =============================================================================
# Randomisation with Memo
# =============================================================================

class MemoRandomiser:
    """Handles paper randomisation while preserving memo associations"""
    
    def __init__(self, paper: Paper, bank_papers: List[Paper], user=None):
        self.paper = paper
        self.bank_papers = bank_papers
        self.user = user
        self.extracted_memo_dir = None
    
    def randomise_with_memo(
        self,
        memo_data: Dict[str, Dict[str, str]],
        same_top_level: bool = False,
        marks_tolerance: Optional[int] = None,
        required_tags: Optional[List[str]] = None,
        output_dir: Optional[str] = None
    ) -> Tuple[Paper, 'PaperMemo']:
        """
        Randomise paper questions while maintaining memo associations
        
        Returns:
            (randomised_paper, paper_memo) tuple
        """
        # Save memos first
        print("📝 Saving memos...")
        paper_memo = MemoManager.create_or_update_paper_memo(
            self.paper,
            memo_data,
            user=self.user
        )
        
        # Prepare bank manifests
        print("🏦 Preparing question bank...")
        bank_manifests = self._prepare_bank_manifests()
        
        # Get current paper manifest
        current_manifest = self._get_paper_manifest()
        
        # Randomise using robustexamextractor
        print("🔀 Randomising questions...")
        extractor = Extractor()
        media_dir = output_dir or self.paper.media_dir or 'media'
        
        randomised_manifest = randomize_nodes(
            current_manifest,
            bank_manifests,
            media_dir,
            require_same_top=same_top_level,
            marks_tolerance=marks_tolerance,
            required_tags=required_tags
        )
        
        # Create new randomised paper record
        print("💾 Creating randomised paper record...")
        randomised_paper = self._create_randomised_paper(
            randomised_manifest,
            original_memo=paper_memo
        )
        
        print(f"✅ Randomisation complete: {randomised_paper.name}")
        return randomised_paper, paper_memo
    
    def _prepare_bank_manifests(self) -> List[Dict[str, Any]]:
        """Convert bank papers to manifests for randomizer"""
        manifests = []
        
        for bank_paper in self.bank_papers:
            try:
                # Reconstruct manifest from stored structure_json
                manifest = json.loads(bank_paper.structure_json or '{}')
                if manifest:
                    manifest['source'] = bank_paper.name
                    manifests.append(manifest)
            except (json.JSONDecodeError, AttributeError):
                print(f"⚠️ Could not load manifest for {bank_paper.name}")
                continue
        
        print(f"📊 Loaded {len(manifests)} papers from bank")
        return manifests
    
    def _get_paper_manifest(self) -> Dict[str, Any]:
        """Get current paper's manifest"""
        try:
            manifest = json.loads(self.paper.structure_json or '{}')
            if not manifest:
                raise ValueError("Empty manifest")
            return manifest
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ Could not load paper manifest: {e}")
            raise
    
    def _create_randomised_paper(
        self,
        manifest: Dict[str, Any],
        original_memo: 'PaperMemo' = None
    ) -> Paper:
        """Create new Paper record from randomised manifest"""
        
        # Generate unique name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"{self.paper.name}_randomised_{timestamp}"
        
        # Calculate total marks
        total_marks = sum(
            (node.get('marks') or 0)
            for node in manifest.get('nodes', [])
            if node.get('type') == 'question'
        )
        
        # Create paper
        randomised_paper = Paper.objects.create(
            name=name,
            qualification=self.paper.qualification,
            total_marks=total_marks,
            structure_json=json.dumps(manifest, ensure_ascii=False),
            is_randomized=True,
            parent_paper=self.paper,  # Link to original
            created_by=self.user
        )
        
        # Create nodes from manifest
        node_map = {}
        for order, node_data in enumerate(manifest.get('nodes', [])):
            exam_node = ExamNode.objects.create(
                id=uuid.uuid4().hex,
                paper=randomised_paper,
                node_type=node_data.get('type', 'paragraph'),
                number=node_data.get('number', ''),
                marks=str(node_data.get('marks', '') or ''),
                text=node_data.get('text', ''),
                content=json.dumps(node_data.get('content', []), ensure_ascii=False),
                order_index=order
            )
            if exam_node.number:
                node_map[exam_node.number] = exam_node
        
        # Set parent-child relationships
        for number, node in node_map.items():
            if '.' in number:
                parent_number = '.'.join(number.split('.')[:-1])
                if parent_number in node_map:
                    node.parent = node_map[parent_number]
                    node.save()
        
        # Copy memos if original had them
        if original_memo:
            self._copy_memo_to_randomised(original_memo, randomised_paper, node_map)
        
        return randomised_paper
    
    def _copy_memo_to_randomised(
        self,
        original_memo: 'PaperMemo',
        randomised_paper: Paper,
        node_map: Dict[str, ExamNode]
    ):
        """Copy memo from original to randomised paper"""
        
        new_paper_memo = PaperMemo.objects.create(
            paper=randomised_paper,
            created_by=original_memo.created_by
        )
        
        for q_memo in original_memo.questions.all():
            # Find corresponding node in randomised paper by question number
            new_node = node_map.get(q_memo.question_number)
            if new_node:
                QuestionMemo.objects.create(
                    paper_memo=new_paper_memo,
                    exam_node=new_node,
                    question_number=q_memo.question_number,
                    content=q_memo.content,
                    notes=q_memo.notes
                )
                print(f"📋 Copied memo for Q{q_memo.question_number}")
        
        print(f"✅ Memos copied to randomised paper")


# =============================================================================
# Memo Generation (HTML/PDF)
# =============================================================================

class MemoGenerator:
    """Generate HTML/PDF views of memos"""
    
    @staticmethod
    def generate_html_memo(paper_memo: 'PaperMemo') -> str:
        """Generate HTML version of memo"""
        
        html_parts = [
            f"<html><head><meta charset='utf-8'>",
            f"<title>Memo — {paper_memo.paper.name}</title>",
            f"<style>",
            f"  body {{ font-family: 'Segoe UI', sans-serif; margin: 2cm; line-height: 1.6; }}",
            f"  h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}",
            f"  .question {{ page-break-inside: avoid; margin: 2rem 0; padding: 1rem; background: #ecf0f1; border-left: 4px solid #3498db; }}",
            f"  .q-number {{ font-weight: bold; color: #2980b9; font-size: 1.2rem; }}",
            f"  .q-content {{ margin-top: 0.5rem; white-space: pre-wrap; }}",
            f"  .memo-content {{ background: white; padding: 1rem; margin-top: 0.5rem; border: 1px solid #bdc3c7; }}",
            f"  .q-notes {{ background: #fff3cd; padding: 0.5rem; margin-top: 0.5rem; border-left: 3px solid #ffc107; font-size: 0.9rem; }}",
            f"  .meta {{ color: #7f8c8d; font-size: 0.9rem; margin-top: 2rem; border-top: 1px solid #bdc3c7; padding-top: 1rem; }}",
            f"</style>",
            f"</head><body>",
            f"<h1>📋 Answer Memo — {paper_memo.paper.name}</h1>",
        ]
        
        # Paper info
        html_parts.append(f"<div class='meta'>")
        html_parts.append(f"<strong>Total Marks:</strong> {paper_memo.paper.total_marks}<br>")
        html_parts.append(f"<strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>")
        html_parts.append(f"</div>")
        
        # Questions
        for q_memo in paper_memo.questions.all():
            html_parts.append(f"<div class='question'>")
            html_parts.append(f"<div class='q-number'>Question {q_memo.question_number}</div>")
            
            # Original question preview
            if q_memo.exam_node:
                preview_text = q_memo.exam_node.text[:200] or 'No question text'
                html_parts.append(f"<small style='color: #7f8c8d;'>{preview_text}...</small>")
            
            # Memo content
            html_parts.append(f"<div class='memo-content'>")
            html_parts.append(f"<strong>Answer/Memo:</strong><br>")
            html_parts.append(f"<div class='q-content'>{q_memo.content}</div>")
            html_parts.append(f"</div>")
            
            # Notes
            if q_memo.notes:
                html_parts.append(f"<div class='q-notes'>")
                html_parts.append(f"<strong>📌 Notes:</strong> {q_memo.notes}")
                html_parts.append(f"</div>")
            
            html_parts.append(f"</div>")
        
        html_parts.append(f"</body></html>")
        return '\n'.join(html_parts)
    
    @staticmethod
    def generate_pdf_memo(paper_memo: 'PaperMemo') -> bytes:
        """Generate PDF version of memo (requires weasyprint)"""
        try:
            from weasyprint import HTML, CSS
            import io
            
            html_content = MemoGenerator.generate_html_memo(paper_memo)
            pdf_file = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_file)
            return pdf_file.getvalue()
        
        except ImportError:
            print("⚠️ weasyprint not installed. Install with: pip install weasyprint")
            return None
        except Exception as e:
            print(f"❌ PDF generation failed: {e}")
            return None


# =============================================================================
# Helper Functions
# =============================================================================

def process_randomisation_form(request, paper_id: str, qualification_id: str) -> Tuple[Paper, 'PaperMemo', str]:
    """
    Process form submission and return randomised paper + memo
    
    Usage in view:
        randomised_paper, paper_memo, message = process_randomisation_form(
            request, paper_id, qualification_id
        )
    """
    
    paper = get_object_or_404(Paper, id=paper_id)
    qualification = get_object_or_404(Qualification, id=qualification_id)
    
    # Parse form data
    memo_json = request.POST.get('memo_data', '{}')
    memo_data = MemoManager.parse_memo_data(memo_json)
    
    same_top = request.POST.get('same_top_level') == 'true'
    marks_tol = request.POST.get('marks_tolerance')
    marks_tolerance = int(marks_tol) if marks_tol and marks_tol.isdigit() else None
    
    required_tags_str = request.POST.get('required_tags', '')
    required_tags = [t.strip() for t in required_tags_str.split(',') if t.strip()]
    
    # Get bank papers
    bank_papers = Paper.objects.filter(qualification=qualification).exclude(id=paper.id)[:10]
    
    # Randomise
    randomiser = MemoRandomiser(paper, bank_papers, user=request.user)
    randomised_paper, paper_memo = randomiser.randomise_with_memo(
        memo_data=memo_data,
        same_top_level=same_top,
        marks_tolerance=marks_tolerance,
        required_tags=required_tags
    )
    
    message = f"✅ Created randomised paper: {randomised_paper.name} with {len(memo_data)} memos"
    
    return randomised_paper, paper_memo, message
