# Security

## Supported versions

Only the latest release and the current `main` branch receive security fixes.

## Reporting

Do not publish credentials, cookies, proxy URLs, or private video details in an issue. Report security problems through GitHub's private security advisory feature.

## Important boundaries

- Inputs are restricted to YouTube video IDs and `youtube.com`/`youtu.be` URLs.
- Cookies are optional and must remain local or in encrypted GitHub secrets.
- Generated result files may contain video descriptions and public comments. Review them before publishing elsewhere.
- Public issue-triggered jobs are disabled by default to prevent compute abuse. Forks can use `workflow_dispatch`; maintainers can opt in with the repository variable `ALLOW_PUBLIC_REQUESTS=true`.
