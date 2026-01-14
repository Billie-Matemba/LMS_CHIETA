from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.conf import settings
import logging
import random
from django.utils.html import mark_safe
import base64 
import uuid
from decimal import Decimal


logger = logging.getLogger(__name__)

#************************
# Qualification creation
#************************
class Qualification(models.Model):
    name = models.CharField(max_length=100, unique=True)
    saqa_id = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_module_choices_for_type(cls, qual_type):
        from . import qualification_registry

        modules = qualification_registry.get_module_choices(qual_type)
        if not modules:
            return []
        return [
            (m.get('code'), m.get('label') or m.get('code'))
            for m in modules
            if m.get('code')
        ]

    def clean(self):
        from . import qualification_registry

        entry = qualification_registry.find_entry(self.name)
        expected_saqa = entry.get('saqa_id') if entry else None
        if expected_saqa and self.saqa_id != expected_saqa:
            raise ValidationError(f"SAQA ID for {self.name} must be {expected_saqa}")

    def __str__(self):
        return f"{self.name} (SAQA: {self.saqa_id})"


#****************
# Custom User
#****************
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('default',         'Awaiting Activation'),
        ('admin',           'Administrator'),
        ('assessor_dev',    'Assessor (Developer)'),
        ('moderator',       'Moderator (Developer)'),
        ('qcto',            'QCTO Validator'),
        ('etqa',            'ETQA'),
        ('learner',         'Learner'),
        ('assessor_marker', 'Assessor (Marker)'),
        ('internal_mod',    'Internal Moderator'),
        ('external_mod',    'External Moderator (QALA)'),
        ('assessment_center', 'Assessment Center')
    ]

    role                     = models.CharField(max_length=30, choices=ROLE_CHOICES, default='admin')
    qualification            = models.ForeignKey(
                                  Qualification,
                                  on_delete=models.SET_NULL,
                                  null=True, blank=True,
                                  related_name='users'
                              )
    email                    = models.EmailField(unique=True)
        ###########################################
    student_number = models.CharField(
        max_length=50, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="Unique student number for learners"
    )
    ############################################

    ####################################################
    assessment_centre = models.ForeignKey(
        'AssessmentCentre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessment_users'
    )
    ####################################################
    objects                  = UserManager()
    created_at               = models.DateTimeField(auto_now_add=True)
    activated_at             = models.DateTimeField(default=now)
    deactivated_at           = models.DateTimeField(null=True, blank=True)
    qualification_updated_at = models.DateTimeField(null=True, blank=True)
    last_updated_at          = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username 
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if self.role == 'assessment_center' and self.assessment_centre:
            self.qualification = self.assessment_centre.qualification_assigned

        if self.pk:
            original = CustomUser.objects.get(pk=self.pk)
            if original.qualification != self.qualification:
                self.qualification_updated_at = now()
        else:
            self.qualification_updated_at = now()  # First-time save

        super().save(*args, **kwargs)


    class Meta:
        ordering = ['-created_at']


    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_role_display()})"

#************************
# Question bank entry
#************************
class QuestionBankEntry(models.Model):
    QUESTION_TYPE_CHOICES = [
        ("standard",   "Standard"),
        ("case_study", "Case Study"),
        ("mcq",        "Multiple Choice"),
    ]

    qualification  = models.ForeignKey(Qualification, on_delete=models.SET_NULL, null=True)
    question_type  = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default="standard")
    text           = models.TextField()
    marks          = models.PositiveIntegerField()
    case_study     = models.ForeignKey("CaseStudy", on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.text[:30]}…"


#****************
# MCQ options
#****************
# class MCQOption(models.Model):
#     question = models.ForeignKey(
#         QuestionBankEntry,
#         on_delete=models.CASCADE,
#         limit_choices_to={"question_type": "mcq"},
#         related_name="options"
#     )
#     text = models.CharField(max_length=255)
#     is_correct = models.BooleanField(default=False)

#     def __str__(self):
#         return f"{'✔' if self.is_correct else '✗'} {self.text}"


