import json
from io import BytesIO
from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages
from docx import Document

from core.models import (
    Assessment,
    CustomUser,
    ExamNode,
    Paper,
    PaperMemo,
    Qualification,
    QuestionMemo,
)


class RandomizedSnapshotEditingTests(TestCase):
    def setUp(self):
        self.qual = Qualification.objects.create(name="Qual", saqa_id="Q001")
        self.user = CustomUser.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="pass1234",
            role="admin",
        )
        self.paper = Paper.objects.create(
            name="Randomized Paper",
            qualification=self.qual,
            created_by=self.user,
            is_randomized=True,
        )
        self.assessment = Assessment.objects.create(
            eisa_id="EISA-0001",
            qualification=self.qual,
            paper=self.paper.name,
            module_number="A",
            module_name="Module A",
            paper_link=self.paper,
            paper_type="randomized",
            created_by=self.user,
        )
        self.node = ExamNode.objects.create(
            paper=self.paper,
            node_type="question",
            number="1",
            text="Original text value",
            marks="5",
            content=[{"type": "text", "text": "Original block"}],
            order_index=1,
        )
        self.url = reverse("assessor_randomized_snapshot", args=[self.assessment.id])
        self.client.force_login(self.user)

    def test_save_node_content_updates_examnode(self):
        payload = {
            "action": "save_node_content",
            "node_id": self.node.id,
            "node_number": "1.1",
            "node_marks": "8",
            "node_text": "Edited heading",
            "node_content_json": json.dumps(
                [{"type": "text", "text": "Edited body"}]
            ),
        }
        response = self.client.post(self.url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        self.node.refresh_from_db()
        self.assertEqual(self.node.number, "1.1")
        self.assertEqual(self.node.marks, "8")
        self.assertEqual(self.node.text, "Edited heading")
        self.assertEqual(self.node.content[0]["text"], "Edited body")

    def test_add_corresponding_memo_creates_questionmemo(self):
        payload = {
            "action": "add_corresponding_memo",
            "node_id": self.node.id,
            "memo_text": "Answer text",
            "memo_notes": "Note",
            "editor_mode": "paper",
        }
        response = self.client.post(self.url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        memo = QuestionMemo.objects.get(exam_node=self.node)
        self.assertEqual(memo.content, "Answer text")
        self.assertEqual(memo.notes, "Note")
        self.assertEqual(memo.question_number, "1")

    def test_memo_variant_download_has_custom_filename(self):
        paper_memo = PaperMemo.objects.create(paper=self.paper, created_by=self.user)
        QuestionMemo.objects.create(
            paper_memo=paper_memo,
            exam_node=self.node,
            question_number="1",
            content="Memo body",
            notes="memo note",
        )
        download_url = (
            reverse("download_randomized_pdf", args=[self.assessment.id])
            + "?format=docx&variant=memo"
        )
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("_memo.docx", response["Content-Disposition"])

    def test_add_corresponding_memo_in_memo_mode_preserves_node(self):
        original_text = self.node.text
        payload = {
            "action": "add_corresponding_memo",
            "node_id": self.node.id,
            "memo_text": "",
            "memo_notes": "auto flip",
            "node_text": original_text,
            "editor_mode": "memo",
        }
        response = self.client.post(self.url, payload, follow=True)
        self.assertEqual(response.status_code, 200)

        memo = QuestionMemo.objects.get(exam_node=self.node)
        self.assertEqual(memo.content, original_text)

        self.node.refresh_from_db()
        self.assertEqual(self.node.text, original_text)

    def test_missing_content_in_memo_mode_shows_helpful_message(self):
        self.node.text = ""
        self.node.content = []
        self.node.save(update_fields=["text", "content"])
        payload = {
            "action": "add_corresponding_memo",
            "node_id": self.node.id,
            "memo_text": "",
            "memo_notes": "",
            "node_text": "",
            "editor_mode": "memo",
        }
        response = self.client.post(self.url, payload, follow=True)
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any(
                "Add the memo text back into this block" in msg.message
                for msg in messages
            )
        )

    def test_memo_docx_contains_question_and_answer(self):
        paper_memo = PaperMemo.objects.create(paper=self.paper, created_by=self.user)
        QuestionMemo.objects.create(
            paper_memo=paper_memo,
            exam_node=self.node,
            question_number="1",
            content="Memo body text",
            notes="Important note",
        )
        url = (
            reverse("download_randomized_pdf", args=[self.assessment.id])
            + "?format=docx&variant=memo"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        doc = Document(BytesIO(response.content))
        combined = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("Question 1", combined)
        self.assertIn("Memo Answer:", combined)
        self.assertIn("Memo body text", combined)
