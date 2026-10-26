# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, report
privately via GitHub's [private vulnerability reporting](../../security/advisories/new)
or email the maintainers. Include steps to reproduce and any relevant logs.

We aim to acknowledge reports within a few business days.

## Scope

This repository is a service template. When you derive a service from it, you
are responsible for its production configuration — notably:

- Setting `ENVIRONMENT=production`, `DEBUG=false`, and `DOCS_ENABLED=false`.
- Providing real `API_KEYS`, `ALLOWED_HOSTS`, and database credentials.
- Terminating TLS in front of the app (HSTS is only emitted in production).
- Using a shared/edge rate limiter when running more than one worker or replica.

The production guard in `src/core/config.py` refuses to start with several
insecure defaults, but it is not a substitute for a security review.

See [`docs/security.md`](docs/security.md) for the hardening checklist.

## Dependencies

Dependencies are audited in CI (`pip-audit`) and kept current via Dependabot.
Report a vulnerable transitive dependency the same way as above.
