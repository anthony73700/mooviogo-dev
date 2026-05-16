# Plan de cloture 48h - Go/No-Go

Date de preparation: 2026-05-15
Perimetre: Mooviogo Django (release finale)

## Objectif

Valider en 48h la mise en production avec un gate Go/No-Go factuel, base sur des preuves (tests, checks, legal, ops).

## Roles

- Release Manager: pilotage du planning et decision finale.
- Tech Lead: validation code, migrations, qualite, rollback.
- QA Lead: execution recette et smoke tests.
- Ops/Infra: deploiement, observabilite, supervision.
- Legal/Compliance: validation textes juridiques et mentions obligatoires.

## Timeline execution (T0 = fenetre de release)

## T-48h a T-36h - Gel fonctionnel + verification de base

- [ ] Freeze des features (uniquement correctifs critiques autorises).
- [ ] Verifier branche cible et changelog release.
- [ ] Confirmer migrations presentes et ordonnees.
- [ ] Lancer checks Django.
- [ ] Lancer suite tests critiques.

Commandes:

```bash
cd /home/debian/mooviogo-dev
/home/debian/mooviogo-dev/.venv/bin/python manage.py check
/home/debian/mooviogo-dev/.venv/bin/python -m pytest apps/tickets/tests/test_ticket_validation.py apps/reports/tests/test_report_moderation.py apps/reports/tests/test_report_observability.py apps/web/tests/test_password_reset_flow.py apps/web/tests/test_admin_analytics_finance.py -q
/home/debian/mooviogo-dev/.venv/bin/python manage.py showmigrations
```

Critere de passage:

- [ ] 0 erreur bloquante sur check.
- [ ] Tests critiques verts.
- [ ] Aucune migration manquante ou incoherente.

## T-36h a T-24h - Recette fonctionnelle ciblee

- [ ] Recette scan QR operateur: success, token invalide, hors perimetre.
- [ ] Recette moderation: assign, resolve, dismiss, ban, suspend.
- [ ] Recette reset password: demande email + confirmation token.
- [ ] Recette analytics admin: KPI + export CSV.
- [ ] Recette pages legales: tous les slugs et rendu HTML.

Scenarios minimaux a cocher:

- [ ] Scan ticket valide -> statut USED + audit SUCCESS.
- [ ] Scan hors perimetre -> refus + reason_code + audit FORBIDDEN_SCOPE.
- [ ] Moderation ban_user -> user desactive + event/alert log.
- [ ] Forgot password rate limit -> HTTP 429 + alerte.
- [ ] Analytics CSV contient processing_fees_cents et platform_net_cents.

Critere de passage:

- [ ] 100% des scenarios critiques passes.
- [ ] 0 bug Sev-1/Sev-2 ouvert.

## T-24h a T-12h - Pre-prod, securite, observabilite

- [ ] Verifier variables d'environnement production.
- [ ] Verifier backend email production (pas console backend).
- [ ] Verifier throttling actif et coherent.
- [ ] Verifier logs observabilite (event/alert) et collecte centralisee.
- [ ] Verifier endpoint health.

Commandes / checks:

```bash
cd /home/debian/mooviogo-dev
/home/debian/mooviogo-dev/.venv/bin/python manage.py check --deploy
/home/debian/mooviogo-dev/.venv/bin/python manage.py migrate --plan
/home/debian/mooviogo-dev/.venv/bin/python manage.py collectstatic --noinput
```

Critere de passage:

- [ ] check --deploy acceptable pour la politique securite cible.
- [ ] Logs event/alert visibles en centralisation.
- [ ] Health endpoint OK.

## T-12h a T-4h - Validation juridique et go readiness

- [ ] Valider checklist legal complete dans docs/legal/legal-review-checklist.md.
- [ ] Completer champs obligatoires restants (RCS, TVA, siege, hebergeur, juridiction).
- [ ] Valider document pret signature docs/legal/legal-pages-ready-signature.md.
- [ ] Validation formelle Legal + Product + Tech + Ops.

Critere de passage:

- [ ] 0 champ legal critique manquant.
- [ ] Accord explicite des 4 responsables (Legal/Product/Tech/Ops).

## T-4h a T0 - Go/No-Go final

- [ ] Re-run check + tests critiques rapides.
- [ ] Verifier migrations prêtes et sauvegarde base effectuee.
- [ ] Verifier plan rollback pret et teste sur papier.
- [ ] Tenir meeting Go/No-Go (max 15 min) avec decision tracee.

Commandes:

```bash
cd /home/debian/mooviogo-dev
/home/debian/mooviogo-dev/.venv/bin/python manage.py check
/home/debian/mooviogo-dev/.venv/bin/python -m pytest apps/tickets/tests/test_ticket_validation.py apps/reports/tests/test_report_moderation.py apps/reports/tests/test_report_observability.py apps/web/tests/test_password_reset_flow.py apps/web/tests/test_admin_analytics_finance.py -q
```

## Decision Gate Go/No-Go

GO uniquement si tout est vrai:

- [ ] Aucune alerte Sev-1/Sev-2 ouverte.
- [ ] Tests critiques verts.
- [ ] Migrations valides + backup confirme.
- [ ] Observabilite active (event/alert logs + supervision).
- [ ] Validation juridique formelle recue.
- [ ] Plan rollback executable en moins de 15 minutes.

NO-GO si au moins un point suivant:

- [ ] Echec test critique ou bug Sev-1/Sev-2 non corrige.
- [ ] Champ legal obligatoire non valide.
- [ ] Migration risquee non couverte par rollback clair.
- [ ] Monitoring/alerting non operationnel.

## Runbook de release (jour J)

1. [ ] Snapshot/backup base de donnees.
2. [ ] Deploiement applicatif.
3. [ ] Migration schema.
4. [ ] Health check immediat.
5. [ ] Smoke tests API et web.
6. [ ] Verification logs event/alert sur 30 minutes.
7. [ ] Declaration GO definitive.

## Plan de rollback

Declenchement rollback immediat si:

- [ ] Incident Sev-1 post-release.
- [ ] Erreur migration avec impact donnees.
- [ ] Degradation majeure sur scan/moderation/auth.

Actions rollback:

1. [ ] Stop trafic vers version courante (ou maintenance courte).
2. [ ] Redeployer version precedente.
3. [ ] Restaurer base selon procedure validee.
4. [ ] Rejouer health + smoke tests minimum.
5. [ ] Publier postmortem initial sous 24h.

## PV de decision Go/No-Go (a remplir)

- Date/heure decision:
- Decision: GO / NO-GO
- Participants:
- Risques acceptes:
- Actions post-decision:
- Heure effective de mise en prod:
