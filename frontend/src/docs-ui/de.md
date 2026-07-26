---
slug: getting-started
title: Erste Schritte
category: Grundlagen
summary: Sicher anmelden, ein Unternehmen auswählen, navigieren und die Sitzung beenden.
keywords: login, unternehmen, navigation, logout, sitzung
related: dashboard,companies,security
---
# Erste Schritte
CompanyAI ist ein unternehmensbezogenes Operations-Dashboard. Melden Sie sich mit einem genehmigten Administratorkonto an und wählen Sie danach das Unternehmen, für das Sie arbeiten dürfen.
## Schritte
1. Öffnen Sie das Dashboard und melden Sie sich an.
2. Wählen Sie das aktive Unternehmen in der oberen Leiste.
3. Nutzen Sie die Seitenleiste für Overview, Activity, System Status, Providers, Agent, Email, Approvals oder Documentation.
4. Nutzen Sie den Breadcrumb Trail in der oberen Leiste, um Ihre Position zu bestätigen.
5. Verwenden Sie Logout, wenn Sie den Arbeitsplatz verlassen.
> [!TIP] Ist ein gespeichertes Unternehmen nicht mehr verfügbar, wählt CompanyAI ein sicher zugängliches Unternehmen.
> [!WARNING] Teilen Sie niemals Passwörter, Tokens oder kopierte Browser-Speicherwerte.
## Häufige Fehler
- Im falschen Unternehmen arbeiten.
- Read-only Seiten als Live-Steuerung verstehen.
- Eine Sitzung auf einem gemeinsam genutzten Rechner offen lassen.
## Verwandte Seiten
- Dashboard
- Companies
- Security

---
slug: dashboard
title: Dashboard
category: Betrieb
summary: Das Operations Center und seine read-only Statussignale verstehen.
keywords: overview, health, quick actions, notifications, betrieb
related: activity-center,system-status,providers
---
# Dashboard
Die Overview-Seite ist das operative Kontrollzentrum. Sie fasst Zustand, aktuelles Unternehmen, Provider, Freigaben, E-Mail-Sichtbarkeit, Agent-Status und aktuelle Aktivität zusammen.
## Zuerst prüfen
1. System Health zeigt Backend, Datenbank, Agent, Provider, E-Mail und Storage.
2. Company Summary bestätigt Unternehmen und Kennzahlen.
3. Quick Actions öffnen wichtige Module.
4. Recent Activity führt zum Activity Center.
> [!NOTE] Overview ist read-only. Es sendet keine E-Mails, startet keine Kampagnen und verändert keine Provider.
## Best Practices
- Vor einer lokalen Validierung aktualisieren.
- Unternehmensname vor Modulwechsel prüfen.
- Activity Center für zeitliche Nachweise verwenden.

---
slug: companies
title: Companies
category: Administration
summary: Wie der aktive Unternehmenskontext alle Dashboard-Daten begrenzt.
keywords: unternehmen, membership, active company, isolation, selector
related: getting-started,security,activity-center
---
# Companies
Jeder operative Datensatz gehört zu einem Unternehmen. Der aktive Unternehmenswähler bestimmt, welche company-scoped Datensätze angefordert werden.
## Schritte
1. Melden Sie sich an.
2. Öffnen Sie den Unternehmenswähler in der oberen Leiste.
3. Wählen Sie nur Unternehmen aus der Liste Ihres Kontos.
4. Prüfen Sie nach dem Wechsel, dass die Seite neu geladen hat.
> [!WARNING] Eine veraltete oder nicht autorisierte Company ID wird vom Backend abgelehnt.
## Best Practices
- Unternehmen vor Freigaben und E-Mail-Prüfungen bestätigen.
- Für Requester und Approver unterschiedliche Administratoren nutzen.

---
slug: providers
title: Providers
category: Integrationen
summary: Provider-Verbindungen, Status und das aktuelle read-only Integrationsmodell.
keywords: provider, connection, lemlist, credential, adapter, status
related: system-status,email-campaigns,security
---
# Providers
Provider sind externe oder lokale Adapter, dargestellt über sichere company-scoped Metadaten. Die Providers-Seite zeigt konfigurierte Verbindungen und vertrauenswürdige Provider-Typen.
## Schritte
1. Öffnen Sie Provider Connections.
2. Prüfen Sie konfigurierte und aktive Verbindungen.
3. Lesen Sie Authentication Type und Capabilities.
4. Nutzen Sie System Status für die Provider-Lage.
> [!INFO] Credential-Werte werden nie angezeigt.
> [!WARNING] Live-Provider-Mutationen und reale Sends sind nicht aktiviert.
## Häufige Fehler
- Ein Catalog Entry wird mit Live-Credentials verwechselt.
- Mock/local Provider werden mit externer Zustellung verwechselt.

---
slug: agent
title: Agent
category: Automatisierung
summary: Safe read-only Agent Runtime und Tool Registry Boundary verstehen.
keywords: agent, runtime, tool registry, read-only, audit, approval
related: approvals,activity-center,security
---
# Agent
Die Agent-Seite führt deterministische interne Tools über eine kontrollierte Runtime Boundary aus. Tools sind registriert, unternehmensaktiviert und auditiert.
## Schritte
1. Öffnen Sie Agent Activity.
2. Aktivieren Sie das lokale read-only Tool, falls es fehlt.
3. Führen Sie ein read-only Tool aus.
4. Prüfen Sie Structured Result und Audit Event.
> [!TIP] Agent Runtime hat keine unrestricted shell und keinen arbitrary external HTTP access.
> [!WARNING] Künftige High-Risk Tools müssen hinter Approvals und exakten Berechtigungen bleiben.
## Best Practices
- Tool-Ergebnisse als company-scoped Nachweis behandeln.
- Agent-Aktionen später im Activity Center prüfen.

---
slug: email-campaigns
title: Email Campaigns
category: E-Mail
summary: Mock/read-only Kampagnenmodell und lokaler Test-E-Mail-Workflow.
keywords: email, campaign, mock, lemlist, inbox, approval, send
related: approvals,providers,activity-center
---
# Email Campaigns
Email Operations unterstützt lokale Test-E-Mail-Nachweise und mock/read-only Kampagnensichtbarkeit. Es sendet keine realen E-Mails und startet keine realen Kampagnen.
## Schritte
1. Öffnen Sie Email Operations.
2. Prüfen Sie importierte Inbound E-Mail.
3. Öffnen Sie Details für Proposal und Approval Context.
4. Prüfen Sie Mock Campaign Status und read-only Counts.
> [!WARNING] Explicit local test send ist deterministisch und lokal. Es ist keine externe Zustellung.
## Best Practices
- Approval State vor einem Outbound Snapshot prüfen.
- In Providers prüfen, ob überhaupt Live-Credentials existieren.

---
slug: approvals
title: Approvals
category: Governance
summary: Approval Requests, Entscheidungstrennung und unveränderbare Nachweise.
keywords: approval, decision, requester, approver, immutable, policy
related: email-campaigns,agent,security
---
# Approvals
Approvals schützen riskante Aktionen durch Trennung von Request und Decision. Das Dashboard zeigt exakten Inhalt und zulässige Entscheidungen.
## Schritte
1. Öffnen Sie Approvals.
2. Lesen Sie requested action und content genau.
3. Prüfen Sie, dass Requester und Approver unterschiedlich sind, wenn erforderlich.
4. Approve oder Reject nur bei korrektem Inhalt.
> [!WARNING] Self-approval muss blockiert bleiben.
## Best Practices
- Immutable outbound snapshots nach Approval prüfen.
- Activity Center für den Audit Trail nutzen.

