"""
Isabela State University - Cauayan Campus Library
Feedback & Admin Sentiment Dashboard Views
"""

import csv
import logging
import math
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ml
from .aspects import aspects_by_service_id
from .forms import FeedbackForm
from .models import FeedbackLog, LibraryService

logger = logging.getLogger(__name__)

DONUT_RADIUS = 38
DONUT_CIRCUMFERENCE = 2 * math.pi * DONUT_RADIUS  # ≈ 238.8, matches the dashboard SVG r=38

RANGE_WINDOWS = {
    '7days': timedelta(days=7),
    '30days': timedelta(days=30),
}
RANGE_FILE_LABELS = {'7days': 'Last_7_Days', '30days': 'Last_30_Days'}


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
    """Public landing page."""
    return render(request, 'home.html', {
        'services': LibraryService.objects.filter(is_active=True),
        'library_email': settings.LIBRARY_CONTACT_EMAIL,
    })


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
    range_param = request.GET.get('range', '30days')
    if range_param not in RANGE_WINDOWS:
        range_param = '30days'
    window = RANGE_WINDOWS[range_param]

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

    now = timezone.now()
    since = now - window
    previous_since = since - window

    logs_qs = FeedbackLog.objects.filter(timestamp__gte=since)
    previous_qs = FeedbackLog.objects.filter(timestamp__gte=previous_since, timestamp__lt=since)

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
    bucket_length = window / bucket_count
    trend_points = []
    for i in range(bucket_count):
        bucket_start = since + bucket_length * i
        bucket_end = since + bucket_length * (i + 1)
        bucket_qs = FeedbackLog.objects.filter(timestamp__gte=bucket_start, timestamp__lt=bucket_end)
        b_total, _, _, _, b_pos, b_neu, b_neg = _sentiment_breakdown(bucket_qs)
        trend_points.append({
            'label': 'Today' if i == bucket_count - 1 else bucket_end.strftime('%b %d'),
            'positive': b_pos,
            'neutral': b_neu,
            'negative': b_neg,
            'total': b_total,
        })

    # Recent feedback log stream (independent of the date-range filter, but
    # respects the same service filter as the breakdown table above),
    # paginated. Relies on FeedbackLog.Meta.ordering (sentiment_priority,
    # then -timestamp) so negative feedback surfaces first.
    recent_qs = FeedbackLog.objects.select_related('service').all()
    if selected_service:
        recent_qs = recent_qs.filter(service=selected_service)
    paginator = Paginator(recent_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    feedback_logs = list(page_obj.object_list)
    nb_threshold_pct = _attach_model_labels(feedback_logs)  # only this page's rows are re-classified

    context = {
        'range_param': range_param,
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
@require_POST
def feedback_resolve(request, pk):
    """AJAX endpoint: mark a feedback log's administrative action as resolved."""
    log = get_object_or_404(FeedbackLog, pk=pk)
    log.is_action_resolved = True
    log.action_label = "✓ Resolved"
    log.save(update_fields=['is_action_resolved', 'action_label'])
    return JsonResponse({'status': 'success', 'action_label': log.action_label})


@staff_member_required(login_url='staff_login')
def admin_export_report(request):
    """Export the currently filtered feedback logs as a CSV report (opens in Excel)."""
    range_param = request.GET.get('range', '30days')
    if range_param not in RANGE_WINDOWS:
        range_param = '30days'
    since = timezone.now() - RANGE_WINDOWS[range_param]
    logs = FeedbackLog.objects.select_related('service').filter(timestamp__gte=since)

    # Same service filter as the dashboard, so exporting matches what's on screen.
    service_param = request.GET.get('service', '')
    if service_param.isdigit():
        logs = logs.filter(service_id=service_param)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"ISU_Cauayan_Library_Sentiment_Report_{RANGE_FILE_LABELS[range_param]}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # UTF-8 byte-order mark: without it Excel assumes the local ANSI code page
    # and garbles characters like "✓ Resolved" or an em dash.
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Service', 'Sentiment', 'Comment', 'Action', 'Resolved'])
    for log in logs:
        writer.writerow([
            # Local time (TIME_ZONE), matching the dashboard — not the stored UTC.
            timezone.localtime(log.timestamp).strftime('%Y-%m-%d %H:%M'),
            log.service.name,
            log.sentiment,
            log.comment,
            log.action_label,
            'Yes' if log.is_action_resolved else 'No',
        ])
    return response
