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


class ComponentPredictionTests(TestCase):
    """Runs the real sentiment_model.pkl: the hybrid must expose its NB and DT sub-models."""

    def test_returns_label_and_confidence_per_model_for_each_text(self):
        from . import ml
        texts = ['The wifi is very slow', 'Staff were very helpful']
        result = ml.component_predictions(texts)
        self.assertEqual(result['threshold'], 0.9)
        self.assertEqual(len(result['rows']), 2)

        model, vectorizer = ml._load()
        features = vectorizer.transform([ml.preprocess(t) for t in texts])
        for row, nb_expected, dt_expected in zip(result['rows'], model.nb_.predict(features), model.dt_.predict(features)):
            for key, expected in (('nb', nb_expected), ('dt', dt_expected)):
                label, confidence = row[key]
                self.assertEqual(label, str(expected).lower())  # same label the model itself predicts
                self.assertGreaterEqual(confidence, 1 / 3)       # top class of 3 is at least a third
                self.assertLessEqual(confidence, 1.0)

    def test_empty_input_skips_model(self):
        from . import ml
        self.assertEqual(ml.component_predictions([]), {'threshold': None, 'rows': []})


class ModelReloadTests(TestCase):
    """A retrained .pkl must take effect without restarting the server."""

    def setUp(self):
        from . import ml
        self.ml = ml
        self._saved = (ml._model, ml._vectorizer, ml._loaded_mtimes)
        ml._model = ml._vectorizer = ml._loaded_mtimes = None

    def tearDown(self):
        self.ml._model, self.ml._vectorizer, self.ml._loaded_mtimes = self._saved

    def test_reloads_only_when_model_files_change(self):
        with patch.object(self.ml, '_file_mtimes', side_effect=[(1, 1), (1, 1), (2, 2)]), \
             patch.object(self.ml.joblib, 'load', return_value=object()) as mock_load:
            self.ml._load()
            self.ml._load()
            self.assertEqual(mock_load.call_count, 2)  # model + vectorizer, loaded once
            self.ml._load()
            self.assertEqual(mock_load.call_count, 4)  # files changed -> reloaded


class ReclassifyFeedbackCommandTests(TestCase):
    def setUp(self):
        service = LibraryService.objects.get(name='Internet/Wi-Fi')
        self.log = FeedbackLog.objects.create(service=service, comment='the wifi needs to be faster', sentiment='Positive')

    @patch('feedback.management.commands.reclassify_feedback.ml.classify', return_value='negative')
    def test_dry_run_changes_nothing(self, mock_classify):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('reclassify_feedback', stdout=out)
        self.log.refresh_from_db()
        self.assertEqual(self.log.sentiment, 'Positive')
        self.assertIn('Positive -> Negative', out.getvalue())

    @patch('feedback.management.commands.reclassify_feedback.ml.classify', return_value='negative')
    def test_apply_updates_label_priority_and_auto_action(self, mock_classify):
        from io import StringIO
        from django.core.management import call_command
        call_command('reclassify_feedback', '--apply', stdout=StringIO())
        self.log.refresh_from_db()
        self.assertEqual(self.log.sentiment, 'Negative')
        self.assertEqual(self.log.sentiment_priority, 0)
        self.assertEqual(self.log.action_label, 'Create IT Ticket')


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

    @patch('feedback.views.ml.component_predictions')
    def test_recent_logs_show_naive_bayes_and_decision_tree_labels(self, mock_components):
        FeedbackLog.objects.create(
            service=LibraryService.objects.first(), comment='slow wifi', sentiment='Negative'
        )
        mock_components.return_value = {
            'threshold': 0.9,
            'rows': [{'nb': ('neutral', 0.814), 'dt': ('positive', 1.0)}],
        }
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(self.url)

        mock_components.assert_called_once_with(['slow wifi'])
        log = response.context['feedback_logs'][0]
        self.assertEqual((log.nb_label, log.nb_confidence), ('Neutral', 81))
        self.assertEqual((log.dt_label, log.dt_confidence), ('Positive', 100))
        self.assertEqual(response.context['nb_threshold_pct'], 90)
        self.assertContains(response, 'NB &amp; DT Results', html=False)
        self.assertContains(response, '81%')
        self.assertContains(response, 'at least 90% confident')

    @patch('feedback.views.ml.component_predictions', side_effect=OSError('model file missing'))
    def test_dashboard_renders_when_model_results_unavailable(self, mock_components):
        FeedbackLog.objects.create(service=LibraryService.objects.first(), comment='slow wifi', sentiment='Negative')
        self.client.login(username='librarian', password='testpass123')
        with self.assertLogs('feedback.views', level='ERROR'):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        log = response.context['feedback_logs'][0]
        self.assertIsNone(log.nb_label)

    def test_export_report_requires_staff(self):
        response = self.client.get(reverse('admin_export_report'))
        self.assertEqual(response.status_code, 302)

    def test_export_report_returns_csv_for_staff(self):
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(reverse('admin_export_report'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

    def _export(self, range_param):
        from datetime import timedelta
        from django.utils import timezone
        service = LibraryService.objects.get(name='Internet/Wi-Fi')
        now = timezone.now()
        for days, comment in ((2, 'two days ago'), (10, 'ten days ago'), (45, 'forty-five days ago')):
            FeedbackLog.objects.create(service=service, comment=comment, sentiment='Negative',
                                       timestamp=now - timedelta(days=days))
        self.client.login(username='librarian', password='testpass123')
        return self.client.get(reverse('admin_export_report'), {'range': range_param})

    def test_export_7_days_only_includes_last_week(self):
        response = self._export('7days')
        body = response.content.decode('utf-8-sig')
        self.assertIn('two days ago', body)
        self.assertNotIn('ten days ago', body)
        self.assertIn('Last_7_Days', response['Content-Disposition'])

    def test_export_30_days_includes_last_month(self):
        body = self._export('30days').content.decode('utf-8-sig')
        self.assertIn('two days ago', body)
        self.assertIn('ten days ago', body)
        self.assertNotIn('forty-five days ago', body)

    def test_semester_range_is_gone_and_falls_back_to_30_days(self):
        response = self._export('semester')
        self.assertIn('Last_30_Days', response['Content-Disposition'])
        self.assertNotIn('forty-five days ago', response.content.decode('utf-8-sig'))
        dashboard = self.client.get(self.url, {'range': 'semester'})
        self.assertEqual(dashboard.context['range_param'], '30days')
        self.assertNotContains(dashboard, 'This Semester')

    def test_export_is_excel_friendly_utf8_with_local_times(self):
        from django.utils import timezone
        response = self._export('7days')
        self.assertTrue(response.content.startswith('﻿'.encode('utf-8')))  # BOM for Excel
        log = FeedbackLog.objects.get(comment='two days ago')
        local = timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M')
        self.assertIn(local, response.content.decode('utf-8-sig'))
