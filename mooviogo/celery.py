"""Celery application for Mooviogo."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mooviogo.settings.development")

app = Celery("mooviogo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
