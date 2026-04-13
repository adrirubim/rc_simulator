# Repository Standard (adrirubim)

This repository follows the shared **repository standard** used across sibling projects (homogeneous documentation and community health files).

## Required root files

- `README.md`
- `LICENSE`
- `CHANGELOG.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SUPPORT.md`
- `REPO_STANDARD.md`

## README contract

`README.md` must keep this section order (if not applicable, keep the section and mark it **N/A**):

1. Title + tagline
2. Badges
3. Table of Contents
4. Operational Quickstart
5. Overview
6. Features
7. Tech Stack
8. Requirements
9. Installation
10. Security
11. Documentation
12. CI/CD
13. Testing
14. Architecture
15. Project Status
16. Default Users (development)
17. Useful Commands
18. Before Pushing to GitHub
19. Contributing
20. Author
21. License

## Local gate (CI parity)

The required local entrypoint is:

- `scripts/dev-verify.sh`

## GitHub UX (templates + workflows)

The repo must include:

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`

And workflows (stable filenames):

- `.github/workflows/lint.yml`
- `.github/workflows/tests.yml`
- `.github/workflows/security.yml`

