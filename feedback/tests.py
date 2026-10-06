"""
Isabela State University - Cauayan Campus Library
Feedback app test suite
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
    — the model itself only derives sentiment_priority from it."""

    def setUp(self):
        self.service = LibraryService.objects.first()

    def test_positive_sentiment_priority(self):
        log = FeedbackLog.objects.create(
            service=self.service, comment='Great service!', sentiment=FeedbackLog.Sentiment.POSITIVE
        )
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
        model, vectorizer = ml._load()
        self.assertEqual(result['threshold'], model.threshold)  # whatever the notebook trained with
        self.assertGreater(model.threshold, 0)
        self.assertLess(model.threshold, 1)
        self.assertEqual(len(result['rows']), 2)

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


class SentimentPredictionTests(TestCase):
    """Runs the real model on tests/sentiment_samples.py through the single `ml.classify()` function.

    Only the clear-cut English positives and negatives are hard assertions. The model is trained mostly
    on English, is weaker on neutral/factual sentences, and still mislabels the sentence in KNOWN_WEAK
    as neutral, so that one is only required to never come out as the *opposite* polarity.
    """

    KNOWN_WEAK = {'the wifi keeps dropping on the second floor'}
    OPPOSITE = {'positive': 'negative', 'negative': 'positive'}

    def setUp(self):
        from tests.sentiment_samples import CLEAR_ENGLISH, SAMPLES
        self.clear_english = CLEAR_ENGLISH
        self.samples = SAMPLES

    def test_clear_english_samples_get_the_right_label(self):
        from . import ml
        for text, expected in self.clear_english:
            predicted = ml.classify(text)
            self.assertNotEqual(predicted, self.OPPOSITE[expected], f"polarity flipped: {text!r} -> {predicted}")
            if text not in self.KNOWN_WEAK:
                self.assertEqual(predicted, expected, text)

    def test_no_sample_in_any_language_flips_polarity(self):
        from . import ml
        for text, expected, lang in self.samples:
            if expected in self.OPPOSITE:
                self.assertNotEqual(ml.classify(text), self.OPPOSITE[expected], f"[{lang}] {text!r}")

    def test_confidences_are_not_saturated_at_100_percent(self):
        """The dashboard's NB & DT percentages must carry information (calibrated NB, leaves of >= 10 rows)."""
        from . import ml
        rows = ml.component_predictions([text for text, _, _ in self.samples])['rows']
        for key, max_share in (('nb', 0.10), ('dt', 0.50)):
            saturated = sum(row[key][1] >= 0.99 for row in rows) / len(rows)
            self.assertLessEqual(saturated, max_share, f"{key.upper()} claims >=99% on {saturated:.0%} of samples")

    def test_classify_is_the_trained_hybrids_own_prediction(self):
        """Guards against reintroducing a custom 'highest percentage wins' rule on top of predict()."""
        from . import ml
        model, vectorizer = ml._load()
        for text, _, _ in self.samples:
            expected = str(model.predict(vectorizer.transform([ml.preprocess(text)]))[0]).lower()
            self.assertEqual(ml.classify(text), expected, text)

    def test_submitted_feedback_is_saved_and_shown_with_the_predicted_label(self):
        """form submit -> saved -> staff dashboard, for every clear-cut English sample."""
        import re
        from html import unescape
        service = LibraryService.objects.filter(is_active=True).first()
        for text, expected in self.clear_english:
            response = self.client.post(reverse('feedback_submit'), {'service': service.pk, 'comment': text})
            self.assertIn(response.status_code, (200, 302))
            saved = FeedbackLog.objects.get(comment=text)
            self.assertEqual(saved.sentiment, saved.sentiment.capitalize())
            self.assertNotEqual(saved.sentiment.lower(), self.OPPOSITE[expected], text)

        User.objects.create_user(username='librarian2', password='testpass123', is_staff=True)
        self.client.login(username='librarian2', password='testpass123')
        html = self.client.get(reverse('admin_dashboard')).content.decode()
        shown = {}
        for row in re.findall(r'<tr>(.*?)</tr>', html, re.S):
            comment = re.search(r'font-style: italic;">\s*"(.*?)"\s*</td>', row, re.S)
            pill = re.search(r'isu-status-pill isu-status-\w+">(\w+)<', row)  # first pill = the Sentiment column
            if comment and pill:
                shown[unescape(comment.group(1)).strip()] = pill.group(1)
        for text, _ in self.clear_english:
            self.assertEqual(shown.get(text), FeedbackLog.objects.get(comment=text).sentiment, text)