#*****************************************
# Assessment + Build-A-Paper & Randomization
#*****************************************
class Assessment(models.Model):
    PAPER_TYPE_CHOICES = [
        ('admin_upload', 'Admin Upload'),
        ('randomized', 'Randomized Paper')
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_moderation', 'Pending Moderation'),
        ('moderated', 'Moderated'),
        ('pending_etqa', 'Pending ETQA Review'),
        ('etqa_approved', 'ETQA Approved'),
        ('etqa_rejected', 'ETQA Rejected'),
        ('pending_qcto', 'Pending QCTO Review'),
        ('qcto_approved', 'QCTO Approved'),
        ('qcto_rejected', 'QCTO Rejected'),
        ("Released to students", "Released to students"),
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('QDD Review', 'QDD Review'),
        
    ]

    eisa_id = models.CharField(max_length=50)
    qualification = models.ForeignKey(Qualification, on_delete=models.SET_NULL, null=True)
    paper = models.CharField(max_length=50)
    paper_type = models.CharField(
        max_length=50,
        choices=PAPER_TYPE_CHOICES,
        default='admin_upload'
    )
    paper_link = models.ForeignKey(
        "Paper",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="assessments"
    )
    extractor_paper = models.OneToOneField(
        'ExtractorPaper',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assessment_record'
    )
    saqa_id = models.CharField(max_length=50, blank=True, null=True)
    moderator = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to="assessments/", blank=True, null=True)
    
    # Memo field for admin uploads
    memo = models.FileField(
        upload_to="assessments/memos/", 
        blank=True, 
        null=True,
        help_text="Memo file for admin-uploaded assessments"
    )
    
    comment = models.TextField(blank=True)
    forward_to_moderator = models.BooleanField(default=False)
    moderator_report = models.FileField(
        upload_to="moderator_reports/", 
        blank=True, 
        null=True,
        help_text="Word document report from moderator"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    qcto_report = models.FileField(
        upload_to="qcto_reports/", 
        blank=True, 
        null=True,
        help_text="Word document report from qcto"
    )
    
    # ETQA fields - only used for randomized papers
    is_selected_by_etqa = models.BooleanField(default=False)
    memo_file = models.FileField(
        upload_to='memos/randomized/', 
        null=True, 
        blank=True,
        help_text="Memo file for randomized assessments requiring ETQA approval"
    )
    etqa_approved = models.BooleanField(default=False)
    etqa_comments = models.TextField(blank=True)
    etqa_approved_date = models.DateTimeField(null=True, blank=True)

    # Add status tracking fields
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='draft'
    )
    status_changed_at = models.DateTimeField(auto_now_add=True)
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='status_changes'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assessments_created"
    )
    module_name = models.CharField(
        max_length=100,
        help_text="e.g. Chemical Operations",
        default="Unknown Module"
    )
    module_number = models.CharField(
        max_length=2,
        help_text="Module identifier (1A, 1B, etc)",
        default="1A"
    )

    def get_memo_path(self, filename):
        """Generate organized path for memo files"""
        safe_name = self.module_name.replace(' ', '_')
        return f'assessments/memos/{safe_name}/{self.module_number}/{filename}'

    def requires_etqa_approval(self):
        """Only randomized papers require ETQA approval"""
        return self.paper_type == 'randomized'

    def clean(self):
        """Validation to ensure correct memo field usage"""
        if self.paper_type == 'admin_upload':
            # Admin uploads should use the 'memo' field
            if self.memo_file:
                raise ValidationError({
                    'memo_file': 'For admin uploads, use the standard memo field'
                })
        else:
            # Randomized papers should use memo_file
            if self.memo:
                raise ValidationError({
                    'memo': 'For randomized papers, use the memo_file field'
                })

    def save(self, *args, **kwargs):
        self.clean()
        is_create = self._state.adding
        previous_status = None
        status_changed = False

        if not is_create and self.pk:
            previous_status = (
                Assessment.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            )
            if previous_status is not None and previous_status != self.status:
                status_changed = True

        # Remove the PDF renaming logic - let files keep their original names
        super().save(*args, **kwargs)

        if not is_create and status_changed:
            try:
                from core import automated_notifications

                automated_notifications.send_personalized_status_notifications(
                    status=self.status,
                    assessment_id=self.id,
                    qualification=self.qualification.name if self.qualification else None,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to dispatch workflow notification for assessment %s: %s",
                    self.id,
                    exc,
                )

    # — new M2M through-model fields —
    questions = models.ManyToManyField(
        'QuestionBankEntry',
        through='AssessmentQuestion',
        related_name='assessments'
    )
    questions_randomized = models.BooleanField(default=False)

    def randomize_questions(self):
        linked_qs = list(self.questions.all())
        if not linked_qs:
            return
        random.shuffle(linked_qs)
        for idx, q in enumerate(linked_qs, start=1):
            aq, _ = AssessmentQuestion.objects.get_or_create(
                assessment=self,
                question=q,
                defaults={'order': idx}
            )
            aq.order = idx
            aq.save(update_fields=['order'])
        self.questions_randomized = True
        self.save(update_fields=['questions_randomized'])

    def update_status(self, new_status, user):
        """Update assessment status with audit trail"""
        if new_status in dict(self.STATUS_CHOICES):
            self.status = new_status
            self.status_changed_at = now()
            self.status_changed_by = user
            self.save()

    def get_next_status(self):
        """Determine next status based on paper type and current status"""
        if self.paper_type == 'admin_upload':
            STATUS_FLOW = {
                'draft': 'pending_moderation',
                'pending_moderation': 'moderated',
                'moderated': 'pending_qcto',
                'pending_qcto': 'active'
            }
        else:  # randomized paper
            STATUS_FLOW = {
                'draft': 'pending_etqa',
                'pending_etqa': 'etqa_approved',
                'etqa_approved': 'pending_moderation',
                'pending_moderation': 'moderated',
                'moderated': 'pending_qcto',
                'pending_qcto': 'active'
            }
        return STATUS_FLOW.get(self.status)

    def can_transition_to(self, new_status, user):
        """Check if status transition is allowed for user role"""
        ALLOWED_TRANSITIONS = {
            'moderator': ['moderated', 'pending_moderation'],
            'etqa': ['etqa_approved', 'etqa_rejected'],
            'qcto': ['qcto_approved', 'qcto_rejected'],
            'admin': [s[0] for s in self.STATUS_CHOICES]
        }
        return new_status in ALLOWED_TRANSITIONS.get(user.role, [])

    class Meta:
        permissions = [
            ("can_moderate", "Can moderate assessments"),
            ("can_etqa_review", "Can review as ETQA"),
            ("can_qcto_review", "Can review as QCTO")
        ]

    def __str__(self):
        return f"{self.paper} - {self.qualification}"


