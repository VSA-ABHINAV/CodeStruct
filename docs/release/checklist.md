# Release checklist

CodeStruct is currently `0.1.0.dev0`; this checklist authorizes neither a tag nor publication.

- [ ] Owner selects a license and approves license metadata.
- [ ] Owner supplies/approves maintainer identity and project URLs.
- [ ] Changelog and version are approved; CLI, API, wheel, and UI versions match.
- [ ] Backend tests/coverage, Ruff, mypy, frontend coverage/accessibility, ESLint, and build pass.
- [ ] Dependency licenses and vulnerability reports receive human review.
- [ ] Wheel/sdist verification, checksums, clean install, packaged runtime, upgrade, and rollback pass.
- [ ] Known accessibility, fault-injection, and platform limitations are accepted.
- [ ] Windows evidence is current; Linux/macOS CI has actually passed before support is claimed.
- [ ] Candidate checksum and database backup are retained for rollback.
- [ ] A release approver explicitly authorizes any tag and separate publication action.

Never upload SQLite data, analyzed graphs, environment files, or project source as release artifacts.
