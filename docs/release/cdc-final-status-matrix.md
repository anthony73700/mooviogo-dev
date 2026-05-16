# Matrice Finale CDC - Mooviogo

Date: 2026-05-15

## Statut global

- Couverture fonctionnelle principale: TERMINEE
- Couverture i18n front principale: TERMINEE
- Geocoding + UX carto: TERMINE
- Sweep de navigation/templates: TERMINE

## Exigences CDC vs statut

| Exigence CDC | Statut | Preuve / implementation |
| --- | --- | --- |
| Audit des ecarts et correction continue | Termine | Historique des vagues de patchs + tests passes |
| OTP telephone web + API | Termine | Endpoints auth + tests signup OTP |
| Inscription avec verification telephone | Termine | serializers/views auth + migration user phone |
| OAuth social + securisation Apple | Termine | verification JWKS/audience/issuer |
| SEO technique (robots, sitemap, OG, canonical, JSON-LD) | Termine | routes et templates web |
| OpenAPI + page docs | Termine | /api/schema/ + /api/docs/ |
| Consentement analytics pilote par env | Termine | base.html + settings + env |
| Geolocalisation modeles/serializers | Termine | migrations sorties/events geolocation |
| Geocoding provider + endpoint | Termine | /api/v1/city-feed/geocode/ |
| UX carto creation sortie (map + pin + coords) | Termine | template sorties/create + persistance view |
| Traduction exhaustive pages coeur (auth, sorties, restaurants, evenements, home, partenaire, admin) | Termine (coeur) | trans tags + catalogues fr/en |
| Rendu anglais reel | Termine | locale/en/LC_MESSAGES/django.po + django.mo |
| Sweep complet rendu/navigation | Termine | tests smoke + suite web verte |

## Validation effectuee

- `python manage.py check`: OK
- `pytest apps/web/tests/test_template_smoke_navigation.py`: OK
- `pytest apps/web/tests`: OK

## Risques residuels non bloquants

- Outil natif Django `makemessages/compilemessages` indisponible faute de gettext systeme dans cet environnement.
- Mitigation en place: generation PO/MO via script `scripts/update_i18n_catalogs.py`.

## Definition de fini (atteinte)

- Les parcours publics et proteges ne renvoient pas d'erreur 500 sur les routes web principales.
- Les flux critiques (auth OTP, reset password, SEO/docs) restent verts.
- Les pages coeur demandees sont internationalisees avec rendu anglais operationnel.
