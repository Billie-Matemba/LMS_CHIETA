from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.timezone import localtime, now

from core.models import Assessment, CustomUser


STATUS_TEMPLATES = {
    'Submitted to Moderator': {
        'subject': 'Assessment Submitted for Moderation',
        'personal_subject': 'Assessment Pending Your Review',
        'message': 'An assessment has been submitted and is awaiting your moderation review.',
        'recipient_roles': ['moderator'],
    },
    'Submitted to QCTO': {
        'subject': 'Assessment Submitted for QCTO Review',
        'personal_subject': 'Assessment Awaiting QCTO Review',
        'message': 'An assessment has been approved by moderator and is now awaiting QCTO review.',
        'recipient_roles': ['qcto'],
    },
    'Submitted to ETQA': {
        'subject': 'Assessment Submitted for ETQA Approval',
        'personal_subject': 'Assessment Awaiting ETQA Approval',
        'message': 'An assessment has been approved and is now awaiting ETQA final approval.',
        'recipient_roles': ['etqa'],
    },
    'Returned for Changes': {
        'subject': 'Assessment Returned for Changes',
        'personal_subject': 'Please Address Assessment Feedback',
        'message': 'The moderator has returned your assessment for further changes and improvements.',
        'recipient_roles': ['assessor_dev'],
    },
    'Approved by Moderator': {
        'subject': 'Assessment Approved by Moderator',
        'personal_subject': 'Assessment Approved - Next Step',
        'message': 'Your assessment has been approved by the moderator and is proceeding to QCTO.',
        'recipient_roles': ['assessor_dev', 'admin'],
    },
    'Approved by ETQA': {
        'subject': 'Assessment Approved by ETQA',
        'personal_subject': 'Assessment Fully Approved',
        'message': 'Your assessment has received final approval from ETQA and is now approved.',
        'recipient_roles': ['assessor_dev', 'qcto', 'admin'],
    },
    'Released to students': {
        'subject': 'Assessment Released to Learners',
        'personal_subject': 'Assessment Now Live for Learners',
        'message': 'The assessment is now available for learners to attempt.',
        'recipient_roles': ['assessor_dev', 'assessment_center', 'admin'],
    },
    'Rejected': {
        'subject': 'Assessment Rejected',
        'personal_subject': 'Assessment Requires Resubmission',
        'message': 'Your assessment has been rejected. Please review feedback and resubmit.',
        'recipient_roles': ['assessor_dev', 'admin'],
    },
}


def _roles_for_status(status: str):
    template = STATUS_TEMPLATES.get(status) or {}
    return template.get('recipient_roles', [])


def build_user_notifications(user, limit=25, qualification=None):
    """
    Build a summarized notification payload for the UI.
    Filters assessments by status + qualification + user role.
    """
    notifications = []
    filters = {'qualifications': [], 'statuses': []}

    if not getattr(user, 'is_authenticated', False):
        return notifications, filters

    relevant_statuses = [
        status for status, template in STATUS_TEMPLATES.items()
        if user.role in template.get('recipient_roles', [])
    ]
    if not relevant_statuses:
        return notifications, filters

    # Resolve qualification filter
    qualification_id = None
    qualification_name = None
    if qualification is not None:
        if hasattr(qualification, 'pk'):
            qualification_id = qualification.pk
        elif isinstance(qualification, int):
            qualification_id = qualification
        elif isinstance(qualification, str):
            qualification_name = qualification
    elif getattr(user, 'qualification_id', None):
        qualification_id = user.qualification_id

    qs = (
        Assessment.objects.select_related('qualification', 'status_changed_by', 'created_by')
        .filter(status__in=relevant_statuses)
        .order_by('-status_changed_at', '-created_at')
    )
    if qualification_id:
        qs = qs.filter(qualification_id=qualification_id)
    elif qualification_name:
        qs = qs.filter(qualification__name__icontains=qualification_name)

    if limit:
        qs = qs[:limit]

    qualification_map = {}
    status_map = {}

    for assessment in qs:
        ts = assessment.status_changed_at or assessment.created_at
        ts_local = localtime(ts) if ts else None
        qual_name = assessment.qualification.name if assessment.qualification else "Unassigned"
        qual_key = assessment.qualification_id or 0
        qualification_map[qual_key] = qual_name
        status_label = assessment.get_status_display() if hasattr(assessment, "get_status_display") else assessment.status
        status_map[assessment.status] = status_label

        notifications.append({
            'assessment_id': assessment.id,
            'eisa_id': assessment.eisa_id,
            'paper': assessment.paper,
            'status': assessment.status,
            'status_display': status_label or assessment.status,
            'status_slug': slugify(assessment.status) or 'status',
            'qualification': qual_name,
            'qualification_id': assessment.qualification_id or 0,
            'qualification_matches': bool(
                user.qualification_id and assessment.qualification_id == user.qualification_id
            ),
            'timestamp': ts_local,
            'timestamp_iso': ts_local.isoformat() if ts_local else '',
            'recipient_name': getattr(user, 'name', getattr(user, 'username', '')),
            'updated_by': getattr(assessment.status_changed_by, 'name', None)
                           or getattr(assessment.status_changed_by, 'username', 'System'),
            'updated_by_role': (
                assessment.status_changed_by.get_role_display()
                if assessment.status_changed_by and hasattr(assessment.status_changed_by, 'get_role_display')
                else ''
            ),
            'message': STATUS_TEMPLATES.get(assessment.status, {}).get('message', ''),
        })

    filters['qualifications'] = [
        {'id': key, 'name': name} for key, name in sorted(qualification_map.items(), key=lambda item: item[1])
    ]
    filters['statuses'] = [
        {'value': key, 'label': label} for key, label in sorted(status_map.items(), key=lambda item: item[1])
    ]
    return notifications, filters


