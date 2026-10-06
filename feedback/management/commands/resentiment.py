"""
Re-predict the sentiment of every saved feedback row with the current model.

Run this after retraining, or after changing the prediction code, so older rows
stop showing labels from the previous model:

    python manage.py resentiment             # update every row that changed
    python manage.py resentiment --dry-run   # only list what would change

Same job as `reclassify_feedback`, but it applies the changes by default.
"""

from .reclassify_feedback import Command as ReclassifyCommand


class Command(ReclassifyCommand):
    help = "Re-predict the sentiment of all saved feedback with the current model (use --dry-run to preview)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="List the rows that would change without saving anything.",
        )

    def handle(self, *args, dry_run=False, **options):
        super().handle(*args, apply=not dry_run, **options)
