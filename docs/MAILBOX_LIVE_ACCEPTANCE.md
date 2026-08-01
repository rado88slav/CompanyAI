# Controlled Generic SMTP/IMAP Mailbox Acceptance

This guide prepares one or two real mailboxes for operator-driven acceptance.
Do not paste passwords into chat, shell commands, screenshots, tickets or docs.

Dashboard sequence:

1. Open `http://localhost:8080`.
2. Sign in as an administrator with access to the target company.
3. Open Provider Connections.
4. Use Controlled live acceptance.
5. Add or select a Generic SMTP/IMAP mailbox.
6. Enter non-secret settings:
   - email address;
   - sender display name;
   - username;
   - SMTP host;
   - SMTP port;
   - SMTP security;
   - IMAP host;
   - IMAP port;
   - IMAP security;
   - IMAP folder;
   - optional reply-to address.
7. Enter the mailbox password only in the masked password field.
8. Save the mailbox.
9. Run Test SMTP.
10. Run Test IMAP.
11. Activate only after both tests show success.

Common port guidance:

- SMTP SSL/TLS commonly uses `465`.
- SMTP STARTTLS commonly uses `587`.
- IMAP SSL/TLS commonly uses `993`.
- IMAP STARTTLS commonly uses `143`.

Use the mailbox provider's official settings rather than guessing.

Safety guarantees for the connection tests:

- SMTP test authenticates and verifies TLS without sending email.
- IMAP test authenticates, verifies TLS and opens the configured folder read-only.
- IMAP test does not mark, move, delete or change messages.
- The saved password is encrypted and is not returned or redisplayed.
- The tests do not start campaigns, scheduler workers or bulk actions.

Stop points:

- Stop before entering credentials until automated checks are complete.
- Stop before any explicit one-message send test.
- Stop before any real outreach campaign.
