---
slug: getting-started
title: Bien démarrer
category: Bases
summary: Se connecter, choisir une société, naviguer et fermer la session en sécurité.
keywords: login, société, navigation, logout, session
related: dashboard,companies,security
---
# Bien démarrer
CompanyAI est un tableau de bord opérationnel isolé par société. Connectez-vous avec un compte administrateur approuvé, puis choisissez la société autorisée.
## Étapes
1. Ouvrez le dashboard et connectez-vous.
2. Choisissez la société active dans la barre supérieure.
3. Utilisez la navigation gauche pour Overview, Activity, System Status, Providers, Agent, Email, Approvals ou Documentation.
4. Utilisez le fil d’Ariane dans la barre supérieure pour confirmer votre position.
5. Utilisez Logout lorsque vous quittez le poste.
> [!TIP] Si une société enregistrée n’est plus disponible, CompanyAI sélectionne une société accessible.
> [!WARNING] Ne partagez jamais mots de passe, tokens ou valeurs copiées du stockage navigateur.
## Erreurs fréquentes
- Travailler dans la mauvaise société.
- Lire les pages read-only comme des contrôles live.
- Laisser une session ouverte sur un poste partagé.
## Pages liées
- Dashboard
- Companies
- Security

---
slug: dashboard
title: Dashboard
category: Opérations
summary: Comprendre le centre opérationnel et ses signaux read-only.
keywords: overview, health, quick actions, notifications, opérations
related: activity-center,system-status,providers
---
# Dashboard
La page Overview est le centre opérationnel. Elle résume santé système, société courante, providers, approvals, visibilité email, statut agent et activité récente.
## À vérifier d’abord
1. System Health affiche backend, database, agent, providers, email et storage.
2. Company Summary confirme la société et les compteurs principaux.
3. Quick Actions ouvre les modules courants.
4. Recent Activity mène vers Activity Center.
> [!NOTE] Overview est read-only. Il n’envoie pas d’email, ne lance pas de campagnes et ne modifie pas les providers.
## Bonnes pratiques
- Rafraîchir avant une validation locale.
- Vérifier le nom de société avant d’ouvrir un module.
- Utiliser Activity Center comme preuve chronologique.

---
slug: companies
title: Companies
category: Administration
summary: Comment le contexte de société active limite toutes les données.
keywords: société, membership, active company, isolation, selector
related: getting-started,security,activity-center
---
# Companies
Chaque enregistrement opérationnel appartient à une société. Le sélecteur de société active contrôle les données company-scoped demandées par le dashboard.
## Étapes
1. Connectez-vous.
2. Ouvrez le sélecteur de société dans la barre supérieure.
3. Choisissez uniquement une société disponible pour votre compte.
4. Après changement, vérifiez que les données se rechargent.
> [!WARNING] Une Company ID obsolète ou non autorisée est rejetée par le backend.
## Bonnes pratiques
- Confirmer la société avant approvals ou revue email.
- Utiliser des administrators distincts pour requester et approver.

---
slug: providers
title: Providers
category: Intégrations
summary: Connexions provider, statuts et modèle d’intégration read-only actuel.
keywords: provider, connection, lemlist, credential, adapter, status
related: system-status,email-campaigns,security
---
# Providers
Les providers sont des adaptateurs externes ou locaux exposés via une metadata sûre et company-scoped. La page Providers affiche les connexions configurées et les types de providers approuvés.
## Étapes
1. Ouvrez Provider Connections.
2. Vérifiez les connexions configurées et actives.
3. Lisez authentication type et capabilities.
4. Consultez System Status pour la posture provider.
> [!INFO] Les valeurs de credentials ne sont jamais affichées.
> [!WARNING] Les mutations live provider et les vrais sends ne sont pas activés.
## Erreurs fréquentes
- Confondre une entrée catalogue avec un credential live.
- Confondre provider mock/local et livraison externe.

