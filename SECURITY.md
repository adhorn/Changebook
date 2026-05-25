# Security

## Reporting vulnerabilities

If you discover a security vulnerability, please report it privately via email to **adrian.hornsby@icloud.com**. Do not open a public GitHub issue.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

You should receive a response within 48 hours.

## Current security model

Changebook is in early development (v0.1). The current authentication model uses **mock identity headers** (`X-User-Name`, `X-User-Email`) intended for local development and demos only. There is no cryptographic authentication.

**Do not deploy this to a network accessible by untrusted users without adding real authentication first.**

The codebase is designed so that swapping in real auth (e.g. Auth.js / NextAuth JWT verification) requires changing a single dependency (`backend/app/core/auth.py`) without modifying any business logic.

### Known limitations

- **No real authentication**: Identity is taken from request headers without verification
- **No rate limiting**: API endpoints have no request throttling
- **No tenant isolation**: All data is globally accessible (single-org assumption)
- **Swagger UI exposed**: API documentation is publicly accessible at `/docs`
- **Hold-point verification is trust-based**: The verifier name is typed by the operator, not cryptographically verified

These are acceptable for a local development tool and will be addressed before any production deployment.