def send_status_notifications(status, assessment_id=None, role=None, qualification=None):
    """
    Auto-send emails to users filtered by role, qualification, and triggered by assessment status.
    """
    email_template = STATUS_TEMPLATES.get(status)
    if not email_template:
        print(f"No email template found for status: {status}")
        return False

    recipient_roles = email_template.get('recipient_roles', [])
    if role:
        recipient_roles = [role]

    query_filter = {'role__in': recipient_roles}
    if qualification:
        query_filter['qualification__name__icontains'] = qualification

    users = CustomUser.objects.filter(**query_filter).exclude(is_superuser=True)
    if not users.exists():
        print(f"No users found with roles: {recipient_roles}")
        return False

    assessment_info = ""
    if assessment_id:
        try:
            assessment = Assessment.objects.get(id=assessment_id)
            assessment_info = (
                f"\n\nAssessment: {assessment.paper}"
                f"\nEISA ID: {assessment.eisa_id}"
                f"\nQualification: {assessment.qualification.name if assessment.qualification else 'N/A'}"
            )
        except Assessment.DoesNotExist:
            assessment = None

    email_list = [user.email for user in users if user.email]
    if not email_list:
        print("No valid email addresses found")
        return False

    full_message = email_template['message'] + assessment_info + "\n\nPlease log in to the LMS for more details."

    try:
        send_mail(
            subject=email_template['subject'],
            message=full_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=email_list,
            fail_silently=False,
        )
        print(f"Status notification emails sent to {len(email_list)} users for status: {status}")
        return True
    except Exception as e:
        print(f"Error sending status notification emails: {str(e)}")
        return False


def send_personalized_status_notifications(status, assessment_id=None, role=None, qualification=None):
    """
    Send personalized emails to users with template rendering.
    """
    recipient_roles = _roles_for_status(status)
    if role:
        recipient_roles = [role]

    if not recipient_roles:
        return False

    query_filter = {'role__in': recipient_roles}
    if qualification:
        query_filter['qualification__name__icontains'] = qualification

    users = CustomUser.objects.filter(**query_filter).exclude(is_superuser=True)
    if not users.exists():
        return False

    assessment = None
    if assessment_id:
        try:
            assessment = Assessment.objects.get(id=assessment_id)
        except Assessment.DoesNotExist:
            pass

    template_meta = STATUS_TEMPLATES.get(status, {})

    for user in users:
        context = {
            'user': user,
            'status': status,
            'assessment': assessment,
            'qualification': qualification,
            'timestamp': now(),
        }
        try:
            html_message = render_to_string('emails/status_notification.html', context)
            plain_message = strip_tags(html_message)
            subject = template_meta.get('personal_subject') or template_meta.get('subject') or f'Assessment Status Update: {status}'
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            print(f"Error sending email to {user.email}: {str(e)}")

    return True