---
slug: activity-center
title: Activity Center
category: Betrieb
summary: Einheitliche Timeline für Agent-, Approval-, Provider- und E-Mail-Ereignisse.
keywords: activity, timeline, audit, events, filters, details
related: dashboard,approvals,system-status
---
# Activity Center
Activity Center ist die lesbare operative Timeline. Audit Events werden als Cards mit Category, Status, Actor, Source und Safe Details normalisiert.
## Schritte
1. Öffnen Sie Activity.
2. Filtern Sie nach Category oder Severity.
3. Öffnen Sie Safe Details nur bei Bedarf.
4. Wechseln Sie zum Related Module für Kontext.
> [!INFO] Raw audit details, provider payloads und secret-like values werden nicht angezeigt.
## Best Practices
- Für Validierungsnachweise verwenden.
- Mit System Status kombinieren, wenn Sie Betriebszustand untersuchen.
## Development Data
In Development-Umgebungen kann Activity Center mit deterministischen Sample Events über `scripts/dev/seed-activity.sh` befüllt werden. Der Befehl ist development-only, company-scoped, idempotent und erzeugt keine Credentials, Provider Calls oder externe Zustellung.

---
slug: system-status
title: System Status
category: Betrieb
summary: Health Indicators für Backend, Datenbank, Provider und geplante Dienste.
keywords: system, health, readiness, backend, database, lemlist, telephony
related: dashboard,providers,activity-center
---
# System Status
System Status ist eine reine Health-Indicator-Seite. Sie zeigt Runtime Posture und markiert planned oder limited Bereiche klar.
## Schritte
1. Öffnen Sie System Status.
2. Prüfen Sie zuerst Backend und Database.
3. Prüfen Sie Providers und Agent Runtime.
4. Behandeln Sie Queue, Telephony und future AI Providers als planned, solange sie nicht healthy sind.
> [!NOTE] Diese Seite enthält keine Mutation Actions.
## Häufige Fehler
- Einen planned service als Live-Integration lesen.
- Provider Status bei E-Mail-Untersuchungen ignorieren.

---
slug: security
title: Security
category: Governance
summary: Credential Safety, Permissions, Approvals, Audit und Company Isolation.
keywords: security, credentials, permissions, audit, tokens, secrets
related: approvals,companies,providers
---
# Security
CompanyAI ist auf Company Isolation, explizite Autorisierung, sichere Credential Storage und append-only Audit Evidence ausgelegt.
## Grundregeln
1. Credentials werden nicht im Dashboard angezeigt.
2. Tokens gehören nicht in Tickets oder Dokumentation.
3. Company Context wird durch das Backend erzwungen.
4. Approval Separation schützt riskante Aktionen.
5. Audit Events bewahren Nachweise ohne Secret Payloads.
> [!WARNING] Keine Credential Entry Forms ohne genehmigten verschlüsselten Storage Flow hinzufügen.
## Best Practices
- Permissions vor Tool-Aktivierung prüfen.
- Lokale Development Credentials von echten Konten trennen.

---
slug: settings
title: Settings
category: Hilfe
summary: Lokale Dashboard Preferences, Session Actions und Documentation Shortcuts verwalten.
keywords: settings, preferences, theme, notifications, profile, language
related: getting-started,security,faq
---
# Settings
Settings ist der protected workspace für Account Context und sichere lokale Dashboard Preferences. Es sammelt keine Credentials und ändert keine Passwörter.
## Sections
1. Profile zeigt Display Name, E-Mail, Rolle und aktives Unternehmen.
2. Preferences speichert Interface Language, Documentation Language, Landing Page, Timezone, Date Format und Density lokal.
3. Appearance speichert light, dark oder system mode lokal.
4. Notifications speichert lokale Preferences für Approvals, Provider Health, Campaigns und Agent Signals.
5. Security zeigt current session context und bietet Logout.
6. Company defaults zeigt read-only company information und dashboard preference.
7. Documentation öffnet das built-in Documentation Center.
> [!WARNING] Password Change und MFA benötigen einen künftigen verified secure backend flow. Geben Sie keine Ersatzpasswörter in unsupported forms ein.
## Best Practices
- Nach Preference-Änderungen speichern.
- Documentation Language passend zum Workflow wählen.
- Settings als browser-local behandeln, bis Backend Preference Storage existiert.

