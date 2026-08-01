---
slug: getting-started
title: Първи стъпки
category: Основи
summary: Влезте безопасно, изберете компания и работете в правилния контекст.
keywords: вход, компания, навигация, изход, сесия
related: dashboard,companies,security
---
# Първи стъпки
CompanyAI е оперативен dashboard с изолация по компания. Започнете с вход чрез одобрен administrator account и изберете компанията, с която имате право да работите.
## Стъпки
1. Отворете dashboard-а и влезте.
2. Изберете активна компания от горната лента.
3. Използвайте лявата навигация за Overview, Activity, System Status, Providers, Agent, Email, Approvals или Documentation.
4. Използвайте breadcrumbs в горната лента, за да потвърдите къде се намирате.
5. Използвайте Logout, когато приключите.
> [!TIP] Ако запазена компания вече не е достъпна, CompanyAI избира първата компания, до която имате право.
> [!WARNING] Не споделяйте пароли, tokens или стойности от browser storage.
## Чести грешки
- Работа в грешна компания.
- Приемане на read-only страници за live provider контроли.
- Оставена отворена сесия на споделена development машина.
## Свързани страници
- Dashboard
- Companies
- Security

---
slug: dashboard
title: Dashboard
category: Операции
summary: Разберете operational control center-а и неговите read-only health signals.
keywords: overview, health, quick actions, notifications, операции
related: activity-center,system-status,providers
---
# Dashboard
Overview е оперативният център. Той обобщава health, текуща компания, providers, approvals, email visibility, agent status и recent activity.
## Първо проверете
1. System Health показва backend, database, agent, providers, email и storage.
2. Company Summary потвърждава избраната компания и ключови броячи.
3. Quick Actions отварят основни модули.
4. Recent Activity води към Activity Center.
> [!NOTE] Overview е read-only. Не изпраща email, не стартира campaigns и не променя providers.
## Добри практики
- Refresh преди local validation.
- Потвърдете името на компанията преди работа.
- Използвайте Activity Center за хронологични доказателства.

---
slug: companies
title: Companies
category: Администрация
summary: Как active company context ограничава всички dashboard данни.
keywords: компания, membership, active company, isolation, selector
related: getting-started,security,activity-center
---
# Companies
Всеки operational record в CompanyAI принадлежи на компания. Active company selector-ът определя кои company-scoped записи се заявяват.
## Стъпки
1. Влезте в dashboard-а.
2. Отворете company selector-а в горната лента.
3. Изберете само компания от списъка за вашия account.
4. След смяна проверете, че страницата е презаредила данните.
> [!WARNING] Невалиден или неоторизиран company ID се отхвърля от backend-а.
## Добри практики
- Потвърдете компанията преди approvals или email workflow review.
- Използвайте различни administrators за requester и approver сценарии.

---
slug: providers
title: Providers
category: Интеграции
summary: Преглед на provider connections, статуси и текущия read-only integration model.
keywords: provider, connection, lemlist, credential, adapter, status
related: system-status,email-campaigns,security
---
# Providers
Providers са външни или local adapters, представени чрез безопасна company-scoped metadata. Providers страницата показва configured connections и trusted provider types.
## Стъпки
1. Отворете Provider Connections.
2. Проверете configured и active connection броя.
3. Прегледайте authentication type и capabilities.
4. Използвайте System Status за provider posture.
> [!INFO] Credential values никога не се визуализират.
## Generic SMTP/IMAP mailbox
1. Изберете Add email mailbox.
2. Въведете non-secret настройки: email address, sender name, username, SMTP и IMAP hosts, ports, security modes и IMAP folder.
3. Въведете password само в masked password field.
4. Запазете mailbox-а, после стартирайте Test SMTP и Test IMAP.
5. Activate е позволено само след успешни два теста.
> [!WARNING] SMTP тестът не изпраща email. IMAP тестът отваря configured folder read-only и не променя messages.
## Troubleshooting
- DNS failure: проверете host name.
- Connection failure или timeout: проверете port, firewall и network access.
- TLS failure: използвайте валиден trusted certificate. Invalid certificates не могат да се приемат.
- Authentication failure: проверете username и password, без да поставяте secrets в logs.
- Folder not found: проверете IMAP folder, обикновено INBOX.
## Чести грешки
- Да се мисли, че catalog entry означава live credential.
- Смесване на mock/local provider с external delivery.

