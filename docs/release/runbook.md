# Mooviogo — Incident Runbook

## On-call quick reference

| Symptom | First action |
| --- | --- |
| `/health/` returns 503 | `docker compose logs web db redis` |
| 5xx spike in Sentry | Identify the offending endpoint, hotfix or rollback |
| Payments failing | Check Stripe Dashboard → Events; verify `STRIPE_WEBHOOK_SECRET` |
| OTP SMS not sending | Twilio console → Logs; check balance + number status |
| Celery queue backing up | `docker compose exec worker celery -A mooviogo inspect active` |
| WebSocket chats disconnected | Restart `asgi` service; check Redis memory |

## Restart procedures

```bash
# Restart everything
docker compose -f docker-compose.prod.yml restart

# Restart only workers (safe, no user impact)
docker compose -f docker-compose.prod.yml restart worker beat

# Force flush Celery queue (DANGEROUS — loses pending tasks)
docker compose exec redis redis-cli FLUSHDB
```

## Rollback to last known good

```bash
cd /opt/mooviogo
PREV=$(git log --oneline -n 5 | sed -n '2p' | awk '{print $1}')
git checkout "$PREV"
docker compose -f docker-compose.prod.yml build web asgi worker beat
docker compose -f docker-compose.prod.yml up -d
bash scripts/smoke_test.sh
```

## Restore database backup

```bash
gunzip -c /var/backups/mooviogo/mooviogo-YYYYMMDDTHHMMSSZ.sql.gz | \
    psql "$DATABASE_URL"
```

Run on a **staging** DB first, never on prod blind.

## Secrets rotation

1. `python scripts/generate_prod_secrets.py` to generate new keys
2. Update `.env.production`
3. **Important**: `SECRET_KEY` rotation invalidates sessions but not JWTs
   (signing key for JWT is separate via SimpleJWT defaults — verify).
4. `DATA_ENCRYPTION_KEY` rotation requires re-encrypting existing rows;
   use a temporary dual-read code path before retiring the old key.

## Capacity playbook

- 5xx > 1 % for 5 min → scale `web` to N+1 replicas
- Celery queue depth > 500 → scale `worker` concurrency
- DB CPU > 80 % sustained → add read replica or upgrade tier

## Contacts

- Tech lead: …
- Stripe support: dashboard.stripe.com/support
- Twilio support: support.twilio.com
- Hosting: …
