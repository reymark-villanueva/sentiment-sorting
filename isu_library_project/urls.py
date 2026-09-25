"""
URL configuration for isu_library_project project.

The Django built-in admin (model CRUD) is mounted at /django-admin/ so it
doesn't collide with the custom staff console at /admin/dashboard/
(feedback.urls). `staff_member_required` still resolves 'admin:login'
correctly regardless of the URL prefix used here.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('feedback.urls')),
]