---
slug: agent
title: Agent
category: Автоматизация
summary: Safe read-only Agent Runtime и Tool Registry boundary.
keywords: agent, runtime, tool registry, read-only, audit, approval
related: approvals,activity-center,security
---
# Agent
Agent страницата изпълнява deterministic internal tools през контролиран runtime boundary. Tools са registered, company-enabled и audited.
## Стъпки
1. Отворете Agent Activity.
2. Enable-нете local read-only tool, ако липсва.
3. Стартирайте read-only tool.
4. Прегледайте structured result и audit event.
> [!TIP] Agent Runtime няма unrestricted shell и няма arbitrary external HTTP access.
> [!WARNING] Бъдещи high-risk tools трябва да останат зад approvals и exact permissions.
## Добри практики
- Третирайте output-а като company-scoped evidence.
- Проверявайте agent actions в Activity Center.

---
slug: email-campaigns
title: Email Campaigns
category: Email
summary: Mock/read-only email campaign модел и local test email workflow.
keywords: email, campaign, mock, lemlist, inbox, approval, send
related: approvals,providers,activity-center
---
# Email Campaigns
Email Operations поддържа local test email evidence и mock/read-only campaign visibility. Не изпраща реален email и не стартира реални campaigns.
## Стъпки
1. Отворете Email Operations.
2. Прегледайте imported inbound email.
3. Отворете detail за proposal и approval context.
4. Проверете mock campaign status и read-only counts.
> [!WARNING] Explicit local test send е deterministic и local-only. Не е external delivery.
## Добри практики
- Проверете approval state преди outbound snapshot.
- В Providers вижте дали изобщо има live credential.

---
slug: approvals
title: Approvals
category: Governance
summary: Approval requests, decision separation и immutable evidence.
keywords: approval, decision, requester, approver, immutable, policy
related: email-campaigns,agent,security
---
# Approvals
Approvals защитават рискови действия чрез separation между request и decision. Dashboard-ът показва exact approval content и decision actions, когато са позволени.
## Стъпки
1. Отворете Approvals.
2. Прочетете exact requested action и content.
3. Потвърдете, че requester и approver са различни administrators, когато е нужно.
4. Approve или reject само ако content-ът е правилен.
> [!WARNING] Self-approval трябва да остане blocked.
## Добри практики
- Проверявайте immutable outbound snapshots след approval.
- Използвайте Activity Center за audit trail.

---
slug: activity-center
title: Activity Center
category: Операции
summary: Unified chronological timeline за agent, approval, provider и email events.
keywords: activity, timeline, audit, events, filters, details
related: dashboard,approvals,system-status
---
# Activity Center
Activity Center е четимата operational timeline страница. Тя нормализира audit events в cards с category, status, actor, source и safe details.
## Стъпки
1. Отворете Activity.
2. Филтрирайте по category или severity.
3. Разгънете safe details само при нужда.
4. Отворете related module за повече context.
> [!INFO] Raw audit details, provider payloads и secret-like values не се показват.
## Добри практики
- Използвайте за validation evidence.
- Комбинирайте със System Status при investigation.
## Development data
В development среда Activity Center може да се попълни с deterministic sample events чрез `scripts/dev/seed-activity.sh`. Командата е development-only, company-scoped, idempotent и не създава credentials, provider calls или external delivery.

---
slug: system-status
title: System Status
category: Операции
summary: Health indicators за backend, database, providers и planned services.
keywords: system, health, readiness, backend, database, lemlist, telephony
related: dashboard,providers,activity-center
---
# System Status
System Status е страница само за health indicators. Тя показва runtime posture и ясно маркира planned или limited areas.
## Стъпки
1. Отворете System Status.
2. Първо проверете Backend и Database.
3. Прегледайте Providers и Agent Runtime.
4. Третирайте Queue, Telephony и future AI Providers като planned, освен ако не са healthy.
> [!NOTE] Тази страница няма mutation actions.
## Чести грешки
- Planned service да се чете като live integration.
- Да се игнорира provider status при email investigation.

---
slug: security
title: Security
category: Governance
summary: Credential safety, permissions, approvals, audit и company isolation.
keywords: security, credentials, permissions, audit, tokens, secrets
related: approvals,companies,providers
---
# Security
CompanyAI е проектиран около company isolation, explicit authorization, safe credential storage и append-only audit evidence.
## Основни правила
1. Credentials не се визуализират.
2. Tokens не се копират в tickets или docs.
3. Company context се налага от backend-а.
4. Approval separation пази рисковите действия.
5. Audit events пазят evidence без secret payloads.
> [!WARNING] Не добавяйте credential-entry forms без approved encrypted storage flow.
## Добри практики
- Проверявайте permissions преди tools.
- Дръжте local development credentials отделно от real accounts.

