# Security Policy

## Supported versions

CodeStruct has not published a stable release. Security fixes are applied only to
the current `main` branch until a versioned support policy is announced.

## Reporting a vulnerability

Do not include exploit details, credentials, private source code, or sensitive
project data in a public issue. Contact the project maintainers through a private
channel already published by the maintainers, or GitHub private vulnerability
reporting if enabled after publication. No private reporting address currently
exists; do not invent one or put sensitive details in a public issue.

Include the affected revision, reproduction conditions, impact, and the minimum
detail needed to validate the report. Maintainers should acknowledge the report,
coordinate a fix and disclosure timeline privately, and credit the reporter when
requested and appropriate.

## Current security boundary

The API accepts opaque configured project IDs. Canonical roots stay server-side;
relative selections are canonicalized and containment-checked. Reparse points are
default-deny, limits/exclusions apply, and errors do not reveal private paths.
Static analysis reads source only as data and must never import or execute it.

Graphs use relative evidence and do not publish source bodies. SQLite contains
local results and an internal canonical identity; protect it as sensitive data,
never publish it, and stop the service before backup/recovery. Secrets, `.env`,
dependencies, VCS data, and generated output are excluded, but configuration
owners must still authorize only appropriate roots.

This local MVP has no user authentication. CORS is not authorization. Never expose
the backend to an untrusted/public network without authentication, transport
security, isolation, rate limiting, deployment hardening, and a separate review.
See [the security model](docs/architecture/security-model.md).