---
slug: agent
title: Agent
category: Automatisation
summary: Comprendre Agent Runtime read-only et la frontière Tool Registry.
keywords: agent, runtime, tool registry, read-only, audit, approval
related: approvals,activity-center,security
---
# Agent
La page Agent exécute des outils internes déterministes dans une runtime boundary contrôlée. Les tools sont enregistrés, activés par société et audités.
## Étapes
1. Ouvrez Agent Activity.
2. Activez le tool local read-only s’il manque.
3. Lancez un tool read-only.
4. Consultez le structured result et l’audit event.
> [!TIP] Agent Runtime n’a ni unrestricted shell ni arbitrary external HTTP access.
> [!WARNING] Les futurs high-risk tools doivent rester derrière approvals et permissions exactes.
## Bonnes pratiques
- Traiter la sortie tool comme une preuve company-scoped.
- Revoir les actions agent dans Activity Center.

---
slug: email-campaigns
title: Email Campaigns
category: Email
summary: Modèle mock/read-only et workflow local de test email.
keywords: email, campaign, mock, lemlist, inbox, approval, send
related: approvals,providers,activity-center
---
# Email Campaigns
Email Operations prend en charge les preuves local test email et la visibilité mock/read-only des campagnes. Il n’envoie pas de vrai email et ne lance pas de vraies campagnes.
## Étapes
1. Ouvrez Email Operations.
2. Consultez les inbound emails importés.
3. Ouvrez le détail pour proposal et approval context.
4. Vérifiez mock campaign status et read-only counts.
> [!WARNING] Explicit local test send est déterministe et local-only. Ce n’est pas une livraison externe.
## Bonnes pratiques
- Vérifier approval state avant un outbound snapshot.
- Utiliser Providers pour savoir si un live credential existe.

---
slug: approvals
title: Approvals
category: Gouvernance
summary: Approval requests, séparation de décision et preuve immuable.
keywords: approval, decision, requester, approver, immutable, policy
related: email-campaigns,agent,security
---
# Approvals
Approvals protège les actions risquées en séparant request et decision. Le dashboard affiche le contenu exact et les actions de décision autorisées.
## Étapes
1. Ouvrez Approvals.
2. Lisez précisément requested action et content.
3. Vérifiez que requester et approver sont distincts si requis.
4. Approve ou reject uniquement si le contenu est correct.
> [!WARNING] Self-approval doit rester bloqué.
## Bonnes pratiques
- Vérifier les immutable outbound snapshots après approval.
- Utiliser Activity Center pour l’audit trail.

---
slug: activity-center
title: Activity Center
category: Opérations
summary: Timeline unifiée pour événements agent, approval, provider et email.
keywords: activity, timeline, audit, events, filters, details
related: dashboard,approvals,system-status
---
# Activity Center
Activity Center est la timeline opérationnelle lisible. Elle normalise les audit events en cards avec category, status, actor, source et safe details.
## Étapes
1. Ouvrez Activity.
2. Filtrez par category ou severity.
3. Dépliez safe details seulement si nécessaire.
4. Ouvrez le related module pour plus de contexte.
> [!INFO] Raw audit details, provider payloads et valeurs secret-like ne sont pas affichés.
## Bonnes pratiques
- L’utiliser comme preuve de validation.
- Le combiner avec System Status lors d’une investigation.
## Données de développement
En environnement development, Activity Center peut être rempli avec des sample events déterministes via `scripts/dev/seed-activity.sh`. La commande est development-only, company-scoped, idempotente et ne crée aucun credential, provider call ou livraison externe.

---
slug: system-status
title: System Status
category: Opérations
summary: Health indicators pour backend, database, providers et services planifiés.
keywords: system, health, readiness, backend, database, lemlist, telephony
related: dashboard,providers,activity-center
---
# System Status
System Status est une page d’indicateurs santé uniquement. Elle montre la posture runtime et marque clairement les zones planned ou limited.
## Étapes
1. Ouvrez System Status.
2. Vérifiez d’abord Backend et Database.
3. Consultez Providers et Agent Runtime.
4. Traitez Queue, Telephony et future AI Providers comme planned sauf indication healthy.
> [!NOTE] Cette page ne contient aucune mutation action.
## Erreurs fréquentes
- Lire un planned service comme une intégration live.
- Ignorer provider status pendant une investigation email.