---
slug: settings
title: Settings
category: Помощ
summary: Управление на local dashboard preferences, session actions и documentation shortcuts.
keywords: settings, preferences, theme, notifications, profile, language
related: getting-started,security,faq
---
# Settings
Settings е protected workspace за account context и безопасни local dashboard preferences. Не събира credentials и не сменя passwords.
## Sections
1. Profile показва display name, email, role и active company.
2. Preferences пази interface language, documentation language, landing page, timezone, date format и density локално.
3. Appearance пази light, dark или system mode локално.
4. Notifications пази local preferences за approvals, provider health, campaigns и agent signals.
5. Security показва current session context и позволява logout.
6. Company defaults показва read-only company information и dashboard preference.
7. Documentation отваря built-in Documentation Center.
> [!WARNING] Password change и MFA изискват бъдещ verified secure backend flow. Не въвеждайте replacement passwords в unsupported form.
## Добри практики
- Save след промяна на preferences.
- Използвайте Documentation language, за да съвпада help content с workflow-а ви.
- Третирайте settings като browser-local, докато няма backend preference storage.

---
slug: faq
title: FAQ
category: Помощ
summary: Практични отговори за чести въпроси.
keywords: faq, questions, troubleshooting, login, provider, email, agent
related: getting-started,security,system-status
---
# FAQ
## Защо не виждам компания?
Account-ът ви трябва да има active access или да сте platform superuser.
## Може ли CompanyAI да изпраща реален email?
Не. Текущата delivery е local test only, а campaign views са mock или read-only.
## Защо provider е listed, но не active?
Trusted catalog може да съдържа provider type преди company connection или live credential.
## Къде да проверя какво се е случило?
Activity Center е четимата timeline страница; Audit Log показва low-level audit fields.
## Какво да правя при expired session?
Влезте отново. Dashboard-ът чисти protected context автоматично.

---
slug: local-edition
title: Local Edition Beta
category: Операции
summary: Инсталиране и локално стартиране на CompanyAI върху Windows workstation.
keywords: local, beta, docker, windows, backup, sandbox, install
related: getting-started,system-status,settings
---
# Local Edition Beta
CompanyAI Local Edition Beta е предназначен за Windows workstation с Docker Desktop и WSL2. Dashboard-ът се отваря на `http://localhost:8080`.
## Основни действия
1. Копирайте package-а на internal SSD преди употреба.
2. Стартирайте със `scripts/local/start.sh` или Windows Start wrapper.
3. Спрете със `scripts/local/stop.sh`.
4. Направете backup със `scripts/local/backup.sh`.
5. Създайте диагностика със `scripts/local/diagnose.sh`.
> [!WARNING] Не пазете business data постоянно върху обикновена USB flash drive.
## First run
Ако няма administrator, dashboard-ът показва setup-required wizard. Завършете го еднократно; няма default password.
## Backups
Database backups са manual и checksum-protected. Optional encrypted configuration backup е наличен само когато operator подаде passphrase за конкретната команда.
## Безопасност
LAN access е изключен по подразбиране, данните са в persistent Docker volumes, а нормални stop, restart, rebuild и update команди пазят business data.

---
slug: email-sandbox
title: Email Sandbox
category: Email
summary: Restricted email test mode за ранна контролирана outreach проверка.
keywords: email, sandbox, allowlist, approval, quota, emergency stop
related: email-campaigns,approvals,security
---
# Email Sandbox
Email Sandbox е задължителната safety boundary преди реален outreach pilot. Backend-ът enforcement-ва recipient allowlists, sender allowlists, quotas, approval, duplicate-send protection и emergency stop.
## Начални лимити
1. Само allowlisted team-controlled recipients.
2. Един recipient на message.
3. Пет messages на час.
4. Десет messages на ден.
5. `[COMPANYAI TEST]` subject prefix, когато е configured.
6. Няма automatic follow-ups, bulk sending или attachments.
> [!WARNING] Не използвайте реални HVAC prospects по време на sandbox acceptance testing.
## Ако send бъде rejected
Проверете visible reason, approval state, allowlist и emergency stop. Rejections се audit-ват със sanitized reasons.

---
slug: release-notes
title: Release Notes
category: Product
summary: Последни product-quality dashboard milestones.
keywords: release, notes, changes, activity, status, documentation
related: dashboard,activity-center,system-status
---
# Release Notes
## Текущ dashboard milestone
- Operations homepage е polish-нат като control center.
- Activity Center е добавен като normalized read-only timeline.
- System Status е добавен за health indicators only.
- Documentation Center е добавен като multilingual built-in help system.
- Breadcrumb navigation е добавена към protected dashboard shell.
- Settings е добавен със safe local preference storage.
- Development activity seed command е добавена за local Activity Center testing.
- Local Edition Beta foundation е добавен с production runtime, lifecycle scripts, backup/restore foundation, setup-required detection и backend-enforced Email Sandbox policy.
## Safety posture
- Няма real email sends.
- Няма campaign launches.
- Няма phone calls.
- Няма paid external actions.
- Няма unrestricted shell или arbitrary HTTP tool access.
