# Environment variables and secrets

## Local development

Copy `.env.example` to `.env` inside `backend/`. The example is tracked and contains only safe defaults and empty credentials. The real `.env` is ignored. Keep examples updated whenever a setting is introduced.

Run commands from `backend/`. Settings load `backend/.env` explicitly, independent of the working directory. Process environment variables override `.env` values. Restart the service after changing settings because configuration is cached.

PostgreSQL runs through `~/Documents/os-services/compose.yaml`, bound to `127.0.0.1:5432`. Its private `.env` contains `POSTGRES_PASSWORD`; the backend's private `.env` contains the matching `DB_PASSWORD`. See the [reproducible Compose setup](./README.md#local-postgresql). `make env` only copies the template and does not generate a password. Choose a password and set both files before initializing the volume. Changing these files alone does not rotate an existing PostgreSQL role password.

`CORS_ORIGINS` uses a JSON array, for example `["http://localhost:5173"]`. AI is disabled by default; credentials are unnecessary for the initial scaffold. Provider selection and model validation will be completed with the AI integration.

## Secret handling plan

1. Use separate provider keys for local development and production. Share keys through a password manager or the hosting platform's secret store.
2. Keep AI credentials exclusively in the backend. Frontend `VITE_*` variables are public configuration and must never contain AI keys.
3. In deployment and CI, inject secrets as environment variables using the platform's secret settings. Do not ship the local `.env` file or embed credentials in images, commands, source files, or fixtures.
4. Never log the settings object, authorization headers, database passwords, or provider credentials. `SecretStr` masks the AI key and database password in ordinary representations; code must still avoid logging their unwrapped values.
5. If a key is exposed, revoke and replace it immediately. Removing a file from Git does not invalidate a key or remove it from existing history.
6. Before public AI access, implement server-enforced usage limits or authentication. Add secret scanning in CI when the repository workflow is established.

Track `pyproject.toml`, `uv.lock`, `.python-version`, and environment templates. Ignore virtual environments, local databases, generated files, and real environment files. `.gitignore` does not protect secrets in files that are already tracked.

## Initial settings

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | API documentation title |
| `ENVIRONMENT` | `development`, `test`, or `production` |
| `DB_HOST` | PostgreSQL hostname, default `127.0.0.1` |
| `DB_PORT` | PostgreSQL port, default `5432` |
| `DB_NAME` | Database name, default `performance_dashboard` |
| `DB_USER` | Database role, default `dashboard` |
| `DB_PASSWORD` | Required backend-only PostgreSQL password |
| `CORS_ORIGINS` | Explicit allowed browser origins, as a JSON array |
| `METRICS_WINDOW_MINUTES` | Planned default reporting window, 1–1440 |
| `AI_PROVIDER` | `disabled`, `gemini`, or `groq`; adapter implementation follows later |
| `AI_API_KEY` | Backend-only provider secret |
| `AI_MODEL` | Provider model identifier, selected during AI integration |
| `AI_TIMEOUT_SECONDS` | Planned provider timeout, greater than 0 and at most 120 |
