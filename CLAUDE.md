# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Elysium Fisio-Pilates** — appointment scheduling PWA for a single-location physiotherapy/pilates clinic. Access is primarily driven by scanning a QR Code or opening a direct link, guiding users to a lightweight registration screen.

### User Roles & Permissions
- **Admin / Staff (Fisioterapeuta):**
  - Full control over the entire clinic agenda (see which patients booked which slots).
  - Track hourly capacity (view remaining open spaces/slots available per hour).
  - Register patient payments manually (package type, total sessions, payment date, and track overall attendance).
- **Patients (External Users):**
  - Self-register with name, cedula, and phone (public form — no login needed to register).
  - Self-service booking for Fisioterapia or Pilates based on live slot availability.
  - View current active plan metrics: package type, total sessions, and remaining sessions (`sesiones_restantes`).
  - View plan expiration date (dynamically calculated).
  - Access portal anonymously via cedula (QR code flow) or via email+password login.

## Test Accounts

| Role | Email | Password | Redirects to |
|------|-------|----------|--------------|
| Admin | `admin@elysium.com` | `admin123` | `/dashboard` |
| Patient | `paciente@elysium.com` | `paciente123` | `/portal` (auto-loads Carlos Pérez, cedula `00000001`, Pilates 8/12) |

Both accounts are auto-seeded by `_seed_admin()` and `_seed_paciente()` in `main.py` on every startup.

## Core Business Rules & Policies

1. **Plan Expiration Rule (45-Day Validity):**
   - When an Admin registers a payment or assigns a package, the system must log: package type, total sessions, and the payment date.
   - The expiration date must be automatically computed by the backend as exactly **45 calendar days** starting from the payment/registration date.
   - Sessions can only be booked if the appointment date is less than or equal to the plan's expiration date.

2. **Strict Cancellation & No-Show Policy (2-Hour Window):**
   - Patients can freely cancel or reschedule an appointment from their panel **only if there are more than 2 hours remaining** before the appointment's start time.
   - If a patient attempts to cancel within the 2-hour window, or fails to show up (No-Show), the system must mark the appointment status as `'No asistió con penalización'` and **automatically deduct 1 session** from their `sesiones_restantes`.
   - A background asyncio job runs every 5 minutes and auto-penalizes past appointments that were never resolved.

3. **Hourly Capacity Validation:**
   - The agenda must enforce strict slot limits per hour. The backend must validate available capacity before confirming any booking to prevent overbooking.

4. **Strict Time-Slot & Capacity Constraints:**

   **Allowed schedule window:** Appointments can only be scheduled between **7:00 AM and 6:30 PM** (last valid slot starts at 18:30). Any time outside this window must be rejected.

   **Fixed 30-minute intervals:** Booking times must strictly fall on `:00` or `:30` of any hour. Valid examples: `7:00`, `7:30`, `8:00`, `8:30`. Times like `8:45` or `9:20` are invalid and must be blocked by backend validation — not just frontend.

   **Pilates:**
   - Max **6 patients** per concurrent time slot.
   - Standard session duration: **60 minutes**.
   - Exception: *Sesión de cortesía* lasts exactly **45 minutes**.

   **Fisioterapia:**
   - Max **2 patients** per concurrent time slot.
   - Follows the same fixed 30-minute interval logic.

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

> **Hot-reload on Windows/Docker (D: drive):** File changes on D: drive sometimes don't trigger webpack hot reload. If the UI doesn't update after saving, run `docker compose restart frontend` to force a fresh webpack compile.

Service URLs when running:
- Frontend: http://localhost:3000
- Backend API + Swagger: http://localhost:8000 and http://localhost:8000/docs
- PostgreSQL: localhost:5432, database `elysium_agenda`

## Architecture

Three Docker containers (`docker-compose.yml`):

1. **`db`** — `postgres:15`, credentials `admin / password_seguro`, DB `elysium_agenda`. Has a healthcheck; backend waits for it.
2. **`backend`** — FastAPI, `./backend/`, entry `main:app`, uvicorn hot-reload. Creates DB tables and seeds admin + test patient on startup via `lifespan`.
3. **`frontend`** — CRA React, `./frontend/`, `npm start`. Volume-mounted for hot-reload.

