from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from review.models import Flag
from review.services import create_flag, decide_flag


class AuthRequiredTests(TestCase):
    def test_queue_redirects_anonymous_user_to_login(self):
        resp = self.client.get(reverse("queue"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp.url)

    def test_decide_redirects_anonymous_user_to_login(self):
        flag = create_flag("txn-1", card1="1", amount="1.00", score=0.9, threshold=0.5)
        resp = self.client.post(reverse("decide", args=[flag.id]), {"decision": "approve"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("login"), resp.url)
        flag.refresh_from_db()
        self.assertEqual(flag.status, Flag.Status.PENDING)  # nothing happened


class QueueViewTests(TestCase):
    def setUp(self):
        self.analyst = User.objects.create_user("analyst1", password="x")
        self.client.force_login(self.analyst)

    def test_queue_lists_only_pending_flags(self):
        pending = create_flag("txn-pending", card1="1", amount="1.00", score=0.9, threshold=0.5)
        decided = create_flag("txn-decided", card1="2", amount="2.00", score=0.9, threshold=0.5)
        decide_flag(decided, approve=True, actor=self.analyst)

        resp = self.client.get(reverse("queue"))

        flags_shown = list(resp.context["flags"])
        self.assertIn(pending, flags_shown)
        self.assertNotIn(decided, flags_shown)


class DecideViewTests(TestCase):
    def setUp(self):
        self.analyst = User.objects.create_user("analyst1", password="x")
        self.client.force_login(self.analyst)
        self.flag = create_flag("txn-1", card1="1", amount="1.00", score=0.9, threshold=0.5)

    def test_approve_via_post_updates_status_and_redirects_to_queue(self):
        resp = self.client.post(reverse("decide", args=[self.flag.id]), {"decision": "approve"})
        self.assertRedirects(resp, reverse("queue"))
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, Flag.Status.APPROVED)
        self.assertEqual(self.flag.decided_by, self.analyst)

    def test_get_is_not_allowed(self):
        resp = self.client.get(reverse("decide", args=[self.flag.id]))
        self.assertEqual(resp.status_code, 405)
