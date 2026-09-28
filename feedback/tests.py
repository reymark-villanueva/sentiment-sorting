"""
Isabela State University - Cauayan Campus Library
Feedback app test suite
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from .models import FeedbackLog, LibraryService

User = get_user_model()


class LibraryServiceModelTests(TestCase):
    def test_eight_services_seeded_by_migration(self):
        self.assertEqual(LibraryService.objects.count(), 8)

    def test_str_returns_name(self):
        service = LibraryService.objects.first()
        self.assertEqual(str(service), service.name)


class FeedbackLogModelTests(TestCase):
    """Sentiment is set explicitly (as the view does, from feedback.ml.classify)
    — the model itself only derives sentiment_priority and action_label from it."""

    def setUp(self):
        self.service = LibraryService.objects.first()

    def test_positive_sentiment_is_commended(self):
        log = FeedbackLog.objects.create(
            service=self.service, comment='Great service!', sentiment=FeedbackLog.Sentiment.POSITIVE
        )
        self.assertEqual(log.action_label, "✓ Commended")
        self.assertEqual(log.sentiment_priority, 2)

    def test_neutral_sentiment_priority(self):
        log = FeedbackLog.objects.create(
            service=self.service, comment='It was okay.', sentiment=FeedbackLog.Sentiment.NEUTRAL
        )
        self.assertEqual(log.sentiment_priority, 1)

    def test_negative_sentiment_priority(self):
        log = FeedbackLog.objects.create(
            service=self.service, comment='Terrible.', sentiment=FeedbackLog.Sentiment.NEGATIVE
        )
        self.assertEqual(log.sentiment_priority, 0)

    def test_negative_on_wifi_service_creates_it_ticket_action(self):
        wifi = LibraryService.objects.get(name='Internet/Wi-Fi')
        log = FeedbackLog.objects.create(
            service=wifi, comment='Wifi is down.', sentiment=FeedbackLog.Sentiment.NEGATIVE
        )
        self.assertEqual(log.action_label, "Create IT Ticket")

    def test_manual_action_label_survives_later_saves(self):
        log = FeedbackLog.objects.create(
            service=self.service, comment='Terrible.', sentiment=FeedbackLog.Sentiment.NEGATIVE
        )
        log.action_label = "✓ Resolved"
        log.is_action_resolved = True
        log.save()
        log.refresh_from_db()
        self.assertEqual(log.action_label, "✓ Resolved")

    def test_blank_sentiment_defaults_to_neutral(self):
        log = FeedbackLog.objects.create(service=self.service, comment='...')
        self.assertEqual(log.sentiment, FeedbackLog.Sentiment.NEUTRAL)


class PublicViewTests(TestCase):
    def test_home_returns_200(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_does_not_link_staff_login(self):
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, reverse('staff_login'))

    def test_home_lists_every_active_service(self):
        hidden = LibraryService.objects.first()
        hidden.is_active = False
        hidden.save()
        response = self.client.get(reverse('home'))
        for service in LibraryService.objects.filter(is_active=True):
            self.assertContains(response, escape(service.name))
        self.assertEqual(len(response.context['services']), LibraryService.objects.filter(is_active=True).count())

    def test_feedback_step_returns_200(self):
        response = self.client.get(reverse('feedback_step'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'feedback_step.html')


class FeedbackSubmitTests(TestCase):
    """feedback_submit classifies `comment` via feedback.ml.classify — mocked
    here so these tests don't depend on the actual trained model files."""

    def setUp(self):
        self.service = LibraryService.objects.first()
        self.url = reverse('feedback_submit')

    @patch('feedback.views.ml.classify', return_value='negative')
    def test_valid_standard_post_creates_log_and_redirects(self, mock_classify):
        response = self.client.post(self.url, {
            'service': self.service.pk,
            'comment': 'The wifi needs to be faster.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeedbackLog.objects.count(), 1)
        mock_classify.assert_called_once_with('The wifi needs to be faster.')
        self.assertEqual(FeedbackLog.objects.first().sentiment, 'Negative')

    @patch('feedback.views.ml.classify', return_value='positive')
    def test_valid_ajax_post_returns_json_with_reference_code(self, mock_classify):
        response = self.client.post(
            self.url,
            {
                'service': self.service.pk,
                'comment': 'The staff were very helpful.',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('reference_code', data)

    def test_missing_comment_returns_400_with_errors(self):
        response = self.client.post(
            self.url,
            {'service': self.service.pk, 'comment': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')

    def test_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='librarian', password='testpass123', is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='student', password='testpass123', is_staff=False
        )
        self.url = reverse('admin_dashboard')

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_non_staff_redirected_to_login(self):
        self.client.login(username='student', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_user_sees_dashboard(self):
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/dashboard.html')

    def test_export_report_requires_staff(self):
        response = self.client.get(reverse('admin_export_report'))
        self.assertEqual(response.status_code, 302)

    def test_export_report_returns_csv_for_staff(self):
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(reverse('admin_export_report'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