class AssessmentStatusNotification(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='status_notifications'
    )
    status = models.CharField(max_length=120)
    notified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('assessment', 'status')
        ordering = ['-notified_at']

    def __str__(self):
        return f"{self.assessment_id} → {self.status} @ {self.notified_at:%Y-%m-%d %H:%M}"
class AssessmentQuestion(models.Model):
    """Through-model to store per-question content, marks, and order."""
    assessment   = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    question     = models.ForeignKey(QuestionBankEntry, on_delete=models.CASCADE)
    order        = models.PositiveIntegerField(default=0)
    marks        = models.PositiveIntegerField(default=0)
    content_html = models.TextField(
        blank=True,
        help_text="Paste question text, tables, images (HTML) here."
    )

    class Meta:
        unique_together = ('assessment', 'question')
        ordering = ['order']

    def rendered_content(self):
        return mark_safe(self.content_html)

class CaseStudy(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()

    def __str__(self):
        return self.title

class GeneratedQuestion(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        related_name='generated_questions',
        on_delete=models.CASCADE
    )
    text = models.TextField()
    marks = models.PositiveIntegerField()
    case_study = models.ForeignKey(
        CaseStudy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.text[:50]}… ({self.marks} marks)"



class MCQOption(models.Model):
    question = models.ForeignKey(
        QuestionBankEntry,
        on_delete=models.CASCADE,
        limit_choices_to={"question_type": "mcq"},
        related_name="options"
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{'✔' if self.is_correct else '✗'} {self.text}"

class ChecklistItem(models.Model):
    label = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.label



class AssessmentCentre(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255, blank=True)
    qualification_assigned = models.ForeignKey(Qualification, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name

# Batch model ___________________________________________________________________________________________#

class Batch(models.Model):
    center = models.ForeignKey('AssessmentCentre', on_delete=models.CASCADE)
    qualification = models.ForeignKey('Qualification', on_delete=models.CASCADE)
    assessment = models.ForeignKey('Assessment', on_delete=models.CASCADE)
    assessment_date = models.DateField()
    # number_of_learners = models.PositiveIntegerField()
    submitted_to_center = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Batch - {self.center.name} | {self.qualification.name} | {self.assessment.eisa_id}"

#students model -------------------------------------------------------------------
class ExamAnswer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey('GeneratedQuestion', on_delete=models.CASCADE)
    answer_text = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    attempt_number = models.PositiveSmallIntegerField(default=1)  # Track attempts

    class Meta:
        unique_together = ('user', 'question', 'attempt_number')  # Include attempts 
        verbose_name = 'Exam Answer'
        verbose_name_plural = 'Exam Answers'

    @property
    def assessment(self):
        """Quick access to the assessment through the question"""
        return self.question.assessment

    def __str__(self):
        return f"Answer by {self.user} for {self.question} (Attempt {self.attempt_number})"

# <-------------------------------------------Questions storage Models --------------------------------------------------->
# core/models.py
from django.db import models


class Paper(models.Model):
    """Exam paper with extracted structure"""
    id = models.CharField(max_length=40, primary_key=True, editable=False, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    qualification = models.ForeignKey(Qualification, on_delete=models.CASCADE, related_name='papers')
    total_marks = models.IntegerField(default=0)
    
    # Store full manifest as JSON for randomization
    structure_json = models.JSONField(default=dict, blank=True)
    is_randomized = models.BooleanField(default=False)
    
    # Parent paper (if this is randomised)
    parent_paper = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='randomised_variants'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Paper"
        verbose_name_plural = "Papers"
    
    def __str__(self):
        return self.name
    
    @property
    def question_count(self):
        return self.nodes.filter(node_type='question').count()


class ExamNode(models.Model):
    """A node in the paper structure (question, instruction, table, image, etc.)"""
    NODE_TYPES = [
        ('question', 'Question'),
        ('instruction', 'Instruction/Rubric'),
        ('table', 'Table'),
        ('image', 'Image/Figure'),
        ('pagebreak', 'Page Break'),
        ('case_study', 'Case Study'),
        ('paragraph', 'Paragraph'),
    ]
    
    id = models.CharField(max_length=40, primary_key=True, editable=False, default=uuid.uuid4)
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='nodes')
    
    # Question numbering (1, 1.1, 1.1.1, etc.)
    number = models.CharField(max_length=50, blank=True, default="", db_index=True)
    
    node_type = models.CharField(max_length=20, choices=NODE_TYPES, default='paragraph')
    marks = models.CharField(max_length=20, blank=True, default="")  # Can be "10" or range like "10-12"
    
    # Text content
    text = models.TextField(blank=True, default="", help_text="Plain text preview/summary")
    
    # Full content structure (paragraphs, tables, images, etc.)
    content = models.JSONField(default=list, blank=True)
    
    # Parent-child relationship (1.1 has parent 1)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Order in paper
    order_index = models.IntegerField(default=0, db_index=True)
    
    # Extraction metadata
    manifest_output_dir = models.CharField(max_length=500, blank=True, help_text="Path to extracted media")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['paper', 'order_index']
        verbose_name = "Exam Node"
        verbose_name_plural = "Exam Nodes"
    
    def __str__(self):
        return f"Q{self.number or '?'}" if self.node_type == 'question' else f"{self.node_type}"

    @property
    def marks_int(self):
        """Parse marks as integer"""
        if not self.marks:
            return 0
        try:
            return int(self.marks.split('-')[0])  # Take first number from range
        except:
            return 0

    def save(self, *args, **kwargs):
        if self.number is None:
            self.number = ""
        if self.marks is None:
            self.marks = ""
        super().save(*args, **kwargs)


class PaperMemo(models.Model):
    """Stores memo/answer key for entire paper"""
    id = models.CharField(max_length=40, primary_key=True, editable=False, default=uuid.uuid4)
    paper = models.OneToOneField(Paper, on_delete=models.CASCADE, related_name='memo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Paper Memo"
        verbose_name_plural = "Paper Memos"
    
    def __str__(self):
        return f"Memo for {self.paper.name}"


class QuestionMemo(models.Model):
    """Stores memo/answer for individual question"""
    id = models.CharField(max_length=40, primary_key=True, editable=False, default=uuid.uuid4)
    paper_memo = models.ForeignKey(PaperMemo, on_delete=models.CASCADE, related_name='questions')
    exam_node = models.OneToOneField(ExamNode, on_delete=models.CASCADE, related_name='memo')
    question_number = models.CharField(max_length=50, db_index=True)
    content = models.TextField(help_text="Memo/answer content")
    notes = models.TextField(blank=True, help_text="Additional notes/warnings")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Question Memo"
        ordering = ['question_number']
    
    def __str__(self):
        return f"Memo Q{self.question_number}"


# *****************************************
# Extraction tooling + submissions
# *****************************************
class RegexPattern(models.Model):
    """Stores regex patterns that successfully parsed past papers."""
    pattern = models.TextField()
    description = models.TextField(blank=True)
    match_score = models.FloatField(default=0)
    format_signature = models.CharField(max_length=100, blank=True)
    example_usage = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-match_score', '-created_at']

    def __str__(self):
        label = self.format_signature or "Regex Pattern"
        score = f"{self.match_score:.0%}" if self.match_score else "0%"
        return f"{label} ({score})"


class ExtractorPaper(models.Model):
    """Uploaded document that drives the advanced extractor workflow."""
    title = models.CharField(max_length=255, blank=True)
    original_file = models.FileField(upload_to='uploads/')
    created_at = models.DateTimeField(auto_now_add=True)
    system_prompt = models.TextField(blank=True, default='')
    module_name = models.CharField(max_length=255, blank=True, default='')
    paper_number = models.CharField(max_length=50, blank=True, default='')
    paper_letter = models.CharField(max_length=10, blank=True, default='')

    def __str__(self):
        return self.title or f"Extractor Paper {self.id}"


class ExtractorBlock(models.Model):
    """Low-level paragraph/table/image blocks captured from DOCX parsing."""
    BLOCK_TYPES = [
        ('paragraph', 'Paragraph'),
        ('table', 'Table'),
        ('image', 'Image'),
        ('heading', 'Heading'),
        ('instruction', 'Instruction'),
        ('rubric', 'Rubric'),
    ]

    paper = models.ForeignKey(ExtractorPaper, related_name='blocks', on_delete=models.CASCADE)
    order_index = models.IntegerField(default=0)
    block_type = models.CharField(max_length=20, choices=BLOCK_TYPES)
    xml = models.TextField(blank=True)
    text = models.TextField(blank=True)
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    w = models.FloatField(null=True, blank=True)
    h = models.FloatField(null=True, blank=True)
    is_qheader = models.BooleanField(default=False)
    detected_qnum = models.CharField(max_length=50, blank=True)
    detected_marks = models.CharField(max_length=50, blank=True)
    rand_order_index = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        label = self.get_block_type_display()
        return f"{label} #{self.order_index} ({self.paper_id})"


class ExtractorBlockImage(models.Model):
    """Images extracted from DOCX tables/paragraphs."""
    block = models.ForeignKey(ExtractorBlock, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='paper_images/')

    def __str__(self):
        return f"Image for block {self.block_id}"


class ExtractorTestPaper(models.Model):
    """Randomized paper that was generated from extractor content."""
    title = models.CharField(max_length=255, blank=True, default='')
    module_name = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or f"Randomized Test {self.id}"


class ExtractorTestItem(models.Model):
    """Individual question entry on a randomized test paper."""
    test = models.ForeignKey(ExtractorTestPaper, related_name='items', on_delete=models.CASCADE)
    order_index = models.IntegerField(default=0)
    question_number = models.CharField(max_length=50, blank=True)
    marks = models.CharField(max_length=50, blank=True)
    qtype = models.CharField(max_length=50, blank=True)
    content_type = models.CharField(max_length=50, blank=True)
    content = models.TextField(blank=True)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.question_number or 'Q'} on {self.test_id}"


class ExtractorUserBox(models.Model):
    """User-curated bounding boxes used for question banking."""
    paper = models.ForeignKey(ExtractorPaper, related_name='user_boxes', on_delete=models.CASCADE)
    x = models.FloatField()
    y = models.FloatField()
    w = models.FloatField()
    h = models.FloatField()
    order_index = models.IntegerField(default=0)
    question_number = models.CharField(max_length=50, blank=True)
    marks = models.CharField(max_length=50, blank=True)
    qtype = models.CharField(max_length=50, blank=True)
    parent_number = models.CharField(max_length=50, blank=True)
    header_label = models.CharField(max_length=255, blank=True)
    case_study_label = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    content_type = models.CharField(max_length=50, blank=True)
    content = models.TextField(blank=True)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.question_number or 'Box'} on paper {self.paper_id}"


class OfflineStudent(models.Model):
    """Learners captured by assessment centres when offline."""
    STATUS_PRESENT = 'present'
    STATUS_ABSENT = 'absent'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_ABSENT, 'Absent'),
    ]

    student_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PRESENT)
    qualification = models.ForeignKey(Qualification, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='offline_students_created'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student_number} - {self.first_name} {self.last_name}"


