"""
Isabela State University - Cauayan Campus Library
Feedback Submission Form
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import FeedbackLog, LibraryService


class FeedbackForm(forms.ModelForm):
    """
    Validates the public feedback submission.

    Text-only by design: this system classifies sentiment from `comment`
    via the trained model, so a comment is required — there's no star
    rating or demographic field to fall back on.
    """

    service = forms.ModelChoiceField(
        queryset=LibraryService.objects.filter(is_active=True),
        error_messages={'required': 'Please select a library service.'},
    )
    comment = forms.CharField(
        min_length=3,
        widget=forms.Textarea(attrs={'rows': 5}),
        error_messages={
            'required': 'Please share your feedback — this is what gets classified.',
            'min_length': 'Please share a little more detail.',
        },
    )

    class Meta:
        model = FeedbackLog
        fields = ['service', 'comment']


class StaffLoginForm(AuthenticationForm):
    """AuthenticationForm with the site's input styling instead of Django's default widgets."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'isu-input', 'autofocus': True, 'placeholder': 'Staff username'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'isu-input', 'placeholder': 'Password'}),
    )
