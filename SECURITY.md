# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it through
[GitHub Security Advisories](https://github.com/Lenivvenil/archi2likec4/security/advisories/new).

**Do not** open a public issue for security vulnerabilities.

We will acknowledge your report within 72 hours and aim to release a fix
within 14 days for critical issues.

## Scope

archi2likec4 processes XML files from coArchi repositories. Key areas:

- **XML parsing** — we use `defusedxml` to prevent XXE and entity expansion attacks.
- **File generation** — output is written only to the configured `output_dir`.
- **Web UI** (optional) — Flask-based dashboard with CSRF protection; intended for local use only.

## Dependencies

We pin upper bounds on all runtime dependencies and monitor advisories via Dependabot.