### Backend layout (`./backend/`)

```
main.py              # App factory, CORS, lifespan (create_all + _seed_admin + _seed_paciente)
database.py          # SQLAlchemy engine, SessionLocal, Base, get_db()
auth/
  jwt.py             # create_access_token / verify_token + get_current_user dependency
models/
  paciente.py        # Paciente table — PK column must be named 'Paciente' (string)
  usuario.py         # Staff/admin users with bcrypt hashed passwords
  cita.py            # Cita table — id (UUID), paciente_id (FK), fecha, hora, tipo, estado, notas
  pago.py            # Package purchase: tipo_paquete, total_sesiones, sesiones_restantes, fecha_pago, fecha_vencimiento
routes/
  auth.py            # POST /auth/login → JWT with sub, nombre, es_admin, paciente_id
  pacientes.py       # Full CRUD /pacientes/ — JWT protected
  citas.py           # Full CRUD /citas/ + background job procesar_citas_vencidas()
  pagos.py           # POST /pagos/ + GET /pagos/?paciente_id= — JWT protected
  portal.py          # Public (no JWT): GET /portal/paciente/{cedula}, POST /portal/citas,
                     #   POST /portal/registro (self-register: nombre+cedula+telefono)
```

> **bcrypt note:** `passlib[bcrypt]` is installed but NOT used — passlib 1.7.4 is incompatible with bcrypt 4.x (raises ValueError on startup). All password hashing uses `import bcrypt` directly.

### Frontend layout (`./frontend/src/`)

```
index.js                    # Entry, imports index.css (Tailwind)
App.js                      # Routes: /login (public) + /portal (public) + / (PrivateRoute admin)
index.css                   # @tailwind base/components/utilities
api/
  auth.js                   # loginRequest() — POST /auth/login (x-www-form-urlencoded)
  pacientes.js              # getPacientes, getPaciente, createPaciente, updatePaciente, deletePaciente
  citas.js                  # getCitas, createCita, patchCitaEstado, updateCita, deleteCita
  pagos.js                  # getPagos, createPago
  portal.js                 # getPortalPaciente, portalRegistro, portalCrearCita (no auth headers)
context/
  AuthContext.js            # AuthProvider, useAuth() — JWT in localStorage (key: elysium_token)
                            # login() returns decoded payload so LoginPage can redirect by role
layouts/
  DashboardLayout.js        # Sidebar + TopBar + <Outlet />
components/
  Sidebar.js                # Dark (slate-900) sidebar, NavLink active = teal-600, lucide icons
  TopBar.js                 # Page title bar, route → title map
  PrivateRoute.js           # Checks isAuthenticated AND user.es_admin=true; patients → /portal
pages/
  LoginPage.js              # Login form — redirects to /dashboard (admin) or /portal (patient)
  DashboardHome.js          # Real stats: citas hoy/semana/mes by tipo, pacientes activos/inactivos, próxima cita
  PacientesPage.js          # Searchable table + create/edit modal + delete confirm
  NuevaCitaPage.js          # Admin appointment booking form
  AgendaPage.js             # Weekly view Lun–Sáb, 30-min slots, capacity badges, estado modal
  PortalPage.js             # Patient self-service: cedula entry OR auto-load (if logged in),
                            #   plan card + progress bar, upcoming citas, booking form, self-register form
```

### Routing structure

```
/login                    → LoginPage (public) — redirects by role after login
/portal                   → PortalPage (public) — anonymous (cedula) or authenticated (email+password)
/ (PrivateRoute — admin only, es_admin=true required)
  /dashboard              → DashboardHome (real stats)
  /agenda                 → AgendaPage
  /pacientes              → PacientesPage
  /nueva-cita             → NuevaCitaPage
```

### JWT payload structure

```json
{
  "sub": "admin@elysium.com",
  "nombre": "Administrador",
  "es_admin": true,
  "paciente_id": null,
  "exp": 1234567890
}
```

- `es_admin=true` → admin, access to all protected routes
- `es_admin=false` + `paciente_id="00000001"` → patient, portal auto-loads their data
- Frontend decodes with `atob(token.split('.')[1])` in `AuthContext.parseToken()`

