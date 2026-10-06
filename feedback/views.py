"""
Isabela State University - Cauayan Campus Library
Feedback & Admin Sentiment Dashboard Views
"""

import csv
import logging
import math
import re
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from . import ml
from .aspects import aspects_by_service_id
from .forms import FeedbackForm
from .models import FeedbackLog, LibraryService

logger = logging.getLogger(__name__)

DONUT_RADIUS = 38
DONUT_CIRCUMFERENCE = 2 * math.pi * DONUT_RADIUS  # ≈ 238.8, matches the dashboard SVG r=38

DEFAULT_RANGE = 'month'
RANGE_ALIASES = {'7days': 'week', '30days': 'month', '365days': 'year'}  # older bookmarked links
# With no date chosen, each range is a rolling window ending now.
RANGE_WINDOWS = {
    'week': timedelta(days=7),
    'month': timedelta(days=30),
    'year': timedelta(days=365),
}
RANGE_FILE_LABELS = {'week': 'Last_7_Days', 'month': 'Last_30_Days', 'year': 'Last_365_Days'}
EARLIEST_REPORT_DATE = date(2000, 1, 1)  # matches the date picker's min; keeps window math in range


def _aware_midnight(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _parse_picker_value(raw):
    """Parse ?date=: a plain date (what the date picker sends), or a week (2026-W41),
    month (2026-10) or year (2026) from hand-made links.

    Returns a date, or None if `raw` is blank or malformed.
    """
    raw = (raw or '').strip()
    try:
        if match := re.fullmatch(r'(\d{4})-W(\d{2})', raw):
            return date.fromisocalendar(int(match[1]), int(match[2]), 1)
        if match := re.fullmatch(r'(\d{4})-(\d{2})', raw):
            return date(int(match[1]), int(match[2]), 1)
        if re.fullmatch(r'\d{4}', raw):
            return date(int(raw), 1, 1)
        return parse_date(raw)
    except ValueError:  # well-formed but impossible, e.g. 2026-02-30 or week 60
        return None


def _calendar_period(range_param, day):
    """(first day, first day of the next period) of the calendar week / month / year containing `day`."""
    if range_param == 'week':  # Monday-Sunday, like the browser's week picker
        first = day - timedelta(days=day.weekday())
        return first, first + timedelta(days=7)
    if range_param == 'month':
        first = day.replace(day=1)
        return first, (first + timedelta(days=32)).replace(day=1)
    return date(day.year, 1, 1), date(day.year + 1, 1, 1)


def _report_window(request):
    """Resolve ?range= and ?date= into the reporting window and the one before it.

    With no date chosen, the window is the rolling last 7 / 30 / 365 days ending
    now. When staff pick a day in the calendar, the window is the whole calendar
    week / month / year (per the selected tab) containing that day, up to now if
    that period is still running, so choosing a month shows every entry of that
    month, not only that day. A malformed date counts as none; a future one is
    clamped to today.

    Returns a dict: range_param, calendar (bool), report_date (the picked day, or
    today), date_param ('' for the rolling window), since, until, previous_since,
    previous_until, file_label, ends_now and period_label.
    """
    range_param = request.GET.get('range', DEFAULT_RANGE)
    range_param = RANGE_ALIASES.get(range_param, range_param)
    if range_param not in RANGE_WINDOWS:
        range_param = DEFAULT_RANGE

    now = timezone.now()
    today = timezone.localdate(now)
    picked = _parse_picker_value(request.GET.get('date'))

    if picked is None:
        window = RANGE_WINDOWS[range_param]
        report_date, date_param, file_label = today, '', RANGE_FILE_LABELS[range_param]
        period_label = {'week': 'Last 7 days', 'month': 'Last 30 days', 'year': 'Last 365 days'}[range_param]
        since, until = now - window, now
        previous_since, previous_until = since - window, since
        ends_now = True
    else:
        picked = max(min(picked, today), EARLIEST_REPORT_DATE)
        first, after = _calendar_period(range_param, picked)
        report_date, date_param = picked, picked.isoformat()
        previous_first, _ = _calendar_period(range_param, first - timedelta(days=1))
        since, until = _aware_midnight(first), min(_aware_midnight(after), now)
        previous_since, previous_until = _aware_midnight(previous_first), since
        ends_now = _aware_midnight(after) > now
        file_label = {
            'week': f"Week_of_{first}",
            'month': f"Month_{first:%Y-%m}",
            'year': f"Year_{first.year}",
        }[range_param]
        last = after - timedelta(days=1)
        period_label = {
            'week': f"{first:%b} {first.day} – {last:%b} {last.day}, {last.year}",
            'month': f"{first:%B %Y}",
            'year': f"{first.year}",
        }[range_param]

    return {
        'range_param': range_param,
        'calendar': picked is not None,
        'report_date': report_date,
        'date_param': date_param,
        'since': since,
        'until': until,
        'previous_since': previous_since,
        'previous_until': previous_until,
        'file_label': file_label,
        'ends_now': ends_now,
        'period_label': period_label,
    }


def _is_ajax(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
    )


def _sentiment_breakdown(queryset):
    """Return (total, positive, neutral, negative, pos_pct, neu_pct, neg_pct) for a FeedbackLog queryset."""
    total = queryset.count()
    if not total:
        return 0, 0, 0, 0, 0.0, 0.0, 0.0
    positive = queryset.filter(sentiment=FeedbackLog.Sentiment.POSITIVE).count()
    neutral = queryset.filter(sentiment=FeedbackLog.Sentiment.NEUTRAL).count()
    negative = total - positive - neutral
    pos_pct = round(positive / total * 100, 1)
    neu_pct = round(neutral / total * 100, 1)
    neg_pct = round(negative / total * 100, 1)
    return total, positive, neutral, negative, pos_pct, neu_pct, neg_pct


def _attach_model_labels(logs):
    """Set NB / DT predictions on each FeedbackLog in `logs` (a list).

    Re-classifies each comment with the hybrid model's two sub-models, so staff
    can compare Naive Bayes and the Decision Tree against the saved sentiment.
    Sets `nb_label` / `dt_label` (capitalized to match FeedbackLog.sentiment,
    e.g. 'Negative') and `nb_confidence` / `dt_confidence` (whole percentages).
    Returns the hybrid's NB confidence threshold as a whole percentage, or None
    if there was nothing to classify or the model can't be loaded (the labels
    then stay None and the dashboard still renders).
    """
    for log in logs:
        log.nb_label = log.dt_label = log.nb_confidence = log.dt_confidence = None
    if not logs:
        return None
    try:
        result = ml.component_predictions([log.comment for log in logs])
    except Exception:
        logger.exception("Could not compute Naive Bayes / Decision Tree predictions")
        return None
    for log, prediction in zip(logs, result['rows']):
        (nb_label, nb_conf), (dt_label, dt_conf) = prediction['nb'], prediction['dt']
        log.nb_label, log.nb_confidence = nb_label.capitalize(), round(nb_conf * 100)
        log.dt_label, log.dt_confidence = dt_label.capitalize(), round(dt_conf * 100)
    return round(result['threshold'] * 100)


def home(request):
    """Public landing page: hero headline, CTA, and visual only."""
    return render(request, 'home.html')


def feedback_step(request):
    """The public feedback wizard: pick a service, write feedback."""
    services = LibraryService.objects.filter(is_active=True)
    context = {
        'services': services,
        'service_aspects': aspects_by_service_id(services),
    }
    return render(request, 'feedback_step.html', context)


@require_POST
def feedback_submit(request):
    """Validate and persist a feedback submission (standard POST or AJAX/JSON)."""
    form = FeedbackForm(request.POST)

    if form.is_valid():
        log = form.save(commit=False)
        # comment is required by the form, so there's always text to classify.
        log.sentiment = ml.classify(form.cleaned_data['comment']).capitalize()
        log.save()
        reference_code = f"ISU-LIB-{log.pk:06d}"

        if _is_ajax(request):
            return JsonResponse({
                'status': 'success',
                'message': 'Thank you! Your library feedback has been submitted successfully.',
                'reference_code': reference_code,
            })

        messages.success(
            request,
            f"Thank you! Your feedback was submitted (Reference: {reference_code})."
        )
        return redirect('home')

    # Invalid submission
    if _is_ajax(request):
        return JsonResponse(
            {'status': 'error', 'errors': form.errors.get_json_data()},
            status=400,
        )

    messages.error(request, "Your feedback could not be submitted — please check the form and try again.")
    context = {
        'services': LibraryService.objects.filter(is_active=True),
        'form': form,
    }
    return render(request, 'feedback_step.html', context, status=400)


@staff_member_required(login_url='staff_login')
def admin_dashboard(request):
    """Staff-only real-time student sentiment monitoring dashboard."""
    period = _report_window(request)
    range_param, date_param = period['range_param'], period['date_param']
    since, until = period['since'], period['until']

    # Service filter — shared by both the "Sentiment Breakdown by Library
    # Service" table and "Recent Feedback Logs" below, so selecting e.g.
    # Wi-Fi narrows both to just that service's entries.
    all_services = LibraryService.objects.filter(is_active=True)
    service_param = request.GET.get('service', '')
    selected_service = None
    if service_param.isdigit():
        selected_service = all_services.filter(pk=service_param).first()
    if not selected_service:
        service_param = ''  # missing/non-numeric/stale id -> fall back to "All Services"

    logs_qs = FeedbackLog.objects.filter(timestamp__gte=since, timestamp__lt=until)
    previous_qs = FeedbackLog.objects.filter(
        timestamp__gte=period['previous_since'], timestamp__lt=period['previous_until']
    )

    total, positive, neutral, negative, pos_pct, neu_pct, neg_pct = _sentiment_breakdown(logs_qs)

    prev_total, _, _, _, prev_pos_pct, prev_neu_pct, prev_neg_pct = _sentiment_breakdown(previous_qs)

    def _trend(curr, prev, has_prev):
        if not has_prev:
            return {'delta': None, 'direction': 'neutral', 'display': '—'}
        delta = round(curr - prev, 1)
        direction = 'positive' if delta > 0 else 'negative' if delta < 0 else 'neutral'
        arrow = '↑' if delta > 0 else '↓' if delta < 0 else '→'
        return {'delta': delta, 'direction': direction, 'display': f"{arrow} {delta:+.1f}%"}

    positive_trend = _trend(pos_pct, prev_pos_pct, bool(prev_total))
    neutral_trend = _trend(neu_pct, prev_neu_pct, bool(prev_total))
    negative_trend = _trend(neg_pct, prev_neg_pct, bool(prev_total))

    # Donut chart geometry (circle r=38 -> circumference ≈ 238.8)
    pos_dash = round(DONUT_CIRCUMFERENCE * pos_pct / 100, 1)
    neu_dash = round(DONUT_CIRCUMFERENCE * neu_pct / 100, 1)
    neg_dash = round(DONUT_CIRCUMFERENCE * neg_pct / 100, 1)
    donut = {
        'circumference': round(DONUT_CIRCUMFERENCE, 1),
        'pos_dash': pos_dash,
        'neu_dash': neu_dash,
        'neg_dash': neg_dash,
        'neu_offset': round(-pos_dash, 1),
        'neg_offset': round(-(pos_dash + neu_dash), 1),
    }

    # Per-service breakdown within the selected date range — narrowed to just
    # the selected service when the service filter is active.
    service_breakdown = []
    services_to_show = [selected_service] if selected_service else all_services
    for service in services_to_show:
        svc_qs = logs_qs.filter(service=service)
        svc_total, _, _, _, svc_pos, svc_neu, svc_neg = _sentiment_breakdown(svc_qs)

        is_it_related = any(k in service.name for k in ('Wi-Fi', 'Internet', 'Computer'))

        if svc_total == 0:
            status_type, status_text = 'neutral', 'No feedback recorded this period'
            insight_text = "No feedback recorded this period — insight unavailable."
        elif svc_neg >= 20:
            status_type, status_text = 'danger', 'Needs Attention'
            insight_text = (
                "High negative sentiment — escalate to IT for an infrastructure review."
                if is_it_related else
                "High negative sentiment — prioritize a service review this period."
            )
        elif svc_neg >= 10:
            status_type, status_text = 'warning', 'Monitor Closely'
            insight_text = "Negative sentiment is rising — monitor closely and address recurring complaints."
        elif svc_pos >= 70:
            status_type, status_text = 'success', 'Performing Well'
            insight_text = "Strong positive sentiment — maintain current service standards."
        else:
            status_type, status_text = 'success', 'Performing Well'
            insight_text = "Sentiment is stable — no urgent action needed."

        service_breakdown.append({
            'name': service.name,
            'icon': service.icon,
            'description': service.description,
            'pos_pct': svc_pos,
            'neu_pct': svc_neu,
            'neg_pct': svc_neg,
            'total_count': svc_total,
            'status_type': status_type,
            'status_text': status_text,
            'insight_text': insight_text,
        })

    # Automated key insight comparing best/worst performing services
    scored = [s for s in service_breakdown if s['total_count'] > 0]
    if scored:
        worst = max(scored, key=lambda s: s['neg_pct'])
        best = max(scored, key=lambda s: s['pos_pct'])
        if worst['neg_pct'] > 0:
            key_insight = (
                f"{worst['name']} shows the highest negative sentiment this period at "
                f"{worst['neg_pct']}% ({worst['total_count']} evaluations), while {best['name']} "
                f"leads in positive sentiment at {best['pos_pct']}%."
            )
        else:
            key_insight = (
                f"All evaluated services are trending positive this period, led by {best['name']} "
                f"at {best['pos_pct']}% positive sentiment."
            )
    else:
        key_insight = "Not enough feedback has been recorded in this period to generate a trend insight."

    # Trend chart: split the selected window into 6 buckets
    bucket_count = 6
    bucket_length = (until - since) / bucket_count
    last_label = 'Today' if period['ends_now'] else timezone.localtime(until - timedelta(seconds=1)).strftime('%b %d')
    trend_points = []
    for i in range(bucket_count):
        bucket_start = since + bucket_length * i
        bucket_end = since + bucket_length * (i + 1)
        bucket_qs = FeedbackLog.objects.filter(timestamp__gte=bucket_start, timestamp__lt=bucket_end)
        b_total, _, _, _, b_pos, b_neu, b_neg = _sentiment_breakdown(bucket_qs)
        trend_points.append({
            'label': last_label if i == bucket_count - 1 else timezone.localtime(bucket_end).strftime('%b %d'),
            'positive': b_pos,
            'neutral': b_neu,
            'negative': b_neg,
            'total': b_total,
        })

    # Recent feedback log stream (independent of the date-range filter, but
    # respects the same service filter as the breakdown table above),
    # paginated, newest first regardless of sentiment.
    recent_qs = FeedbackLog.objects.select_related('service').order_by('-timestamp', '-pk')
    if selected_service:
        recent_qs = recent_qs.filter(service=selected_service)
    paginator = Paginator(recent_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    feedback_logs = list(page_obj.object_list)
    nb_threshold_pct = _attach_model_labels(feedback_logs)  # only this page's rows are re-classified

    context = {
        'range_param': range_param,
        'date_param': date_param,
        'report_date': period['report_date'].isoformat(),
        'earliest_report_date': EARLIEST_REPORT_DATE.isoformat(),
        'period_label': period['period_label'],
        'service_param': service_param,
        'selected_service': selected_service,
        'all_services': all_services,
        'positive': positive,
        'neutral': neutral,
        'negative': negative,
        'total_responses': total,
        'positive_percentage': f"{pos_pct}%",
        'positive_count': f"{positive} responses",
        'neutral_percentage': f"{neu_pct}%",
        'neutral_count': f"{neutral} responses",
        'negative_percentage': f"{neg_pct}%",
        'negative_count': f"{negative} responses",
        'total_feedback_count': f"{total:,} total evaluations this period",
        'positive_trend': positive_trend,
        'neutral_trend': neutral_trend,
        'negative_trend': negative_trend,
        'donut': donut,
        'service_breakdown': service_breakdown,
        'key_insight': key_insight,
        'trend_points': trend_points,
        'page_obj': page_obj,
        'feedback_logs': feedback_logs,
        'nb_threshold_pct': nb_threshold_pct,
        'active_nav': 'sentiment',
    }
    return render(request, 'admin/dashboard.html', context)


@staff_member_required(login_url='staff_login')
def admin_export_report(request):
    """Export the currently filtered feedback logs as a CSV report (opens in Excel)."""
    period = _report_window(request)
    logs = FeedbackLog.objects.select_related('service').filter(
        timestamp__gte=period['since'], timestamp__lt=period['until']
    )

    # Same service filter as the dashboard, so exporting matches what's on screen.
    service_param = request.GET.get('service', '')
    if service_param.isdigit():
        logs = logs.filter(service_id=service_param)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"ISU_Cauayan_Library_Sentiment_Report_{period['file_label']}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # UTF-8 byte-order mark: without it Excel assumes the local ANSI code page
    # and garbles characters like an em dash.
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Service', 'Sentiment', 'Comment'])
    for log in logs:
        writer.writerow([
            # Local time (TIME_ZONE), matching the dashboard — not the stored UTC.
            timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M'),
            log.service.name,
            log.sentiment,
            log.comment,
        ])
    return response
