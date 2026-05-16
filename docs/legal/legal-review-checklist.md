# Checklist revue juridique - Mooviogo

Date: 2026-05-16
Portee: pages legales rendues via apps/web/views.py (_LEGAL_PAGES)
Objectif: valider la conformite avant mise en production.

## Pre-remplissage automatique (depuis le repo)

- Contact legal detecte: [contact@mooviogo.fr](mailto:contact@mooviogo.fr)
- Contact public legal detecte dans pages: [contact@mooviogo.fr](mailto:contact@mooviogo.fr)
- Contexte d'hebergement detecte: OVHcloud - OVH SAS, 2 rue Kellermann, 59100 Roubaix, France
- Environnements detectes: development/production (Django settings)
- Version proposee pour publication: v1.0
- Date d'entree en vigueur proposee: 2026-05-16

Note: une partie des informations societaires est desormais presente dans les pages legales (entite, forme, siege, hebergeur, contact). Les references RCS/TVA restent a confirmer.

## 1. Informations societes et mentions legales

- [ ] Raison sociale exacte verifiee.
- [ ] Forme juridique verifiee (SAS, SARL, etc.).
- [ ] Capital social renseigne.
- [ ] Adresse du siege social renseignee.
- [ ] Numero RCS et ville du greffe renseignes.
- [ ] Numero de TVA intracommunautaire renseigne (si applicable).
- [ ] Directeur de publication nomme.
- [ ] Coordonnees de contact legal conformes.
- [ ] Hebergeur identifie avec denomination + adresse + contact.

## 2. CGU - Conditions Generales d'Utilisation

- [ ] Perimetre du service juridiquement precise (intermediaire, places de marche, reservation).
- [ ] Conditions d'inscription et majorite precisees.
- [ ] Regles de conduite et contenus interdits completees.
- [ ] Clauses de moderation/suspension juridiquement validees.
- [ ] Regime de responsabilite de la plateforme valide.
- [ ] Regles de preuve (logs, traces) mentionnees si necessaire.
- [ ] Droit applicable et juridiction competentes valides.
- [ ] Mecanisme de modification des CGU (information prealable) explicite.

## 3. Politique de confidentialite (RGPD)

- [ ] Responsable de traitement identifie.
- [ ] Coordonnees DPO renseignees (ou mention absence DPO si non obligatoire).
- [ ] Finalites de traitement completees et exactes.
- [ ] Bases legales associees a chaque finalite validees.
- [ ] Categories de donnees personnelles exhaustives.
- [ ] Destinataires et sous-traitants listables et valides.
- [ ] Transferts hors UE statues et garanties mentionnees (si applicable).
- [ ] Durees de conservation par type de donnees precisees.
- [ ] Droits RGPD (acces, rectification, effacement, opposition, limitation, portabilite) operables.
- [ ] Modalites d'exercice des droits (email/process interne/SLA) confirmees.
- [ ] Droit d'introduire une reclamation CNIL mentionne.
- [ ] Politique de securite coherente avec les mesures techniques reelles.

## 4. Cookies / traceurs

- [ ] Distinction cookies strictement necessaires vs optionnels.
- [ ] Liste des cookies/SDK par finalite disponible (nom, duree, fournisseur).
- [ ] Consentement prealable pour cookies non essentiels verifie.
- [ ] Mecanisme de retrait du consentement aussi simple que l'acceptation.
- [ ] Preuve du consentement (journalisation) conforme.

## 5. CGV partenaires

- [ ] Statut juridique de la relation plateforme/partenaire precise.
- [ ] Conditions de publication d'offres et obligations qualite completees.
- [ ] Regles de prix, commissions, taxes, frais PSP formalisees.
- [ ] Facturation, periodicite et justificatifs de commissions valides.
- [ ] SLA support partenaire et gestion litiges formalises.
- [ ] Conditions de suspension/resiliation partenaire juridiquement robustes.

## 6. Annulation et remboursement

- [ ] Regles d'annulation par type d'offre (sortie, event, restaurant, activite) explicites.
- [ ] Delais, penalites et cas de force majeure clairement definis.
- [ ] Delais de remboursement annonces conformes a la pratique PSP/banque.
- [ ] Processus de contestation (preuves, delais, canal) valide.
- [ ] Cohabitation B2C / B2B verifiee dans les regles.

## 7. FAQ / contact / support

- [ ] FAQ alignee avec les textes contractuels (pas de contradiction).
- [ ] Adresse de contact unique operationnelle et monitorable.
- [ ] Delais de reponse internes definis.
- [ ] Escalade moderation/securite formalisee.

## 8. Preuve et gouvernance documentaire

- [ ] Numero de version legal attribue (v1.0, v1.1, etc.).
- [ ] Historique de modifications tenu.
- [ ] Date d'entree en vigueur definie.
- [ ] Strategie de notification des utilisateurs en cas de mise a jour majeure.
- [ ] Archivage des versions precedentes accessible en interne.

## 9. Checks techniques de coherence (avec le code)

- [ ] Slugs legaux exposes et links frontend verifies.
- [ ] Rendue template legale correcte (sans erreurs HTML).
- [ ] Cohérence avec le flux auth/moderation/paiement reel du produit.
- [ ] Cohérence avec les nouvelles mesures securite (rate limiting, alerting, logs).

## 10. Go/No-Go pre-production

- [ ] Validation juriste externe recue (nom + date).
- [ ] Validation produit/ops recue.
- [ ] Ticket de publication legal ferme.
- [ ] Plan de correction post-audit etabli si reserves.

## Informations a completer avant validation finale

- Entite legale exacte: OUTLY [A CONFIRMER]
- Forme juridique: SAS [A CONFIRMER]
- Siege social: 82 RT de Montrigond, 73700 Bourg-Saint-Maurice, France [A CONFIRMER]
- RCS/TVA: [A COMPLETER]
- Directeur de publication: Anthony Asole [A CONFIRMER]
- Hebergeur legal: OVHcloud - OVH SAS, 2 rue Kellermann, 59100 Roubaix, France, 09 72 10 10 07 [A CONFIRMER]
- DPO/Contact RGPD: [contact@mooviogo.fr](mailto:contact@mooviogo.fr) [A CONFIRMER]
- Juridiction contractuelle: droit francais, juridictions francaises competentes [A CONFIRMER]
- Version legale: v1.0 [A CONFIRMER]
- Date d'entree en vigueur: 2026-05-16 [A CONFIRMER]
