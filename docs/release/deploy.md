# Mooviogo — Production deployment guide

This document walks you through a first deployment on a single VPS using Docker
Compose. For systemd-only deployments see `deploy/systemd/`.

## 0. Prerequisites

- A Linux server (Debian 12 / Ubuntu 22.04+), 4 GB RAM minimum, 2 vCPU
- A domain name with DNS A/AAAA pointing to the server
- SSH access as a sudoer
- Managed Postgres 15+ and managed Redis 7+ (Scaleway, Supabase, Neon, etc.)
- Optional: Cloudflare R2 / AWS S3 bucket for media

## 1. Provision the server

```bash
ssh user@server
sudo apt update && sudo apt -y upgrade
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit && ssh user@server  # re-login
```

## 2. Clone and configure

```bash
sudo mkdir -p /opt/mooviogo && sudo chown $USER /opt/mooviogo
cd /opt/mooviogo
git clone <your-repo> .
cp .env.production.example .env.production
python3 scripts/generate_prod_secrets.py >> .env.production  # APPEND, then nano to merge
nano .env.production  # fill in the real keys
```

## 3. TLS certificates

The included `nginx.conf` expects certs at `deploy/certs/fullchain.pem` and
`deploy/certs/privkey.pem`. The simplest path is **Caddy** instead of Nginx, or
running certbot once on the host:

```bash
sudo apt install -y certbot
sudo certbot certonly --standalone -d mooviogo.com -d www.mooviogo.com
sudo cp /etc/letsencrypt/live/mooviogo.com/fullchain.pem deploy/certs/
sudo cp /etc/letsencrypt/live/mooviogo.com/privkey.pem deploy/certs/
sudo chown -R $USER deploy/certs
```

Add a cron entry to renew:

```cron
0 3 * * 1 certbot renew --quiet && docker compose -f /opt/mooviogo/docker-compose.prod.yml restart nginx
```

## 4. First boot

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
docker compose -f docker-compose.prod.yml logs -f web   # follow startup logs
```

The `web` container automatically runs `migrate` and `collectstatic` on boot.

Create the first superuser:

```bash
docker compose exec web python manage.py createsuperuser
```

## 5. Smoke test

```bash
BASE_URL=https://mooviogo.com bash scripts/smoke_test.sh
```

## 6. Stripe webhook

In Stripe Dashboard → Developers → Webhooks → Add endpoint:

- URL: `https://mooviogo.com/api/payments/webhook/`
- Events: `payment_intent.succeeded`, `payment_intent.payment_failed`,
  `checkout.session.completed`, `account.updated` (Connect)
- Copy the `whsec_…` into `STRIPE_WEBHOOK_SECRET` in `.env.production` and
  redeploy.

## 7. Daily backups

```bash
sudo crontab -e
```

Add:

```cron
0 3 * * * DATABASE_URL='postgres://...' /opt/mooviogo/scripts/backup_db.sh >> /var/log/mooviogo-backup.log 2>&1
```

Test a restore on a staging DB **before** trusting backups.

## 8. Updates

```bash
cd /opt/mooviogo
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
bash scripts/smoke_test.sh
```

## 9. Rollback

```bash
git log --oneline -10
git checkout <previous-sha>
docker compose -f docker-compose.prod.yml build && docker compose up -d
# If a migration is incompatible:
docker compose exec web python manage.py migrate <app> <previous_migration>
```

## 10. Monitoring checklist

- [ ] Sentry receives a test exception
- [ ] UptimeRobot pings `/api/health/` every 5 min
- [ ] Disk usage alert (< 15 % free)
- [ ] Postgres slow query log enabled
- [ ] Celery beat `cleanup_expired_otp_keys` heartbeat visible in logs
