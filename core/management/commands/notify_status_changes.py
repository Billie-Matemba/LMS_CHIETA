from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core import automated_notifications
from core.models import Assessment, AssessmentStatusNotification


class Command(BaseCommand):
    help = "Pull recent assessment status changes and send notification emails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookback",
            type=int,
            default=60,
            help="Minutes to look back for status changes (ignored when --all is set).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Ignore lookback window and evaluate all assessments.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which notifications would be sent without dispatching emails.",
        )

    def handle(self, *args, **options):
        lookback = options["lookback"]
        include_all = options["all"]
        dry_run = options["dry_run"]

        if include_all:
            assessments = Assessment.objects.exclude(status__isnull=True).exclude(status="").select_related(
                "qualification"
            )
        else:
            cutoff = timezone.now() - timedelta(minutes=lookback)
            assessments = (
                Assessment.objects.filter(status_changed_at__gte=cutoff)
                .exclude(status__isnull=True)
                .exclude(status="")
                .select_related("qualification")
            )

        base_url = getattr(settings, "SITE_URL", "").rstrip("/")

        processed = 0
        dispatched = 0
        skipped_existing = 0

        for assessment in assessments:
            processed += 1
            current_status = assessment.status
            if AssessmentStatusNotification.objects.filter(
                assessment=assessment, status=current_status
            ).exists():
                skipped_existing += 1
                continue

            partial = self._render_partial(assessment, current_status, base_url)
            extra_context = {"partial_html": partial} if partial else None

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Would notify {current_status} for assessment {assessment.id}"
                )
                continue

            ok = automated_notifications.send_personalized_status_notifications(
                status=current_status,
                assessment_id=assessment.id,
                qualification=assessment.qualification.name if assessment.qualification else None,
                extra_context=extra_context,
            )

            if ok:
                AssessmentStatusNotification.objects.create(
                    assessment=assessment,
                    status=current_status,
                )
                dispatched += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Sent notification for assessment {assessment.id} status '{current_status}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Failed to send notification for assessment {assessment.id} status '{current_status}'"
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete. Evaluated {processed} assessments, skipped {skipped_existing} already logged."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {processed} assessments | dispatched {dispatched} | skipped {skipped_existing} already notified."
                )
            )

    def _render_partial(self, assessment, status, base_url):
        try:
            link = None
            if base_url and assessment.paper_type == "randomized":
                path = reverse("assessor_randomized_snapshot", args=[assessment.id])
                link = f"{base_url}{path}"
            elif base_url:
                path = reverse("assessment_center")
                link = f"{base_url}{path}"
        except NoReverseMatch:
            link = None

        context = {
            "assessment": assessment,
            "status": status,
            "assessment_link": link,
        }
        return render_to_string("emails/partials/assessment_status_block.html", context)
