# Company AI — Codex Instructions

## Project

Company AI is a multi-company automation platform.

Current stack:

- FastAPI backend
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker Compose
- React dashboard planned
- Agent Runtime planned

Architecture:

- modular monolith
- clear API, schema, service, repository and model layers
- UUIDs are canonical identifiers
- all future company-owned data must include company isolation
- provider integrations must use abstractions
- secrets must use dedicated encrypted credential storage

Read these files before planning changes:

- docs/ARCHITECTURE.md
- docs/ROADMAP.md
- project-admin/progress.md
- project-admin/todo.md
- project-admin/decisions.md

## Environment

The repository runs inside WSL Ubuntu.

Project root:

    /home/rado/projects/company-ai

Use Docker for Python commands and tests.

Do not install or run Python directly on Windows.

## Safety Rules

Never read, print, copy, modify or expose:

- .env
- passwords
- API keys
- access tokens
- encryption keys
- private keys

The `.env.example` file may be inspected because it contains placeholders only.

Never perform these actions without explicit user approval:

- apply or roll back an Alembic migration
- create, modify or delete real database records
- run destructive SQL
- delete Docker volumes
- reset the development database
- run docker compose down with volume deletion
- modify files outside this repository
- use network access
- make a Git commit
- push to a remote repository
- rewrite Git history

Do not modify existing applied migrations unless the user explicitly approves it.

Create a new migration for schema changes.

## Working Method

Work on one clearly defined task at a time.

Before editing:

1. inspect the relevant existing code;
2. explain the proposed plan briefly;
3. identify files that will change;
4. stop and ask for approval when the requested task is planning-only.

When implementation is explicitly requested:

1. make focused changes;
2. preserve the existing architectural style;
3. avoid unrelated refactoring;
4. add or update tests;
5. run validation;
6. inspect the final diff;
7. stop before migration application, Git commit or production actions.

Do not silently change product requirements or architecture decisions.

Do not create temporary shortcuts that would require a later rewrite.

## Testing

Run backend tests through Docker.

Preferred command:

    docker run --rm \
      --user root \
      -e PIP_ROOT_USER_ACTION=ignore \
      -e PYTHONPYCACHEPREFIX=/tmp/company-ai-pycache \
      -e APP_SECRET_KEY=test-secret-key-with-at-least-32-characters \
      -e ACCESS_TOKEN_EXPIRE_MINUTES=60 \
      -v "$PWD/backend:/app:ro" \
      -w /app \
      company-ai-backend:dev \
      sh -c '
        python -m pip install --no-cache-dir -r requirements-dev.txt >/dev/null &&
        python -m compileall -q app migrations tests &&
        python -m pytest -p no:cacheprovider
      '

Also validate when relevant:

    bash -n <script>
    docker compose config --quiet
    git diff --check
    alembic heads
    alembic history

Do not apply migrations during validation.

## Git

The `main` branch must remain stable.

Before starting implementation, verify that the working tree is clean.

Do not commit automatically.

At completion, report:

- what changed;
- files changed;
- tests and commands run;
- results;
- remaining risks;
- migrations created but not applied;
- any action requiring user approval.

## Communication

Respond to the user in Bulgarian.

Code, identifiers, comments and technical documentation remain in English.

Be direct and practical.

Do not continue into the next project phase automatically.
