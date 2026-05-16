# Cahier des charges final - Mooviogo (Django uniquement)

Date de reference: 2026-05-15

## 1) Decision technique definitive

Le produit est un site web responsive developpe uniquement avec l'ecosysteme Django.

Stack validee:

- Python
- Django
- Django REST Framework
- PostgreSQL
- Redis
- Celery
- Django Channels
- Stripe / Stripe Connect

## 2) Contradictions supprimees

Les options suivantes sont explicitement hors scope:

- Next.js
- React Native
- NestJS
- Node.js
- Application mobile native iOS/Android

## 3) Cibles produit

- Plateforme web responsive unique (desktop/tablette/mobile web)
- API REST unifiee via DRF
- Temps reel via Django Channels (WebSockets)
- Paiements et onboarding partenaires via Stripe Connect

## 4) Exigences de conformite prioritaires

- Controle majorite 18+ a l'inscription
- Routes web partenaires/nightlife/admin completes
- Notifications multi-canaux (email/sms/whatsapp/push) avec file asynchrone Celery
- WebSockets chat temps reel
- Parcours Stripe Connect (creation compte, onboarding, statut)

## 5) Gouvernance des livrables

- Toute nouvelle specification doit respecter cette decision Django-only
- Aucun livrable ne doit introduire de dependance frontend/backend hors stack validee
- Les evolutions de capacite/scalabilite doivent rester compatibles avec PostgreSQL + Redis + Celery + Channels
