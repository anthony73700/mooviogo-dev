"""Gunicorn configuration for Mooviogo production."""

import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Workers: 2 * CPU + 1, overridable via env
_default_workers = multiprocessing.cpu_count() * 2 + 1
workers = int(os.environ.get("GUNICORN_WORKERS", _default_workers))

worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5

max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = 100

preload_app = os.environ.get("GUNICORN_PRELOAD", "true").lower() == "true"

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Trust the reverse proxy
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "*")
proxy_protocol = False
