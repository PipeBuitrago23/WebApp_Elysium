# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Elysium Fisio-Pilates** — appointment scheduling PWA for a single-location physiotherapy/pilates clinic. Two user roles:
- **Admin/Staff:** full agenda control, attendance tracking, cancellations, metrics
- **Patients (external):** self-service booking for Fisioterapia or Pilates, registration, brief medical history (anamnesis)

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Tailwind CSS 3, React Router 6, Axios, Lucide-React |
| Backend | Python 3.11 / FastAPI, SQLAlchemy, python-jose (JWT), bcrypt |
| Database | PostgreSQL 15 |
| Infrastructure | Docker + Docker Compose |
| Future | n8n webhooks → WhatsApp API (Meta) for reminders |

## Running the Project

```bash
# First run or after adding npm packages — always rebuild + re-install inside the container
docker compose up -d --build
docker compose exec frontend npm install   # required when package.json changes

# Normal start (containers already built)
docker compose up -d

# Tear down (keep DB data)
docker compose down

# Tear down + wipe database
docker compose down -v
```

> **Docker volume gotcha:** The frontend uses an anonymous volume for `node_modules`. After adding packages to `package.json`, run `docker compose exec frontend npm install` inside the running container — don't rely on rebuild alone.

Service URLs when running:
- Frontend: http://localhost:3000
- Backend API + Swagger: http://localhost:8000 and http://localhost:8000/docs
- PostgreSQL: localhost:5432, database `elysium_agenda`

Default admin account (seeded on startup): `admin@elysium.com` / `admin123`

## Architecture

Three Docker containers (`docker-compose.yml`):

1. **`db`** — `postgres:15`, credentials `admin / password_seguro`, DB `elysium_agenda`. Has a healthcheck; backend waits for it.
2. **`backend`** — FastAPI, `./backend/`, entry `main:app`, uvicorn hot-reload. Creates DB tables and seeds admin on startup via `lifespan`.
3. **`frontend`** — CRA React, `./frontend/`, `npm start`. Volume-mounted for hot-reload.

### Backend layout (`./backend/`)

```
main.py          # App factory, CORS, lifespan (create_all + seed admin)
database.py      # SQLAlchemy engine, SessionLocal, Base, get_db()
auth/
  jwt.py         # create_access_token / verify_token (python-jose, HS256, 8h TTL)
models/
  paciente.py    # Paciente table — PK column must be named 'Paciente'
  usuario.py     # Staff/admin users with bcrypt hashed passwords
routes/
  auth.py        # POST /auth/login → JWT (uses bcrypt directly, NOT passlib)
  pacientes.py   # GET /pacientes/ (stub)
```

> **bcrypt note:** `passlib[bcrypt]` is installed but NOT used — passlib 1.7.4 is incompatible with bcrypt 4.x (raises ValueError on startup). All password hashing uses `import bcrypt` directly.

### Frontend layout (`./frontend/src/`)

```
index.js                   # Entry, imports index.css (Tailwind)
App.js                     # Routes: /login + nested / (DashboardLayout + PrivateRoute)
index.css                  # @tailwind base/components/utilities
api/
  auth.js                  # loginRequest() — POST /auth/login (x-www-form-urlencoded)
context/
  AuthContext.js           # AuthProvider, useAuth() — JWT in localStorage (key: elysium_token)
layouts/
  DashboardLayout.js       # Sidebar + TopBar + <Outlet />
components/
  Sidebar.js               # Dark (slate-900) sidebar, NavLink active = teal-600, lucide icons
  TopBar.js                # Page title bar, route → title map
  PrivateRoute.js          # Redirects to /login if not authenticated
pages/
  LoginPage.js             # Login form, teal/slate design
  DashboardHome.js         # 4 stat cards + "Citas de hoy" table (placeholder data)
```

### Routing structure

```
/login                    → LoginPage (public)
/ (PrivateRoute)
  /dashboard              → DashboardHome
  /agenda                 → ComingSoon placeholder
  /pacientes              → ComingSoon placeholder
  /nueva-cita             → ComingSoon placeholder
```

## Current Status (as of 2026-06-12)

**Done:**
- [x] Full Docker Compose setup (db + backend + frontend) with healthcheck
- [x] JWT login (backend) + login page (frontend) — fully functional
- [x] Admin user auto-seeded on backend startup
- [x] Dashboard layout: dark sidebar, nav with icons, topbar, user info + logout
- [x] Dashboard home: 4 stat cards + today's appointments table (empty state)

**Next to build:**
- [ ] **Agenda** — weekly/daily calendar view with appointment slots
- [ ] **Pacientes** — searchable table + registration form with anamnesis fields
- [ ] **Nueva Cita** — form to book an appointment (date, time, type, patient)
- [ ] **Cita model** — DB table and CRUD endpoints in the backend

## Critical Design Rules

1. **Database identifier:** Always use the column named `Paciente` (never `ID_Paciente` or any variant) as the primary key/identifier in patient-related tables. Required for compatibility with external systems.

2. **Auth:** JWT via `python-jose`. Use `bcrypt` directly (not `passlib.CryptContext`). Token stored in `localStorage` under key `elysium_token`.

3. **Code style:** Structured by files, no excessive comments. Modules small and focused: routes only route, models only define schema, business logic separate.

4. **Color palette:** teal-600/700 (primary actions, active nav, brand), slate-900 (sidebar), slate-50 (page background), white (cards).
