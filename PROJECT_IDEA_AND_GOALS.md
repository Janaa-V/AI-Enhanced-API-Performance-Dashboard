# General Project Idea and Goals

## Project Overview

The AI-Enhanced API Performance Dashboard is a full-stack application designed to demonstrate practical backend development, frontend engineering, observability, and responsible use of AI-assisted analysis.

The application monitors a group of simulated backend API endpoints and presents their performance through an interactive dashboard. It tracks latency, request volume, error rates, and recent request activity. A backend AI integration then turns the collected metrics into concise, plain-English observations and optimization suggestions.

This project reflects the type of work involved in building and improving production API systems while keeping the implementation approachable, reproducible, and suitable for public sharing.

## Primary Goals

- Build a complete full-stack application with a FastAPI backend and a React frontend built with Vite and TypeScript.
- Simulate realistic API traffic across several backend endpoints with varied response times and occasional failures.
- Record request-level performance data in a lightweight SQLite database.
- Aggregate the collected data into useful performance metrics and visualizations.
- Provide an intuitive dashboard for reviewing latency, throughput, error rates, and recent requests.
- Add an AI-assisted insights layer that explains notable patterns and suggests possible optimizations.
- Keep the project deployable using free-tier-friendly tools and services.
- Produce a clear, usable application that communicates both technical ability and product thinking.

## Backend Goals

The backend will be built with Python and FastAPI. It will provide the application API, simulated endpoint traffic, metrics aggregation, data persistence, and AI analysis.

The backend will:

- Expose several mock API endpoints that represent common backend operations, such as user, order, product, search, and reporting services.
- Introduce controlled variation in response times and simulated error behavior so the dashboard has meaningful data to display.
- Capture each request's endpoint, HTTP method, status code, latency, and timestamp.
- Store request logs in SQLite using a simple and maintainable schema.
- Provide an aggregated metrics endpoint for the frontend, including average latency, request counts, error counts, error rates, status-code breakdowns, and recent requests.
- Provide an analysis endpoint that sends a structured metrics summary to an AI provider and returns a concise natural-language response.
- Keep AI-provider integration behind a service boundary so the provider can be changed without rewriting the rest of the backend.
- Include basic validation, error handling, and configuration for local development and deployment.

The backend is intended to demonstrate API design, asynchronous application structure, middleware, database access, observability patterns, and safe integration with an external AI service.

## Frontend Goals

The frontend will be built with React, Vite, and TypeScript. It will use function components and hooks, TanStack Query for data fetching and loading states, Axios for HTTP requests, and Recharts for visualizations.

The frontend will:

- Provide a dashboard overview with key performance indicators such as average latency, total requests, and error rate.
- Display latency trends and status-code distribution through responsive Recharts visualizations.
- Show recent API requests in a sortable, readable table.
- Present AI-generated observations in a dedicated insights panel.
- Fetch metrics through a typed API layer and manage loading, error, success, and automatic refetch behavior with TanStack Query.
- Use CSS Modules or another lightweight styling approach to provide a clean layout that adapts to desktop and smaller screens.
- Keep component, model, API, and hook boundaries organized so additional dashboard features can be added later.

The frontend is intended to demonstrate component-based development, React hooks, typed API integration, data visualization, responsive layout, state handling, and user-focused presentation of technical information.

## AI-Assisted Insights

The AI layer will not train or host a machine-learning model. Instead, the backend will send a carefully structured summary of recent API metrics to a free-tier AI API, such as Google Gemini or Groq.

The AI response will focus on practical questions such as:

- Which endpoints appear slower than expected?
- Are error rates increasing or concentrated in a particular service?
- Could latency or error patterns indicate a database, dependency, or resource bottleneck?
- What small optimization or investigation steps would be reasonable to try first?

The goal is to provide useful, understandable guidance while being transparent that the feature is AI-assisted analysis rather than an autonomous monitoring system.

