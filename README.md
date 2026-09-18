# AI-Enhanced API Performance Dashboard

A full-stack application for monitoring simulated API performance and generating AI-assisted observations from collected metrics.

## Stack

- **Backend:** Python, FastAPI, PostgreSQL
- **Frontend:** React, Vite, TypeScript
- **Data fetching:** Axios and TanStack Query
- **Visualization:** Recharts
- **AI integration:** Google Gemini or Groq through the backend

## Backend quick start

Follow the [backend PostgreSQL setup](./backend/README.md#local-postgresql) to start the local database. With uv installed, run:

```bash
cd backend
make setup
make run
```

Run `make help` inside `backend/` for dependency, code-check, and cleanup commands. `make clean` removes backend logs and caches while preserving local settings, databases, and the virtual environment.

## Project documentation

- [Project idea and goals](./PROJECT_IDEA_AND_GOALS.md)
- [Backend overview](./backend/README.md)
- [Frontend overview](./frontend/README.md)
