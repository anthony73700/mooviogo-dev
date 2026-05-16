#!/usr/bin/env bash
# Entrypoint for the Mooviogo container.
# Usage: entrypoint.sh [web|asgi|worker|beat|shell|migrate]

set -euo pipefail

CMD="${1:-web}"

run_release_tasks() {
    echo "[entrypoint] python manage.py check --deploy"
    python manage.py check --deploy --fail-level WARNING || true
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
    if [[ "${SKIP_COLLECTSTATIC:-0}" != "1" ]]; then
        echo "[entrypoint] python manage.py collectstatic --noinput"
        python manage.py collectstatic --noinput --clear
    fi
}

case "$CMD" in
    web)
        run_release_tasks
        exec gunicorn mooviogo.wsgi:application \
            --config /app/deploy/gunicorn.conf.py
        ;;
    asgi)
        # WebSockets (chats) — separate process, no migrate
        exec daphne -b 0.0.0.0 -p "${PORT:-8001}" mooviogo.asgi:application
        ;;
    worker)
        exec celery -A mooviogo worker \
            --loglevel="${CELERY_LOG_LEVEL:-info}" \
            --concurrency="${CELERY_CONCURRENCY:-4}"
        ;;
    beat)
        exec celery -A mooviogo beat --loglevel="${CELERY_LOG_LEVEL:-info}"
        ;;
    migrate)
        run_release_tasks
        ;;
    shell)
        exec python manage.py shell
        ;;
    *)
        # Allow arbitrary command for debug
        exec "$@"
        ;;
esac