class ResentimentCommandTests(TestCase):
    def setUp(self):
        service = LibraryService.objects.first()
        self.bad = FeedbackLog.objects.create(service=service, comment='the staff are friendly and very helpful',
                                              sentiment='Negative')
        self.good = FeedbackLog.objects.create(service=service, comment='borrowing and returning was fast and easy',
                                               sentiment='Positive')

    def _run(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('resentiment', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_only_lists_wrong_rows(self):
        output = self._run('--dry-run')
        self.bad.refresh_from_db()
        self.assertEqual(self.bad.sentiment, 'Negative')
        self.assertIn('Negative -> Positive', output)

    def test_corrects_wrong_rows_and_priority_and_leaves_good_rows(self):
        self._run()
        self.bad.refresh_from_db()
        self.good.refresh_from_db()
        self.assertEqual((self.bad.sentiment, self.bad.sentiment_priority), ('Positive', 2))
        self.assertEqual(self.good.sentiment, 'Positive')


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
    def test_apply_updates_label_and_priority(self, mock_classify):
        from io import StringIO
        from django.core.management import call_command
        call_command('reclassify_feedback', '--apply', stdout=StringIO())
        self.log.refresh_from_db()
        self.assertEqual(self.log.sentiment, 'Negative')
        self.assertEqual(self.log.sentiment_priority, 0)


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
        for days, comment in ((2, 'two days ago'), (10, 'ten days ago'), (45, 'forty-five days ago'),
                              (200, 'two hundred days ago'), (400, 'four hundred days ago')):
            FeedbackLog.objects.create(service=service, comment=comment, sentiment='Negative',
                                       timestamp=now - timedelta(days=days))
        self.client.login(username='librarian', password='testpass123')
        return self.client.get(reverse('admin_export_report'), {'range': range_param})

    def _body(self, response):
        return response.content.decode('utf-8-sig')

    # --- No date chosen: rolling last 7 / 30 / 365 days -----------------------

    def test_weekly_without_a_date_is_the_last_7_days(self):
        response = self._export('week')
        body = self._body(response)
        self.assertIn('two days ago', body)
        self.assertNotIn('ten days ago', body)
        self.assertIn('Last_7_Days', response['Content-Disposition'])

    def test_monthly_without_a_date_is_the_last_30_days(self):
        body = self._body(self._export('month'))
        self.assertIn('ten days ago', body)
        self.assertNotIn('forty-five days ago', body)

    def test_yearly_without_a_date_is_the_last_365_days(self):
        response = self._export('year')
        body = self._body(response)
        self.assertIn('two hundred days ago', body)
        self.assertNotIn('four hundred days ago', body)
        self.assertIn('Last_365_Days', response['Content-Disposition'])

    def test_old_range_names_still_work(self):
        self._export('week')  # seeds the logs
        body = self._body(self.client.get(reverse('admin_export_report'), {'range': '7days'}))
        self.assertIn('two days ago', body)
        self.assertNotIn('ten days ago', body)

    def test_unknown_range_falls_back_to_monthly(self):
        response = self._export('semester')
        self.assertIn('Last_30_Days', response['Content-Disposition'])
        dashboard = self.client.get(self.url, {'range': 'semester'})
        self.assertEqual(dashboard.context['range_param'], 'month')
        self.assertNotContains(dashboard, 'This Semester')

    # --- A week / month / year chosen: the whole calendar period -------------

    def _log_at(self, comment, year, month, day, hour, minute=0):
        from django.utils import timezone
        from datetime import datetime
        FeedbackLog.objects.create(
            service=LibraryService.objects.first(), comment=comment, sentiment='Negative',
            timestamp=timezone.make_aware(datetime(year, month, day, hour, minute)),
        )

    def _export_for(self, range_param, date_value):
        self.client.login(username='librarian', password='testpass123')
        return self.client.get(reverse('admin_export_report'), {'range': range_param, 'date': date_value})

    def test_picking_a_month_shows_that_whole_month_not_one_day(self):
        self._log_at('first of march', 2025, 3, 1, 0, 30)
        self._log_at('mid march', 2025, 3, 15, 12)
        self._log_at('last of march', 2025, 3, 31, 23, 30)
        self._log_at('end of february', 2025, 2, 28, 23, 30)
        self._log_at('start of april', 2025, 4, 1, 0, 30)
        response = self._export_for('month', '2025-03')
        body = self._body(response)
        for expected in ('first of march', 'mid march', 'last of march'):
            self.assertIn(expected, body)
        self.assertNotIn('end of february', body)
        self.assertNotIn('start of april', body)
        self.assertIn('Month_2025-03', response['Content-Disposition'])

    def test_picking_a_week_shows_monday_to_sunday(self):
        self._log_at('monday', 2025, 3, 10, 0, 30)
        self._log_at('sunday night', 2025, 3, 16, 23, 30)
        self._log_at('previous sunday', 2025, 3, 9, 23, 30)
        self._log_at('next monday', 2025, 3, 17, 0, 30)
        response = self._export_for('week', '2025-W11')
        body = self._body(response)
        self.assertIn('monday', body)
        self.assertIn('sunday night', body)
        self.assertNotIn('previous sunday', body)
        self.assertNotIn('next monday', body)
        self.assertIn('Week_of_2025-03-10', response['Content-Disposition'])

    def test_picking_a_year_shows_the_whole_year(self):
        self._log_at('new year', 2025, 1, 1, 0, 30)
        self._log_at('new years eve', 2025, 12, 31, 23, 30)
        self._log_at('last year', 2024, 12, 31, 23, 30)
        self._log_at('next year', 2026, 1, 1, 0, 30)
        response = self._export_for('year', '2025')
        body = self._body(response)
        self.assertIn('new year', body)
        self.assertIn('new years eve', body)
        self.assertNotIn('last year', body)
        self.assertNotIn('next year', body)
        self.assertIn('Year_2025', response['Content-Disposition'])

    def test_any_date_inside_the_period_selects_the_same_period(self):
        self._log_at('mid march', 2025, 3, 15, 12)
        self._log_at('end of february', 2025, 2, 28, 12)
        body = self._body(self._export_for('month', '2025-03-20'))  # a plain date, e.g. from an old link
        self.assertIn('mid march', body)
        self.assertNotIn('end of february', body)

    def test_dashboard_for_a_chosen_month_counts_the_whole_month(self):
        self._log_at('first of march', 2025, 3, 1, 0, 30)
        self._log_at('last of march', 2025, 3, 31, 23, 30)
        self._log_at('start of april', 2025, 4, 1, 0, 30)
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(self.url, {'range': 'month', 'date': '2025-03'})
        self.assertEqual(response.context['total_responses'], 2)
        self.assertEqual(response.context['date_param'], '2025-03-01')
        self.assertEqual(response.context['period_label'], 'March 2025')
        self.assertNotEqual(response.context['trend_points'][-1]['label'], 'Today')
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'value="2025-03-01"')
        self.assertContains(response, 'date=2025-03-01')  # tabs / export keep the chosen day

    def test_calendar_date_picker_is_a_day_picker_on_every_tab(self):
        self.client.login(username='librarian', password='testpass123')
        for range_param in ('week', 'month', 'year'):
            response = self.client.get(self.url, {'range': range_param, 'date': '2025-03-20'})
            self.assertContains(response, 'type="date"')
            self.assertContains(response, 'value="2025-03-20"')  # the picked day is kept, so switching tabs keeps it
            self.assertEqual(response.context['report_date'], '2025-03-20')

    def test_tab_decides_the_span_of_the_picked_day(self):
        self.client.login(username='librarian', password='testpass123')
        labels = {
            'week': 'Mar 17 – Mar 23, 2025',
            'month': 'March 2025',
            'year': '2025',
        }
        for range_param, label in labels.items():
            response = self.client.get(self.url, {'range': range_param, 'date': '2025-03-20'})
            self.assertEqual(response.context['period_label'], label, range_param)

    def test_picking_a_day_through_the_calendar_shows_its_whole_month(self):
        self._log_at('early', 2025, 3, 2, 9)
        self._log_at('late', 2025, 3, 29, 9)
        body = self._body(self._export_for('month', '2025-03-15'))  # what the date input sends
        self.assertIn('early', body)
        self.assertIn('late', body)

    def test_bad_dates_fall_back_to_the_rolling_window(self):
        self._export('week')  # seeds the logs
        for value in ('', 'not-a-date', '2026-02-30', '2025-W60', '2025-13'):
            response = self.client.get(self.url, {'range': 'week', 'date': value})
            self.assertEqual(response.status_code, 200, value)
            self.assertEqual(response.context['date_param'], '', value)
            self.assertEqual(response.context['total_responses'], 1, value)  # only 'two days ago'

    def test_future_date_is_clamped_to_the_current_period(self):
        from datetime import timedelta
        from django.utils import timezone
        today = timezone.localdate()
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(self.url, {'range': 'month', 'date': (today + timedelta(days=90)).isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['date_param'], today.isoformat())  # clamped to today, so the current month so far
        self.assertEqual(response.context['trend_points'][-1]['label'], 'Today')

    def test_very_old_date_is_clamped_to_the_earliest_supported_one(self):
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(self.url, {'range': 'year', 'date': '0001-01-01'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['period_label'], '2000')

    def test_comparison_uses_the_previous_calendar_month(self):
        def log(comment, sentiment, month, day):
            from datetime import datetime
            from django.utils import timezone
            FeedbackLog.objects.create(
                service=LibraryService.objects.first(), comment=comment, sentiment=sentiment,
                timestamp=timezone.make_aware(datetime(2025, month, day, 12)),
            )
        log('march', 'Negative', 3, 10)
        log('february bad', 'Negative', 2, 10)
        log('february good', 'Positive', 2, 20)
        log('january', 'Positive', 1, 20)  # two months back: not part of the comparison
        self.client.login(username='librarian', password='testpass123')
        response = self.client.get(self.url, {'range': 'month', 'date': '2025-03'})
        self.assertEqual(response.context['total_responses'], 1)
        self.assertEqual(response.context['negative_trend']['delta'], 50.0)  # 100% negative vs 50% in February

    def test_recent_logs_are_newest_first_regardless_of_sentiment(self):
        from datetime import timedelta
        from django.utils import timezone
        service = LibraryService.objects.first()
        now = timezone.now()
        for hours, sentiment in ((3, 'Negative'), (1, 'Positive'), (2, 'Neutral')):
            FeedbackLog.objects.create(service=service, comment=f'{hours}h ago', sentiment=sentiment,
                                       timestamp=now - timedelta(hours=hours))
        self.client.login(username='librarian', password='testpass123')
        with patch('feedback.views.ml.component_predictions', return_value={'threshold': 0.9, 'rows': []}):
            response = self.client.get(self.url)
        self.assertEqual([log.comment for log in response.context['feedback_logs']], ['1h ago', '2h ago', '3h ago'])

    def test_export_is_excel_friendly_utf8_with_local_times(self):
        from django.utils import timezone
        response = self._export('week')
        self.assertTrue(response.content.startswith('﻿'.encode('utf-8')))  # BOM for Excel
        log = FeedbackLog.objects.get(comment='two days ago')
        local = timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M')
        self.assertIn(local, response.content.decode('utf-8-sig'))
