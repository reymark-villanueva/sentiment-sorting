"""
Isabela State University - Cauayan Campus Library
Feedback & Student Sentiment Monitoring System — Models
"""

from django.db import models
from django.utils import timezone


class LibraryService(models.Model):
    """An operational service department evaluated by the feedback survey."""

    class IconChoices(models.TextChoices):
        BUILDING = 'building', 'Facilities'
        USERS = 'users', 'Library Staff'
        WIFI = 'wifi', 'Internet/Wi-Fi'
        MONITOR = 'monitor', 'Computer Services'
        BOOK_OPEN = 'book-open', 'Borrowing & Returning'
        LAYOUT = 'layout', 'Study Areas'
        GLOBE = 'globe', 'Online Resources'
        HELP_CIRCLE = 'help-circle', 'Other'

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(
        max_length=50,
        choices=IconChoices.choices,
        default=IconChoices.HELP_CIRCLE,
        help_text="Line-style icon identifier used by the service icon partial.",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Library Service"
        verbose_name_plural = "Library Services"

    def __str__(self):
        return self.name


class FeedbackLog(models.Model):
    """
    A single student sentiment evaluation for a library service.

    This system classifies sentiment purely from the written comment via the
    trained model (feedback.ml.classify) — there's no star rating or
    demographic field. sentiment_priority sorts negative feedback first, then
    neutral, then positive, so staff can triage the most urgent issues.
    """

    class Sentiment(models.TextChoices):
        NEGATIVE = 'Negative', 'Negative'
        NEUTRAL = 'Neutral', 'Neutral'
        POSITIVE = 'Positive', 'Positive'

    SENTIMENT_PRIORITY = {
        Sentiment.NEGATIVE: 0,
        Sentiment.NEUTRAL: 1,
        Sentiment.POSITIVE: 2,
    }

    service = models.ForeignKey(
        LibraryService,
        on_delete=models.CASCADE,
        related_name='feedbacks',
    )
    comment = models.TextField(help_text="Free-text feedback — classified by the trained sentiment model.")
    sentiment = models.CharField(
        max_length=10,
        choices=Sentiment.choices,
        editable=False,
        help_text="Classified by the trained sentiment model (feedback.ml) from `comment`.",
    )
    sentiment_priority = models.PositiveSmallIntegerField(
        default=1,
        editable=False,
        help_text="Sort key derived from sentiment: negative=0, neutral=1, positive=2.",
    )
    action_label = models.CharField(
        max_length=60,
        blank=True,
        default="Under Review",
        help_text="Administrative action, e.g. Create IT Ticket, ✓ Commended, Work Order Sent.",
    )
    is_action_resolved = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['sentiment_priority', '-timestamp']
        verbose_name = "Feedback Log"
        verbose_name_plural = "Feedback Logs"

    def compute_action_label(self):
        """Suggest an administrative action based on the classified sentiment and service."""
        if self.sentiment == self.Sentiment.POSITIVE:
            return "✓ Commended"
        if self.sentiment == self.Sentiment.NEGATIVE:
            service_name = self.service.name if self.service_id else ''
            if 'Wi-Fi' in service_name or 'Internet' in service_name or 'Computer' in service_name:
                return "Create IT Ticket"
            return "Work Order Sent"
        return "Under Review"

    def save(self, *args, **kwargs):
        # The view sets self.sentiment from the trained model (feedback.ml.classify)
        # before calling save(). This is just a defensive fallback in case that
        # was somehow skipped — comment is required, so this shouldn't normally fire.
        if not self.sentiment:
            self.sentiment = self.Sentiment.NEUTRAL
        self.sentiment_priority = self.SENTIMENT_PRIORITY.get(self.sentiment, 1)
        # Only auto-suggest an action label when the log is first created;
        # afterwards staff may change it (e.g. via the dashboard resolve action)
        # without it being silently overwritten on every subsequent save().
        if self.pk is None:
            self.action_label = self.compute_action_label()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.service.name} - {self.sentiment}"