class PaperBankEntry(models.Model):
    """Original assessment uploads that feed the administrator paper bank."""
    assessment = models.OneToOneField(
        Assessment,
        related_name='paper_bank_entry',
        on_delete=models.CASCADE
    )
    original_file = models.FileField(upload_to='paper_bank/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paper bank entry for {self.assessment.eisa_id}"


class Feedback(models.Model):
    """Simple feedback trail tied to an assessment workflow."""
    STATUS_PENDING = 'Pending'
    STATUS_REVISED = 'Revised'
    STATUS_COMPLETED = 'Completed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REVISED, 'Revised'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    assessment = models.ForeignKey(
        Assessment,
        related_name='feedbacks',
        on_delete=models.CASCADE
    )
    to_user = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"Feedback for {self.assessment.eisa_id} -> {self.to_user}"


class GlobalBusinessRecord(models.Model):
    """Custom dataset rows uploaded for the Global Business dashboard."""

    school = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    continent = models.CharField(max_length=100, blank=True)
    learners = models.PositiveIntegerField(default=0)
    submissions = models.PositiveIntegerField(default=0)
    pass_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    average_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['school']

    def __str__(self):
        return self.school


class ExamSubmission(models.Model):
    """Stores PDF uploads and grading metadata for both online/offline learners."""
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    offline_student = models.ForeignKey(
        OfflineStudent,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    assessment = models.ForeignKey(
        Assessment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    paper = models.ForeignKey(
        Paper,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    student_number = models.CharField(max_length=50)
    student_name = models.CharField(max_length=100)
    attempt_number = models.IntegerField()
    pdf_file = models.FileField(upload_to='exam_submissions/%Y/%m/%d/')
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_offline = models.BooleanField(default=False)

    marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    marked_paper = models.FileField(
        upload_to='marked_papers/marker/%Y/%m/%d/',
        null=True,
        blank=True
    )
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='graded_submissions',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    internal_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    internal_total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    internal_graded_at = models.DateTimeField(null=True, blank=True)
    internal_feedback = models.TextField(blank=True)
    internal_marked_paper = models.FileField(
        upload_to='marked_papers/internal/%Y/%m/%d/',
        null=True,
        blank=True
    )
    internal_graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='internal_graded_submissions',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    external_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    external_total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('100.00'))
    external_graded_at = models.DateTimeField(null=True, blank=True)
    external_feedback = models.TextField(blank=True)
    external_marked_paper = models.FileField(
        upload_to='marked_papers/external/%Y/%m/%d/',
        null=True,
        blank=True
    )
    external_graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='external_graded_submissions',
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student_number} - Attempt {self.attempt_number}"

    def save(self, *args, **kwargs):
        """Ensure student details are always populated from related records."""
        if self.offline_student:
            self.student_number = self.offline_student.student_number
            full_name = f"{self.offline_student.first_name} {self.offline_student.last_name}".strip()
            self.student_name = full_name or self.offline_student.student_number
        elif self.student:
            self.student_number = self.student_number or getattr(self.student, "student_number", "") or self.student.email
            full_name = f"{self.student.first_name} {self.student.last_name}".strip()
            self.student_name = self.student_name or full_name or self.student.email
        super().save(*args, **kwargs)

    @property
    def status(self):
        if self.external_marks is not None:
            return "Finalized"
        if self.internal_marks is not None:
            return "Reviewed"
        if self.marks is not None:
            return "Graded by Marker"
        return "Pending"

    @property
    def student_display(self):
        return self.student_name or self.student_number