---
slug: faq
title: FAQ
category: Hilfe
summary: Praktische Antworten auf häufige CompanyAI-Fragen.
keywords: faq, questions, troubleshooting, login, provider, email, agent
related: getting-started,security,system-status
---
# FAQ
## Warum sehe ich kein Unternehmen?
Ihr Konto braucht aktiven Zugriff oder Platform-Superuser-Rechte.
## Kann CompanyAI jetzt echte E-Mails senden?
Nein. Aktuelle Zustellung ist nur lokal testbar; Campaign Views sind mock oder read-only.
## Warum ist ein Provider gelistet, aber nicht aktiv?
Der Trusted Catalog kann einen Provider Type enthalten, bevor Connection oder Live Credential existieren.
## Wo sehe ich, was passiert ist?
Activity Center zeigt die lesbare Timeline; Audit Log zeigt Low-Level Audit Fields.
## Was tun bei abgelaufener Sitzung?
Melden Sie sich erneut an. Das Dashboard löscht protected context automatisch.

---
slug: local-edition
title: Local Edition Beta
category: Betrieb
summary: CompanyAI lokal auf einer Windows Workstation installieren und ausführen.
keywords: local, beta, docker, windows, backup, sandbox, install
related: getting-started,system-status,settings
---
# Local Edition Beta
CompanyAI Local Edition Beta ist für eine Windows Workstation mit Docker Desktop und WSL2 ausgelegt. Das Dashboard öffnet unter `http://localhost:8080`.
## Grundlagen
1. Kopieren Sie das Package vor der Nutzung auf die interne SSD.
2. Starten Sie mit `scripts/local/start.sh` oder dem Windows Start Wrapper.
3. Stoppen Sie mit `scripts/local/stop.sh`.
4. Erstellen Sie Backups mit `scripts/local/backup.sh`.
5. Erstellen Sie Diagnosen mit `scripts/local/diagnose.sh`.
> [!WARNING] Speichern Sie Business Data nicht dauerhaft auf einem gewöhnlichen USB Flash Drive.
## Sicherheit
LAN Access ist standardmäßig deaktiviert, Daten liegen in persistent Docker Volumes, und normale Stop-, Restart-, Rebuild- und Update-Kommandos erhalten Business Data.

---
slug: email-sandbox
title: Email Sandbox
category: Email
summary: Restricted Email Test Mode für frühe kontrollierte Outreach-Validierung.
keywords: email, sandbox, allowlist, approval, quota, emergency stop
related: email-campaigns,approvals,security
---
# Email Sandbox
Email Sandbox ist die verpflichtende Safety Boundary vor einem realen Outreach Pilot. Das Backend erzwingt Recipient Allowlists, Sender Allowlists, Quotas, Approval, Duplicate-Send Protection und Emergency Stop.
## Initiale Limits
1. Nur allowlisted team-controlled recipients.
2. Ein Recipient pro Message.
3. Fünf Messages pro Stunde.
4. Zehn Messages pro Tag.
5. `[COMPANYAI TEST]` Subject Prefix, wenn konfiguriert.
6. Keine automatic Follow-ups, Bulk Sending oder Attachments.
> [!WARNING] Verwenden Sie während Sandbox Acceptance Testing keine echten HVAC Prospects.
## Wenn ein Send abgelehnt wird
Prüfen Sie visible reason, approval state, allowlist und emergency stop. Rejections werden mit sanitized reasons auditiert.

---
slug: release-notes
title: Release Notes
category: Produkt
summary: Aktuelle product-quality Dashboard Milestones.
keywords: release, notes, changes, activity, status, documentation
related: dashboard,activity-center,system-status
---
# Release Notes
## Aktueller Dashboard Milestone
- Operations Homepage wurde zum Control Center poliert.
- Activity Center wurde als normalized read-only Timeline ergänzt.
- System Status wurde für Health Indicators only ergänzt.
- Documentation Center wurde als multilingual built-in help system ergänzt.
- Breadcrumb Navigation wurde zur protected dashboard shell ergänzt.
- Settings wurde mit safe local preference storage ergänzt.
- Development activity seed command wurde für lokales Activity Center Testing ergänzt.
- Local Edition Beta foundation wurde mit production runtime, lifecycle scripts, backup/restore foundation und backend-enforced Email Sandbox policy ergänzt.
## Safety Posture
- Keine realen E-Mail-Sends.
- Keine Campaign Launches.
- Keine Phone Calls.
- Keine paid external actions.
- Keine unrestricted shell oder arbitrary HTTP tool access.
