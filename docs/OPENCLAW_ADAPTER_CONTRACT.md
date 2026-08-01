# Future OpenClaw Adapter Contract

OpenClaw is not integrated today. CompanyAI currently provides only a
preview-only local Agent Manager runtime and this implementation-ready adapter
contract.

Required deployment boundary:

- separate Docker service;
- dedicated CompanyAI service identity;
- authenticated API access only;
- minimum exact tool permissions;
- restricted network policy;
- no Docker socket mount;
- no direct PostgreSQL/database access;
- no unrestricted host filesystem;
- no shell escape or arbitrary command execution;
- controlled secrets boundary through CompanyAI only;
- health check and restart policy;
- pinned image source and version;
- audit correlation on every task;
- prompt/profile delivery through CompanyAI APIs;
- Approval Manager enforcement before external actions;
- runtime disable/revoke procedure.

Runtime contract:

1. CompanyAI creates or selects an agent identity.
2. CompanyAI grants exact tools through Tool Registry.
3. CompanyAI delivers structured prompt/profile sections.
4. OpenClaw returns structured proposals only.
5. CompanyAI validates proposal schema and authorization.
6. CompanyAI records audit events.
7. Provider Execution remains the only path for external provider actions.

OpenClaw must never receive:

- provider credentials or keyrings;
- administrator access tokens;
- database URLs;
- Docker socket access;
- writable project filesystem access;
- unrestricted network credentials;
- bulk-recipient lists without an approved CompanyAI action.
