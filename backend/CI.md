# Backend continuous integration

The GitHub Actions workflow is [Backend CI](../.github/workflows/backend-ci.yml). It runs on pull requests targeting `dev` or `main`, pushes to those branches, and manual dispatch. Required checks run for every matching event without path filters.

## Checks

| Check | Behavior |
| --- | --- |
| Backend quality | Ruff lint, formatting, and Pyright |
| Backend unit tests | pytest on Python 3.12, 3.13, and 3.14 |
| Backend dependency audit | pip-audit checks installed runtime and development dependencies |
| Repository secret scan | Gitleaks scans fetched Git history with findings redacted |
| Backend CI passed | Succeeds only when all preceding jobs succeed |

No PostgreSQL service, database connection check, AI credentials, or deployment secrets are used. Current tests construct connection configuration or mock database behavior without connecting. Keep future database integration tests separate from this unit-test suite.

Jobs install dependencies using `uv sync --locked`. CI pins uv and external action revisions, caches dependencies using the lockfile, uses read-only repository permissions, disables persisted checkout credentials, sets timeouts, and cancels superseded runs. Gitleaks is pinned and its release archive is checked against the published release checksum. Fork pull requests execute without privileged deployment credentials.

## Local verification

From `backend/`:

```bash
make sync
make check
make audit
make pre-commit
```

`make audit` queries a vulnerability service and requires network access. Pre-commit may download its hook environments. Its local secret hook and CI's full-history scan have different scopes. Audit or scanning failures must be investigated; do not suppress failures globally. Any approved vulnerability exception should have a specific identifier, rationale, and review date.

## GitHub setup

1. Open a pull request with this workflow targeting `dev` or `main` and confirm all jobs run successfully.
2. Protect both branches and select **Backend CI passed** as a required status check once GitHub has observed it.
3. Require pull requests, resolve conversations before merging, and keep force pushes and branch deletion disabled.
4. Require approving reviews when another reviewer is available. Avoid requiring a second reviewer for solo development.

The manual trigger is normally discoverable in GitHub's Actions UI after the workflow exists on the default branch. Changes to `uv.lock`, action SHAs, uv, and pre-commit hook versions should be reviewed and kept consistent.

## Later validation and deployment

CI does not currently validate PostgreSQL queries or migrations. Verify them against a separate local test database when those features are introduced.

Deployment automation follows the hosting decision. Plan separate staging/production environments, environment-scoped credentials, a tested immutable artifact, controlled migrations, post-deployment health checks, serialized deployment jobs, and a rollback procedure. This workflow does not deploy the application.