---
slug: security
title: Security
category: Gouvernance
summary: Credential safety, permissions, approvals, audit et company isolation.
keywords: security, credentials, permissions, audit, tokens, secrets
related: approvals,companies,providers
---
# Security
CompanyAI est conçu autour de company isolation, authorization explicite, credential storage sécurisé et audit evidence append-only.
## Règles clés
1. Les credentials ne sont pas affichés.
2. Les tokens ne vont pas dans tickets ou documentation.
3. Le company context est imposé par le backend.
4. Approval separation protège les actions risquées.
5. Les audit events gardent la preuve sans secret payloads.
> [!WARNING] N’ajoutez pas de credential-entry forms sans le flux encrypted storage approuvé.
## Bonnes pratiques
- Vérifier les permissions avant d’activer des tools.
- Séparer local development credentials et comptes réels.

---
slug: settings
title: Settings
category: Aide
summary: Gérer les préférences locales, la session et les raccourcis documentation.
keywords: settings, preferences, theme, notifications, profile, language
related: getting-started,security,faq
---
# Settings
Settings est le protected workspace pour account context et préférences locales sûres du dashboard. Il ne collecte pas de credentials et ne change pas les mots de passe.
## Sections
1. Profile affiche display name, email, role et active company.
2. Preferences stocke localement interface language, documentation language, landing page, timezone, date format et density.
3. Appearance stocke localement light, dark ou system mode.
4. Notifications stocke les préférences locales pour approvals, provider health, campaigns et agent signals.
5. Security affiche current session context et permet logout.
6. Company defaults affiche read-only company information et dashboard preference.
7. Documentation ouvre le built-in Documentation Center.
> [!WARNING] Password change et MFA nécessitent un futur verified secure backend flow. Ne saisissez aucun replacement password dans un formulaire unsupported.
## Bonnes pratiques
- Sauvegarder après modification des preferences.
- Utiliser Documentation language pour aligner le help content avec votre workflow.
- Traiter Settings comme browser-local jusqu’à l’arrivée du backend preference storage.

---
slug: faq
title: FAQ
category: Aide
summary: Réponses pratiques aux questions fréquentes.
keywords: faq, questions, troubleshooting, login, provider, email, agent
related: getting-started,security,system-status
---
# FAQ
## Pourquoi je ne vois pas une société?
Votre compte doit avoir un accès actif ou être platform superuser.
## CompanyAI peut-il envoyer de vrais emails?
Non. La livraison actuelle est local test only; les campaign views sont mock ou read-only.
## Pourquoi un provider est listé mais pas actif?
Le trusted catalog peut contenir un provider type avant une connection ou un live credential.
## Où voir ce qui s’est passé?
Activity Center donne la timeline lisible; Audit Log montre les low-level audit fields.
## Que faire si la session expire?
Reconnectez-vous. Le dashboard nettoie automatiquement le protected context.

---
slug: release-notes
title: Release Notes
category: Produit
summary: Milestones récents du dashboard product-quality.
keywords: release, notes, changes, activity, status, documentation
related: dashboard,activity-center,system-status
---
# Release Notes
## Milestone dashboard actuel
- Operations homepage transformée en control center.
- Activity Center ajouté comme normalized read-only timeline.
- System Status ajouté pour health indicators only.
- Documentation Center ajouté comme multilingual built-in help system.
- Fil d’Ariane ajouté au protected dashboard shell.
- Settings ajouté avec safe local preference storage.
- Development activity seed command ajouté pour tester Activity Center localement.
## Safety posture
- Aucun real email send.
- Aucun campaign launch.
- Aucun phone call.
- Aucune paid external action.
- Aucun unrestricted shell ou arbitrary HTTP tool access.
