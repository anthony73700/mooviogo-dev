# Plan 48h Go/No-Go - Version assignee (RACI)

Date: 2026-05-15
Reference: docs/release/go-no-go-48h.md

## Legende RACI

- R = Responsible (execute)
- A = Accountable (valide final)
- C = Consulted (contribution)
- I = Informed (information)

## Equipe

- RM = Release Manager
- TL = Tech Lead
- QA = QA Lead
- OPS = Ops/Infra
- LEGAL = Legal/Compliance
- PROD = Product Owner

## T-48h a T-36h - Gel fonctionnel + verification de base

| Action | R | A | C | I | Deadline | Critere de sortie |
| --- | --- | --- | --- | --- | --- | --- |
| Geler les features | RM | PROD | TL | QA, OPS, LEGAL | T-48h | Annonce de freeze partagee |
| Verifier branche/changelog | TL | RM | PROD | QA | T-46h | Changelog final signe |
| Verifier migrations | TL | TL | OPS | RM | T-44h | showmigrations coherent |
| Executer `manage.py check` | TL | TL | QA | RM | T-42h | 0 erreur bloquante |
| Executer tests critiques | QA | QA | TL | RM | T-40h | Suite verte |

## T-36h a T-24h - Recette fonctionnelle ciblee

| Action | R | A | C | I | Deadline | Critere de sortie |
| --- | --- | --- | --- | --- | --- | --- |
| Recette scan QR operateur | QA | QA | TL | RM | T-34h | 100% cas critiques ok |
| Recette moderation signalements | QA | QA | TL | RM, LEGAL | T-32h | Actions assign/resolve/ban/suspend OK |
| Recette reset password | QA | QA | TL | RM | T-30h | Email + token confirmes |
| Recette analytics admin + CSV | QA | QA | TL, PROD | RM | T-28h | KPI + export conformes |
| Recette pages legales (slugs+rendu) | QA | LEGAL | TL | RM, PROD | T-26h | Tous slugs accessibles |

## T-24h a T-12h - Pre-prod, securite, observabilite

| Action | R | A | C | I | Deadline | Critere de sortie |
| --- | --- | --- | --- | --- | --- | --- |
| Verifier variables env production | OPS | OPS | TL | RM | T-22h | Secrets/env valides |
| Verifier backend email production | OPS | OPS | TL | RM, QA | T-20h | Envoi test confirme |
| Verifier throttling endpoints sensibles | TL | TL | QA | RM | T-18h | Limites actives et testees |
| Verifier logs observabilite event/alert | OPS | OPS | TL | RM | T-16h | Logs visibles en supervision |
| Verifier health endpoint | OPS | OPS | TL | RM | T-14h | Health 200/ok |
| Executer `manage.py check --deploy` | TL | TL | OPS | RM | T-12h | Resultat acceptable |

## T-12h a T-4h - Validation juridique et readiness

| Action | R | A | C | I | Deadline | Critere de sortie |
| --- | --- | --- | --- | --- | --- | --- |
| Completer checklist legal | LEGAL | LEGAL | PROD, RM | TL, OPS | T-10h | 0 champ obligatoire manquant |
| Completer infos societe obligatoires | LEGAL | LEGAL | PROD | RM | T-9h | RCS/TVA/siege/hebergeur renseignes |
| Valider pack pret signature | LEGAL | LEGAL | PROD | RM | T-8h | Validation ecrite recue |
| Validation croisee Product/Tech/Ops | RM | RM | TL, OPS, PROD | LEGAL, QA | T-6h | Accord explicite 4 parties |

## T-4h a T0 - Gate de decision

| Action | R | A | C | I | Deadline | Critere de sortie |
| --- | --- | --- | --- | --- | --- | --- |
| Re-run check + tests critiques | QA | TL | OPS | RM | T-4h | Vert complet |
| Verifier backup base | OPS | OPS | TL | RM | T-3h | Backup confirme horodate |
| Verifier rollback (<15 min) | TL | TL | OPS | RM | T-2h | Procedure executable |
| Reunion Go/No-Go (15 min) | RM | RM | TL, QA, OPS, LEGAL, PROD | Stakeholders | T-1h | Decision tracee |
| Execution release | OPS | RM | TL | Tous | T0 | Deploy + smoke OK |

## Matrice risques et action immediate

| Risque | Owner | Seuil | Action immediate |
| --- | --- | --- | --- |
| Echec test critique | TL | 1 test rouge | Stop release, correctif, re-run |
| Bug Sev-1/Sev-2 ouvert | RM | >=1 | No-Go automatique |
| Champ legal obligatoire manquant | LEGAL | >=1 | No-Go jusqu'a completion |
| Observabilite non operationnelle | OPS | logs indisponibles > 10 min | No-Go + remediation infra |
| Migration a risque non couverte | TL | rollback non valide | No-Go |

## PV de decision (template)

- Date/heure: [A COMPLETER]
- Decision: GO / NO-GO
- Motifs:
- Risques acceptes:
- Actions immediates:
- Signataires: RM / TL / QA / OPS / LEGAL / PROD
