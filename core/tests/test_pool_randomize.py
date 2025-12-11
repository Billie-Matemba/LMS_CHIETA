from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import (
    Qualification,
    ExtractorPaper,
    ExtractorUserBox,
    Paper,
)


class PoolRandomizeViewTests(TestCase):
    """Ensure randomize endpoint can run entirely off captured boxes without a base paper."""

    def setUp(self):
        self.qual, _ = Qualification.objects.get_or_create(
            name="Maintenance Planner", defaults={"saqa_id": "QP123"}
        )
        self.user = get_user_model().objects.create_user(
            email="tester@example.com",
            password="testpass123",
            username="tester",
            role="assessor_dev",
            qualification=self.qual,
        )
        self.client.force_login(self.user)
        self.extractor = ExtractorPaper.objects.create(
            title="Maintenance Planner A",
            module_name=self.qual.name,
            paper_letter="A",
        )
        # Seed two question boxes to satisfy the pool-only builder
        ExtractorUserBox.objects.create(
            paper=self.extractor,
            x=0,
            y=0,
            w=1,
            h=1,
            order_index=1,
            question_number="1.1.1",
            qtype="question",
            content="{}",
        )
        ExtractorUserBox.objects.create(
            paper=self.extractor,
            x=0,
            y=0,
            w=1,
            h=1,
            order_index=2,
            question_number="2.1.1",
            qtype="question",
            content="{}",
        )

    def test_randomize_base_mode_without_existing_paper(self):
        """POSTing base mode works even when no stored base paper exists."""
        url = reverse("assessor_pool_randomize")
        resp = self.client.post(
            url,
            {
                "module": self.qual.name,
                "letter": "A",
                "mode": "base",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(Paper.objects.filter(is_randomized=True).count(), 1)
