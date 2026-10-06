"""
Isabela State University - Cauayan Campus Library
URL Routing — feedback app
"""

from django.contrib.auth.views import LoginView
from django.urls import path

from . import views
from .forms import StaffLoginForm

urlpatterns = [
    # Public Student Portal
    path('', views.home, name='home'),

    # Staff Login — deliberately unlisted: the public landing page is for
    # students only, so nothing there links here.
    # LOGIN_URL in settings.py points here by name, so
    # @staff_member_required still redirects correctly. Always renders the login
    # form on GET, even if already authenticated as staff.
    path(
        'admin-LFS/',
        LoginView.as_view(
            template_name='staff_login.html',
            authentication_form=StaffLoginForm,
        ),
        name='staff_login',
    ),

    # Public Feedback Wizard (text-only: pick a service, write feedback)
    path('feedback/', views.feedback_step, name='feedback_step'),
    path('feedback/submit/', views.feedback_submit, name='feedback_submit'),

    # Staff Admin Sentiment Console
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/dashboard/export/', views.admin_export_report, name='admin_export_report'),
]
