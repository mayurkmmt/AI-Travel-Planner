# AI Travel Planner

A full-stack, chat-first AI travel planning application. Users describe their trip in plain language and the AI builds a complete, personalised itinerary — day-by-day plan, hotels, restaurants, budget breakdown, packing list, and weather snapshots — grounded in real place data.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Running Tests](#running-tests)
- [Key Pages](#key-pages)
- [Architecture Notes](#architecture-notes)

---

## Features

- **Conversational trip planning** — no forms, no dropdowns. Just chat.
- **AI-generated itineraries** — day-by-day plan with real attractions from OpenStreetMap.
- **Full trip workspace** — itinerary, hotels, restaurants, budget, weather, packing list, map.
- **Edit via chat** — change budget, swap hotels, adjust pace through natural language.
- **Discover destinations** — browse curated Indian destinations and start planning instantly.
- **Trip sharing** — generate a read-only public link, no login required to view.
- **Duplicate trips** — copy any trip as a new draft.
- **User accounts** — register, login, forgot/reset password via email.
- **Profile & dropdown** — avatar menu with profile page and sign out.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, CSS Modules |
| Backend | FastAPI (Python 3.11), SQLAlchemy, Alembic |
| Database | PostgreSQL (production), SQLite (tests) |
| AI / LLM | Google Gemini (`gemini-1.5-flash`, `gemini-3.5-flash-lite`) |
| Task Queue | Celery + Redis (async plan generation) |
| Places Data | OpenStreetMap / Overpass API |
| Auth | JWT (python-jose), bcrypt |
| Rate Limiting | SlowAPI |

---

## Project Structure

```
AI-Travel-Planner/
├── backend/
│   ├── app/
│   │   ├── core/           # Auth dependencies, security utils
│   │   ├── models/         # SQLAlchemy models (user, trip, chat, itinerary, place, extra)
│   │   ├── routers/        # FastAPI routers (auth, chat, trips, locations, shared)
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic (chat, generation, LLM, places, weather)
│   │   ├── workers/        # Celery tasks
│   │   ├── config.py       # Settings via pydantic-settings
│   │   ├── database.py     # SQLAlchemy engine + session
│   │   └── main.py         # FastAPI app entry point
│   ├── alembic/            # Database migrations
│   ├── tests/
│   │   ├── conftest.py     # Test DB setup (SQLite)
│   │   ├── test_api_endpoints.py   # Full API endpoint tests
│   │   └── test_chat_service.py    # Chat service unit tests
│   └── pyproject.toml
│
└── frontend/
    └── src/
        ├── app/
        │   ├── dashboard/      # My trips page
        │   ├── chat/           # New conversation + existing chat
        │   ├── trips/[tripId]/ # Full trip workspace
        │   ├── discover/       # Discover destinations
        │   ├── how-it-works/   # How it works page
        │   ├── faq/            # FAQ page
        │   ├── profile/        # User profile
        │   └── (auth)/         # Login, register, forgot/reset password
        ├── components/
        │   ├── Navbar.tsx      # Sticky navbar with active links + profile dropdown
        │   └── TripChat.tsx    # Conversational chat UI
        └── lib/
            ├── api.ts          # Axios API client
            └── types.ts        # TypeScript interfaces
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis (for Celery; optional in `DEBUG=true` mode — falls back to background tasks)
- A free [Google Gemini API key](https://ai.google.dev/)

---

### Backend Setup

```bash
cd backend

# Install dependencies using uv
pip install uv
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, GEMINI_API_KEY

# Run database migrations
uv run alembic upgrade head

# Start the development server
uv run uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy and configure environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000

# Start the development server
npm run dev
```

App available at: `http://localhost:3000`

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT signing secret (min 32 chars) | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `GEMINI_MODEL` | Plan generation model (default: `gemini-1.5-flash-latest`) | No |
| `GEMINI_CHAT_MODEL` | Chat model (default: `gemini-3.5-flash-lite`) | No |
| `DEBUG` | `true` uses background tasks instead of Celery | No |
| `REDIS_URL` | Redis URL for Celery | No |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | No |
| `SMTP_HOST` | SMTP server for password reset emails | No |
| `SMTP_USERNAME` | SMTP username | No |
| `SMTP_PASSWORD` | SMTP password | No |
| `SMTP_FROM_EMAIL` | From address for emails | No |
| `FRONTEND_URL` | Frontend base URL for reset links | No |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend API base URL (default: `http://localhost:8000`) |

---

## API Overview

All endpoints are prefixed and documented at `/docs`.

| Group | Endpoints |
|---|---|
| **Auth** | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/forgot-password`, `POST /api/auth/reset-password` |
| **Chat** | `POST /api/chat/`, `GET /api/chat/{trip_id}/history/` |
| **Trips** | `GET /api/trips/`, `GET /api/trips/{id}/`, `PATCH /api/trips/{id}/`, `DELETE /api/trips/{id}/` |
| **Trip Actions** | `POST /api/trips/{id}/duplicate/`, `POST /api/trips/{id}/regenerate/`, `GET /api/trips/{id}/status/` |
| **Trip Content** | `GET /api/trips/{id}/itinerary/`, `/hotels/`, `/restaurants/`, `/budget/`, `/weather/`, `/packing-list/`, `/map/`, `/tips/`, `/emergency/` |
| **Sharing** | `POST /api/trips/{id}/share/`, `DELETE /api/trips/{id}/share/`, `GET /api/shared/{token}/` |

---

## Running Tests

```bash
cd backend

# Run all tests
uv run python -m pytest tests/ -v

# Run only API endpoint tests
uv run python -m pytest tests/test_api_endpoints.py -v

# Run only chat service unit tests
uv run python -m pytest tests/test_chat_service.py -v
```

Tests use an in-memory SQLite database — no PostgreSQL or Redis required.

---

## Key Pages

| Route | Description |
|---|---|
| `/dashboard` | My trips — view, filter, delete trips |
| `/chat` | Start a new conversation |
| `/chat/[tripId]` | Continue or edit an existing conversation |
| `/trips/[tripId]` | Full trip workspace — itinerary, hotels, budget, etc. |
| `/discover` | Browse destinations and start planning instantly |
| `/how-it-works` | How the app works |
| `/faq` | Frequently asked questions |
| `/profile` | User profile and sign out |

---

## Architecture Notes

- **Plan generation** runs asynchronously. In `DEBUG=true` mode it uses FastAPI `BackgroundTasks`. In production it dispatches to a Celery worker via Redis. The frontend polls `/api/trips/{id}/status/` every 5 seconds until the status becomes `created`.
- **Chat state** is managed via a `ChatSession` slot-state JSON column. The agent extracts destination, budget, dates, group size, and preferences incrementally across messages.
- **Duplicate trip** copies all fields including destinations, preferences, and thumbnail. The duplicate starts as `draft` status.
- **Rate limiting** is applied on chat send (20/min) and regenerate (5/min) via SlowAPI.
- **JWT tokens** expire after 7 days (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
# AI Travel Planner

A full-stack, chat-first AI travel planning application. Users describe their trip in plain language and the AI builds a complete, personalised itinerary — day-by-day plan, hotels, restaurants, budget breakdown, packing list, and weather snapshots — grounded in real place data.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Running Tests](#running-tests)
- [Key Pages](#key-pages)
- [Architecture Notes](#architecture-notes)

---

## Features

- **Conversational trip planning** — no forms, no dropdowns. Just chat.
- **AI-generated itineraries** — day-by-day plan with real attractions from OpenStreetMap.
- **Full trip workspace** — itinerary, hotels, restaurants, budget, weather, packing list, map.
- **Edit via chat** — change budget, swap hotels, adjust pace through natural language.
- **Discover destinations** — browse curated Indian destinations and start planning instantly.
- **Trip sharing** — generate a read-only public link, no login required to view.
- **Duplicate trips** — copy any trip as a new draft.
- **User accounts** — register, login, forgot/reset password via email.
- **Profile & dropdown** — avatar menu with profile page and sign out.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, CSS Modules |
| Backend | FastAPI (Python 3.11), SQLAlchemy, Alembic |
| Database | PostgreSQL (production), SQLite (tests) |
| AI / LLM | Google Gemini (`gemini-1.5-flash`, `gemini-3.5-flash-lite`) |
| Task Queue | Celery + Redis (async plan generation) |
| Places Data | OpenStreetMap / Overpass API |
| Auth | JWT (python-jose), bcrypt |
| Rate Limiting | SlowAPI |

---

## Project Structure

```
AI-Travel-Planner/
├── backend/
│   ├── app/
│   │   ├── core/           # Auth dependencies, security utils
│   │   ├── models/         # SQLAlchemy models (user, trip, chat, itinerary, place, extra)
│   │   ├── routers/        # FastAPI routers (auth, chat, trips, locations, shared)
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic (chat, generation, LLM, places, weather)
│   │   ├── workers/        # Celery tasks
│   │   ├── config.py       # Settings via pydantic-settings
│   │   ├── database.py     # SQLAlchemy engine + session
│   │   └── main.py         # FastAPI app entry point
│   ├── alembic/            # Database migrations
│   ├── tests/
│   │   ├── conftest.py     # Test DB setup (SQLite)
│   │   ├── test_api_endpoints.py   # Full API endpoint tests
│   │   └── test_chat_service.py    # Chat service unit tests
│   └── pyproject.toml
│
└── frontend/
    └── src/
        ├── app/
        │   ├── dashboard/      # My trips page
        │   ├── chat/           # New conversation + existing chat
        │   ├── trips/[tripId]/ # Full trip workspace
        │   ├── discover/       # Discover destinations
        │   ├── how-it-works/   # How it works page
        │   ├── faq/            # FAQ page
        │   ├── profile/        # User profile
        │   └── (auth)/         # Login, register, forgot/reset password
        ├── components/
        │   ├── Navbar.tsx      # Sticky navbar with active links + profile dropdown
        │   └── TripChat.tsx    # Conversational chat UI
        └── lib/
            ├── api.ts          # Axios API client
            └── types.ts        # TypeScript interfaces
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis (for Celery; optional in `DEBUG=true` mode — falls back to background tasks)
- A free [Google Gemini API key](https://ai.google.dev/)

---

### Backend Setup

```bash
cd backend

# Install dependencies using uv
pip install uv
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, GEMINI_API_KEY

# Run database migrations
uv run alembic upgrade head

# Start the development server
uv run uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy and configure environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000

# Start the development server
npm run dev
```

App available at: `http://localhost:3000`

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT signing secret (min 32 chars) | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `GEMINI_MODEL` | Plan generation model (default: `gemini-1.5-flash-latest`) | No |
| `GEMINI_CHAT_MODEL` | Chat model (default: `gemini-3.5-flash-lite`) | No |
| `DEBUG` | `true` uses background tasks instead of Celery | No |
| `REDIS_URL` | Redis URL for Celery | No |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | No |
| `SMTP_HOST` | SMTP server for password reset emails | No |
| `SMTP_USERNAME` | SMTP username | No |
| `SMTP_PASSWORD` | SMTP password | No |
| `SMTP_FROM_EMAIL` | From address for emails | No |
| `FRONTEND_URL` | Frontend base URL for reset links | No |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend API base URL (default: `http://localhost:8000`) |

---

## API Overview

All endpoints are prefixed and documented at `/docs`.

| Group | Endpoints |
|---|---|
| **Auth** | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/forgot-password`, `POST /api/auth/reset-password` |
| **Chat** | `POST /api/chat/`, `GET /api/chat/{trip_id}/history/` |
| **Trips** | `GET /api/trips/`, `GET /api/trips/{id}/`, `PATCH /api/trips/{id}/`, `DELETE /api/trips/{id}/` |
| **Trip Actions** | `POST /api/trips/{id}/duplicate/`, `POST /api/trips/{id}/regenerate/`, `GET /api/trips/{id}/status/` |
| **Trip Content** | `GET /api/trips/{id}/itinerary/`, `/hotels/`, `/restaurants/`, `/budget/`, `/weather/`, `/packing-list/`, `/map/`, `/tips/`, `/emergency/` |
| **Sharing** | `POST /api/trips/{id}/share/`, `DELETE /api/trips/{id}/share/`, `GET /api/shared/{token}/` |

---

## Running Tests

```bash
cd backend

# Run all tests
uv run python -m pytest tests/ -v

# Run only API endpoint tests
uv run python -m pytest tests/test_api_endpoints.py -v

# Run only chat service unit tests
uv run python -m pytest tests/test_chat_service.py -v
```

Tests use an in-memory SQLite database — no PostgreSQL or Redis required.

---

## Key Pages

| Route | Description |
|---|---|
| `/dashboard` | My trips — view, filter, delete trips |
| `/chat` | Start a new conversation |
| `/chat/[tripId]` | Continue or edit an existing conversation |
| `/trips/[tripId]` | Full trip workspace — itinerary, hotels, budget, etc. |
| `/discover` | Browse destinations and start planning instantly |
| `/how-it-works` | How the app works |
| `/faq` | Frequently asked questions |
| `/profile` | User profile and sign out |

---

## Architecture Notes

- **Plan generation** runs asynchronously. In `DEBUG=true` mode it uses FastAPI `BackgroundTasks`. In production it dispatches to a Celery worker via Redis. The frontend polls `/api/trips/{id}/status/` every 5 seconds until the status becomes `created`.
- **Chat state** is managed via a `ChatSession` slot-state JSON column. The agent extracts destination, budget, dates, group size, and preferences incrementally across messages.
- **Duplicate trip** copies all fields including destinations, preferences, and thumbnail. The duplicate starts as `draft` status.
- **Rate limiting** is applied on chat send (20/min) and regenerate (5/min) via SlowAPI.
- **JWT tokens** expire after 7 days (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