### Data model — `citas.estado` valid values

```
"programada"                    # default on creation
"confirmada"
"completada"                    # triggers sesiones_restantes decrement
"cancelada"                     # free if > 2h before appointment
"No asistió con penalización"   # no-show or late cancel → deducts 1 session
```

Terminal states (`completada`, `cancelada`, `"No asistió con penalización"`) are **immutable** — no further estado changes allowed.

### Data model — `pagos` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| paciente_id | String | FK → pacientes.Paciente |
| tipo_paquete | String | e.g. "Pilates", "Fisioterapia" |
| total_sesiones | Integer | |
| sesiones_restantes | Integer | decremented by backend only |
| fecha_pago | Date | registered by admin |
| fecha_vencimiento | Date | computed server-side: fecha_pago + 45 days |

### Patient registration flow

New patients self-register via `/portal` → "Crea tu perfil aquí":
1. `POST /portal/registro` — creates `pacientes` record with nombre, cedula, telefono (409 if cedula exists)
2. Portal shows their empty dashboard: no plan, no citas, welcome message
3. Admin completes full profile (fecha_nacimiento, antecedentes, cirugias) from PacientesPage when they attend their first session
4. Admin registers payment → plan activates → patient can book sessions

## Current Status

**All core features complete:**
- [x] Full Docker Compose setup (db + backend + frontend) with healthcheck
- [x] JWT auth with role-based redirect: admin → `/dashboard`, patient → `/portal`
- [x] Admin and test patient auto-seeded on startup
- [x] Dashboard layout: dark sidebar, nav with icons, topbar, user info + logout
- [x] Dashboard home: real stats — citas hoy/semana/mes split by Pilates/Fisio, pacientes activos/inactivos, próxima cita + today's table
- [x] `backend/models/paciente.py` + full CRUD `routes/pacientes.py` (JWT protected)
- [x] `frontend/src/pages/PacientesPage.js` — searchable table + create/edit modal + delete confirm
- [x] `backend/models/cita.py` + `routes/citas.py` — full CRUD + all validations + background auto-penalty job
- [x] `backend/models/pago.py` + `routes/pagos.py` — plan management
- [x] `frontend/src/pages/NuevaCitaPage.js` — admin appointment booking form
- [x] `frontend/src/pages/AgendaPage.js` — weekly view + estado modal + capacity badges
- [x] `backend/routes/portal.py` — public routes: lookup, registro, cita booking
- [x] `frontend/src/pages/PortalPage.js` — patient portal: anonymous + authenticated + self-register

**Next to build:**
- [ ] **Notificaciones** — n8n webhook → WhatsApp recordatorio 24h antes de la cita

## Critical Design Rules

1. **Database identifier:** Always use the column named `Paciente` (never `ID_Paciente` or any variant) as the primary key/identifier in patient-related tables.

2. **Auth:** JWT via `python-jose`. Use `bcrypt` directly (not `passlib.CryptContext`). Token stored in `localStorage` under key `elysium_token`. JWT payload always includes `es_admin` (bool) and `paciente_id` (str | null).

3. **Plan expiration:** Always computed server-side as `fecha_pago + timedelta(days=45)`. Never accept it from the client.

4. **Session deduction:** `sesiones_restantes` is decremented by the backend only — never by the frontend. Triggered on estado = `"completada"` or `"No asistió con penalización"`.

5. **Capacity constants (never hardcode inline):** Define in one place — e.g. `CAPACIDAD = {"Pilates": 6, "Fisioterapia": 2}`. Both `routes/citas.py` and `routes/portal.py` define their own copy (same values).

6. **Code style:** Modules small and focused: routes only route, models only define schema, business logic in routes. No excessive comments.

7. **Color palette:** teal-600/700 (primary actions, active nav, brand), slate-900 (sidebar), slate-50 (page background), white (cards).

8. **Timezone gotcha:** Never use `new Date().toISOString().split('T')[0]` — returns UTC date. Always use local date methods: `getFullYear() / getMonth() / getDate()`. Applied in `DashboardHome.js`, `AgendaPage.js`, and `PortalPage.js`.
