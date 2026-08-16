# Security Policy

## Supported Versions

Actuate is pre-1.0 and evolving quickly. Security fixes are made against the
latest released version on PyPI (`actuate-ai`) and the `main` branch only —
older versions are not patched separately.

| Version | Supported |
| ------- | --------- |
| Latest on PyPI | ✅ |
| `master` branch  | ✅ |
| Older releases | ❌ |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report it privately through GitHub's Security Advisories:

1. Go to the **Security** tab of this repository.
2. Click **Report a vulnerability** under "Advisories."
3. Include as much detail as you can: affected version, reproduction steps,
   and potential impact.

You can expect an initial response within **5 business days**. If the issue
is confirmed, a fix will be prioritized and a coordinated disclosure timeline
will be agreed with you before any public advisory is published.

## Scope

This policy covers the `actuate` Python package, the FastAPI control console
(`actuate/api`), and the React frontend (`ui/frontend`). It does not cover
third-party model providers (OpenAI, Anthropic, NVIDIA NIM, etc.) that you
connect through Actuate — please report issues with those providers directly
to them.