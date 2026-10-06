"""
Re-run the current sentiment model on saved feedback.

Feedback keeps the label it was given when submitted. If the model has been
retrained (or a server was still running an older model when a comment came
in), saved labels can disagree with what the model says now. This lists those
rows and, with --apply, updates them.

    python manage.py reclassify_feedback           # dry run: list differences only
    python manage.py reclassify_feedback --apply   # save the new labels
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from feedback import ml
from feedback.models import FeedbackLog


class Command(BaseCommand):
    help = "Re-classify saved feedback with the current model (dry run unless --apply is given)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help="Save the new labels. Without this flag nothing is changed.",
        )

    def handle(self, *args, apply=False, **options):
        logs = FeedbackLog.objects.select_related('service').order_by('timestamp')
        changed = 0
        for log in logs:
            new_sentiment = ml.classify(log.comment).capitalize()
            if new_sentiment == log.sentiment:
                continue
            changed += 1
            self.stdout.write(
                f"#{log.pk} {timezone.localtime(log.timestamp):%Y-%m-%d %H:%M} {log.service.name}: "
                f"{log.sentiment} -> {new_sentiment} | {log.comment[:60]!r}"
            )
            if apply:
                log.sentiment = new_sentiment
                log.save()  # save() also recomputes sentiment_priority

        total = logs.count()
        if not changed:
            self.stdout.write(self.style.SUCCESS(f"All {total} saved labels match the current model."))
        elif apply:
            self.stdout.write(self.style.SUCCESS(f"Updated {changed} of {total} feedback labels."))
        else:
            self.stdout.write(self.style.WARNING(
                f"{changed} of {total} saved labels differ from the current model. "
                "Run again with --apply to update them."
            ))
