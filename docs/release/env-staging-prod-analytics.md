# Guide .env staging/prod - Analytics + OTP + SEO

Date: 2026-05-15

Ce guide complete .env.example pour un deploiement rapide.

## 1) Staging (recommande pour tests)

```env
SECRET_KEY=change-me
DEBUG=False
ALLOWED_HOSTS=staging.mooviogo.com
APP_ENV=staging
APP_BASE_URL=https://staging.mooviogo.com

DATABASE_URL=postgres://user:pass@db:5432/mooviogo_staging
REDIS_URL=redis://redis:6379/0

ACCESS_TOKEN_LIFETIME_MINUTES=60
REFRESH_TOKEN_LIFETIME_DAYS=30

CORS_ALLOWED_ORIGINS=https://staging.mooviogo.com
CSRF_TRUSTED_ORIGINS=https://staging.mooviogo.com

STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=noreply@mooviogo.com

TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_FROM_SMS=+33xxxxxxxxx
TWILIO_FROM_WHATSAPP=whatsapp:+14155238886

WEB_PUSH_VAPID_PUBLIC_KEY=xxxx
WEB_PUSH_VAPID_PRIVATE_KEY=xxxx
WEB_PUSH_VAPID_CLAIMS_SUBJECT=mailto:hello@mooviogo.com

APPLE_CLIENT_ID=com.mooviogo.web

GEOCODING_ENABLED=True
GEOCODING_PROVIDER=nominatim
GEOCODING_NOMINATIM_URL=https://nominatim.openstreetmap.org/search
GEOCODING_USER_AGENT=mooviogo-staging/1.0 (ops@mooviogo.com)

ENABLE_ANALYTICS=True
GA4_MEASUREMENT_ID=G-XXXXXXX
POSTHOG_KEY=phc_xxxxx
POSTHOG_HOST=https://eu.i.posthog.com
META_PIXEL_ID=
TIKTOK_PIXEL_ID=
```

## 2) Production

```env
SECRET_KEY=very-strong-secret
DEBUG=False
ALLOWED_HOSTS=mooviogo.com,www.mooviogo.com
APP_ENV=production
APP_BASE_URL=https://mooviogo.com

DATABASE_URL=postgres://user:pass@db:5432/mooviogo
REDIS_URL=redis://redis:6379/0

ACCESS_TOKEN_LIFETIME_MINUTES=30
REFRESH_TOKEN_LIFETIME_DAYS=15

CORS_ALLOWED_ORIGINS=https://mooviogo.com,https://www.mooviogo.com
CSRF_TRUSTED_ORIGINS=https://mooviogo.com,https://www.mooviogo.com

STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_live_xxx

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=noreply@mooviogo.com

TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_FROM_SMS=+33xxxxxxxxx
TWILIO_FROM_WHATSAPP=whatsapp:+14155238886

WEB_PUSH_VAPID_PUBLIC_KEY=xxxx
WEB_PUSH_VAPID_PRIVATE_KEY=xxxx
WEB_PUSH_VAPID_CLAIMS_SUBJECT=mailto:hello@mooviogo.com

APPLE_CLIENT_ID=com.mooviogo.web

GEOCODING_ENABLED=True
GEOCODING_PROVIDER=nominatim
GEOCODING_NOMINATIM_URL=https://nominatim.openstreetmap.org/search
GEOCODING_USER_AGENT=mooviogo-prod/1.0 (ops@mooviogo.com)

ENABLE_ANALYTICS=True
GA4_MEASUREMENT_ID=G-XXXXXXX
POSTHOG_KEY=phc_xxxxx
POSTHOG_HOST=https://eu.i.posthog.com
META_PIXEL_ID=xxxxxxxx
TIKTOK_PIXEL_ID=xxxxxxxx
```

## 3) Verification rapide

- Verifier que robots et sitemap repondent: `/robots.txt`, `/sitemap.xml`.
- Verifier docs API: `/api/schema/`, `/api/docs/`.
- Verifier OTP web: `/inscription/`.
- Verifier consentement analytics: bandeau cookies visible au premier chargement si `ENABLE_ANALYTICS=True`.
- Verifier image OG par defaut: `/static/og/default-og.svg`.
- Verifier geocoding: `/api/v1/city-feed/geocode/?q=Rue+de+Rivoli&city=Paris`.

## 4) Hardening production (recommande)

### 4.1 JWT

- API publique standard:

  - `ACCESS_TOKEN_LIFETIME_MINUTES=15 a 30`
  - `REFRESH_TOKEN_LIFETIME_DAYS=7 a 15`

- Si risque eleve (operations sensibles):

  - `ACCESS_TOKEN_LIFETIME_MINUTES=10`
  - `REFRESH_TOKEN_LIFETIME_DAYS=7`

Objectif: limiter la fenetre d'abus en cas de vol de token.

### 4.2 CORS / CSRF

- Conserver une allowlist stricte, sans wildcard:

  - `CORS_ALLOWED_ORIGINS=https://mooviogo.com,https://www.mooviogo.com`
  - `CSRF_TRUSTED_ORIGINS=https://mooviogo.com,https://www.mooviogo.com`

- Ne pas ajouter de sous-domaines temporaires non maitrises.
- Verifier que APP_BASE_URL correspond exactement au domaine canonique public.

### 4.3 Cookies / HTTPS

Le fichier production active deja:

- SECURE_SSL_REDIRECT=True
- SESSION_COOKIE_SECURE=True
- CSRF_COOKIE_SECURE=True
- HSTS actif

Verification post-deploiement:

- redirection HTTP -> HTTPS sur toutes les routes.
- cookies session/csrf envoyes avec flag Secure.

### 4.4 Analytics et consentement

- Pour respecter le consentement:

  - `ENABLE_ANALYTICS=True` uniquement si bandeau actif et politique cookies a jour.

- Si incident legal/compliance:

  - basculer `ENABLE_ANALYTICS=False` pour couper tout tracking front sans redeploiement applicatif.

### 4.5 Secrets management

- Ne jamais commiter de secrets dans git (.env exclus du repo).
- Rotation recommandee trimestrielle de:

  - `SECRET_KEY`
  - `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`
  - `TWILIO_AUTH_TOKEN`
  - `WEB_PUSH_VAPID_PRIVATE_KEY`

- Journaliser la date de rotation dans l'ops runbook.

## 5) Runbook de verification post-deploiement (10 min)

- Securite HTTP: verifier redirection HTTPS et headers HSTS sur page d'accueil.
- SEO: `GET /robots.txt -> 200`, `GET /sitemap.xml -> 200`.
- API docs: `GET /api/schema/ -> 200`, `GET /api/docs/ -> 200`.
- Auth OTP: test d'inscription web avec envoi OTP.
- Analytics: consentement refuse sans appels GA4/PostHog/Pixel, consentement accepte avec appels trackers presents.
