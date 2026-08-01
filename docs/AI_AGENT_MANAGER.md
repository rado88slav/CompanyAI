# AI Agent Manager

AI Agent Manager is a preview-only control surface for safe CompanyAI agents.

What works today:

- list CompanyAI-managed agents;
- create the built-in Email Operations Preview Agent;
- inspect the structured prompt/profile before activation;
- edit safe company instructions;
- activate and deactivate the preview agent;
- run synthetic preview tasks;
- see structured proposals, authorization status and audit correlation.

What is preview-only:

- scheduler action previews;
- synthetic reply drafts;
- unsubscribe classification;
- campaign pause proposals;
- forbidden send denial.

What is not implemented:

- unrestricted autonomous execution;
- OpenClaw runtime execution;
- external model calls;
- real mailbox reading;
- provider execution from Agent Manager;
- email send or campaign launch.

Security boundaries:

- Agent profile sections are structured, not a single uncontrolled prompt.
- Agent instructions reject secret-like input.
- The preview runtime is deterministic local code.
- Forbidden sends are denied in backend code before provider execution.
- Approval Manager evaluation is used for proposals that could later become external actions.
- No provider credential, ciphertext, keyring, token, shell, Docker socket, host filesystem or database connection is exposed to the agent.

Synthetic tasks:

1. Preview the next 10 scheduled email actions.
2. Draft a follow-up for a synthetic interested reply.
3. Classify a synthetic unsubscribe reply.
4. Propose pausing a synthetic campaign.
5. Attempt a forbidden send action.

Expected result:

- allowed preview tasks return structured proposals;
- pause proposals show Approval Manager status;
- forbidden send returns `blocked`;
- `external_action_taken` is always `false`;
- `provider_execution_created` is always `false`.
