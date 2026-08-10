# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Elysium Fisio-Pilates** — appointment scheduling PWA for a single-location physiotherapy/pilates clinic. Access is primarily driven by scanning a QR Code or opening a direct link, guiding users to a lightweight registration screen.

> **Multi-tenant conversion in progress (`feature/multi-tenant` branch, off `main`):** Phase 1 of 4 (data layer, tenant context, config system) is **complete** — see the "Multi-Tenancy" section below. Elysium is still the only tenant in practice, but every table is now tenant-scoped with Row-Level Security, and business rules (schedule window, plan validity, capacity, cancellation window) are per-tenant config instead of hardcoded. Not yet built: tenant admin UI, wildcard DNS / real subdomain routing, WhatsApp, self-service onboarding, billing — those are Phases 2–4.

### User Roles & Permissions
- **Admin / Staff (Fisioterapeuta):**
  - Full control over the entire clinic agenda (see which patients booked which slots).
  - Track hourly capacity (view remaining open spaces/slots available per hour).
  - Register patient payments manually (package type, total sessions, payment date, and track overall attendance).
  - Create and manage external "Médico en Convenio" accounts; optionally tag a manually-booked cita with a referring médico.
- **Médico Externo en Convenio (v2.0):**
  - Login-only role (no anonymous access) — account created by an Admin from `/medicos`.
  - Self-service: register a new/existing patient and book a referral appointment for them (`/medico`), attaching `motivo_remision`.
  - Can only see the citas they personally referred (`medico_id` = their own user id) — never the full agenda or patient list.
  - Referral citas do **not** require the patient to have an active paid plan (see Critical Design Rule #13).
- **Patients (External Users):**
  - Self-register with name, cedula, phone, and email (public form — no login needed to register).
  - Self-service booking for Fisioterapia or Pilates based on live slot availability.
  - View current active plan metrics: package type, total sessions, and remaining sessions (`sesiones_restantes`).
  - View plan expiration date (dynamically calculated).
  - Access portal anonymously via cedula (QR code flow) or via email+password login.

## Test Accounts

| Role | Email | Password | Redirects to |
|------|-------|----------|--------------|
| Admin | `admin@elysium.com` | `admin123` | `/dashboard` |
| Patient | `paciente@elysium.com` | `paciente123` | `/portal` (auto-loads Carlos Pérez, cedula `00000001`, Pilates 8/12) |

Admin and test patient are auto-seeded by `_seed_admin()` and `_seed_paciente()` in `main.py` on every startup — both resolve the Elysium tenant by slug first (still hardcoded to `"elysium"`, see Multi-Tenancy below) and no-op with a warning if it doesn't exist yet. There is no seeded médico account — create one from `/medicos` (Admin panel) or `POST /medicos/`.

> **Tenant header required for every request:** since Phase 1, every backend request must resolve a tenant (`TenantMiddleware`) or it 404s — including `curl`/Swagger testing. Locally this happens automatically for the frontend (`REACT_APP_TENANT_SLUG=elysium` in `docker-compose.yml`), but manual API calls (`curl`, Postman, `/docs`) need `-H "X-Tenant-Slug: elysium"` explicitly.

## Core Business Rules & Policies

> These describe Elysium's **current configured values** — as of Phase 1 they live in `tenants.config` (per-tenant, via `Tenant.get_config()`), not hardcoded constants. A different tenant could configure different numbers; see "Multi-Tenancy" below for where each value actually lives now.

1. **Plan Expiration Rule (45-Day Validity):**
   - When an Admin registers a payment or assigns a package, the system must log: package type, total sessions, the payment date, and the plan's **start date** (`fecha_inicio`) — clients don't always start using a plan the same day it's fully paid (e.g. start the 1st, finish paying in installments by the 10th/25th/30th), so the two dates are captured independently.
   - The expiration date must be automatically computed by the backend as exactly **45 calendar days** starting from the plan's **start date** (`fecha_inicio`), not the payment date.
   - Sessions can only be booked if the appointment date is less than or equal to the plan's expiration date.

2. **Strict Cancellation & No-Show Policy (2-Hour Window):**
   - Patients can freely cancel or reschedule an appointment from their panel **only if there are more than 2 hours remaining** before the appointment's start time.
   - If a patient attempts to cancel within the 2-hour window, or fails to show up (No-Show), the system must mark the appointment status as `'No asistió con penalización'` and **automatically deduct 1 session** from their `sesiones_restantes`.
   - A background asyncio job runs every 5 minutes and auto-penalizes past appointments that were never resolved.

3. **Hourly Capacity Validation:**
   - The agenda must enforce strict slot limits per hour. The backend must validate available capacity before confirming any booking to prevent overbooking.

4. **Strict Time-Slot & Capacity Constraints:**

   **Allowed schedule window:** Two fixed blocks — **morning 7:00–11:00** (last slot 11:00) and **afternoon 14:00–18:00** (last slot 18:00). The midday gap 11:30–13:30 is blocked. Any time outside these windows must be rejected. As of Phase 1 this lives in Elysium's `tenants.config.horario.bloques` (a list, specifically to allow the midday gap) and is checked via `core/servicios.py:hora_valida()` — no longer a hardcoded `TURNOS` tuple.

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
| Frontend | React 18, Tailwind CSS 3, React Router 6, Axios, Lucide-React, Recharts |
| Backend | Python 3.11 / FastAPI, SQLAlchemy, python-jose (JWT), bcrypt |
| Database | PostgreSQL 15 |
| Infrastructure | Docker + Docker Compose (local) · Railway (production) |
| Rate limiting | slowapi (5/min login · 10/min portal public endpoints) |
| Email | Resend API (HTTP) — env var `RESEND_API_KEY`; optional `RESEND_FROM` (default `onboarding@resend.dev`) |
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
- Backend API + Swagger: http://localhost:8000 and http://localhost:8000/docs (disabled in production)
- PostgreSQL: localhost:5432, database `elysium_agenda`

## Database Migrations (Alembic)

Schema is managed entirely by Alembic (`backend/alembic/`) — `Base.metadata.create_all()` and the old hand-rolled `_run_migrations()` were removed from `main.py`'s `lifespan`. Every schema change, from now on, is a new Alembic revision.

```bash
# Create a new (empty) revision to hand-write — do NOT use --autogenerate for
# anything touching tenant_id / composite PKs / composite FKs: autogenerate
# does not detect PK column-set changes or composite FK changes reliably, and
# can't generate the DML (seed inserts, backfill UPDATEs) these migrations need.
docker compose exec backend alembic revision -m "short description"

# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Roll back the most recent revision
docker compose exec backend alembic downgrade -1
```

`backend/alembic/env.py` reads its connection from `DATABASE_URL` — the same **admin/table-owner** connection `database.py` falls back to. Migrations always run as the owner (needs full DDL rights and must work before RLS/`app_user` exist); the running app connects separately via `APP_DATABASE_URL` at runtime (see Row-Level Security below).

**Startup:** the backend container's command is `sh -c "alembic upgrade head && uvicorn main:app ..."` (`docker-compose.yml`) — migrations run once, before the app starts serving traffic, instead of inside `lifespan` on every worker boot. **Railway's Start Command for the backend service must be updated to match** (`sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"` or equivalent) — this lives in the Railway dashboard, not in the repo, so it needs a manual one-time update there.

`backend/alembic/versions/0001_baseline.py` is a hand-written snapshot of the schema as it existed before Alembic was introduced (the 6 original tables). It was applied to the real production database with `alembic stamp head` — **never** `alembic upgrade head` — since those tables already existed and must not be recreated. A fresh dev/CI database, by contrast, can run `alembic upgrade head` from empty and it will build the same schema via this revision.

**Revisions so far:**
- `0001_baseline` — snapshot of the pre-multi-tenant schema (see above).
- `0002_multi_tenant_schema` — creates `tenants`/`servicios`, seeds the Elysium tenant + its 2 servicios, adds `tenant_id` to the 6 original tables, rebuilds `pacientes`' PK as composite `(tenant_id, "Paciente")` and the FKs to match. Hand-written, not autogenerated (autogenerate can't reliably detect PK/composite-FK changes or generate the seed/backfill DML). Tested reversible (`alembic downgrade -1`) against real data — but see the time-bounded rollback warning in the migration's own docstring: safe only while Elysium is the sole tenant.
- `0003_rls` — `ENABLE`/`FORCE ROW LEVEL SECURITY` + `tenant_isolation` policy on every tenant-scoped table. Kept separate from `0002` so a rollback of the RLS policy doesn't require re-running the riskier key-reconstruction migration. See "Multi-Tenancy" below for what this actually does.
- `0004_pago_fecha_inicio` — adds `pagos.fecha_inicio` (nullable → backfilled from `fecha_pago` → `SET NOT NULL`), so `fecha_vencimiento` is computed from the plan's start date instead of its payment date (see Critical Design Rule #3).

## Architecture

Three Docker containers (`docker-compose.yml`):

1. **`db`** — `postgres:15`, credentials `admin / password_seguro`, DB `elysium_agenda`. Has a healthcheck; backend waits for it.
2. **`backend`** — FastAPI, `./backend/`, entry `main:app`, uvicorn hot-reload. Runs `alembic upgrade head` on container start (before uvicorn), then seeds admin + test patient via `lifespan`.
3. **`frontend`** — CRA React, `./frontend/`, `npm start`. Volume-mounted for hot-reload.

### Backend layout (`./backend/`)

```
main.py              # App factory, CORS, TenantMiddleware, lifespan (seeds + per-tenant background jobs)
database.py          # SQLAlchemy engine (APP_DATABASE_URL), SessionLocal, Base, get_db(), current_tenant_id
                     #   ContextVar + the engine "begin" listener that applies SET LOCAL app.tenant_id
alembic/             # env.py + versions/ — schema migrations (see "Database Migrations" above)
limiter.py           # slowapi Limiter instance shared across routers
auth/
  jwt.py             # create_access_token / verify_token / get_current_user (validates JWT tenant_id
                     #   against request.state.tenant_id) / require_admin / require_medico
core/
  features.py        # PLAN_FEATURES, features_efectivas(tenant), require_feature(nombre) router dependency
  servicios.py       # capacidad() / tipos_validos() / hora_valida() / descripcion_ventana() — tenant-aware
                     #   replacements for the old hardcoded CAPACIDAD/TURNOS/TIPOS_VALIDOS dicts
  constants.py        # METODOS_PAGO, MAX_PASSWORD_BYTES — deduplicated, NOT tenant config (see Multi-Tenancy)
middleware/
  tenant.py          # TenantMiddleware (subdomain → X-Tenant-Slug [non-prod] → 404) + get_current_tenant dep
models/
  tenant.py          # Tenant table + DEFAULT_CONFIG + Tenant.get_config(ruta, default) — see Multi-Tenancy
  servicio.py        # Servicio table — per-tenant service catalog (nombre, capacidad, duracion_min)
  paciente.py        # Paciente table — composite PK (tenant_id, "Paciente") · habeas_data_aceptado · fecha_aceptacion_habeas
  usuario.py         # Staff/admin/patient/médico users — tenant_id, UNIQUE(tenant_id,id), UNIQUE(tenant_id,email) · bcrypt · es_admin · es_medico · habeas_data_aceptado
  cita.py            # Cita table — id (UUID), tenant_id, paciente_id (composite FK), fecha, hora, tipo, estado, notas, recordatorio_enviado,
                     #   medico_id (composite FK → usuarios, nullable), motivo_remision (nullable)
  pago.py            # Package purchase: tenant_id, tipo_paquete, total_sesiones, sesiones_restantes, fecha_pago, fecha_vencimiento
  venta.py           # Financial income: tenant_id, paciente_id (composite FK), nombre_paquete, categoria, total_sesiones, valor_total, abono, saldo, fecha, metodo_pago, estado (pagada|pendiente)
  gasto.py           # Financial expense: tenant_id, nombre, nit (nullable), valor, fecha, metodo_pago, descripcion (nullable)
routes/
  auth.py            # POST /auth/login → JWT (includes tenant_id, habeas_data_aceptado, es_medico, medico_id) · rate-limited 5/min
                     #   looks up Usuario by (tenant_id, email), not email alone
                     #   POST /auth/aceptar-habeas → persists consent + timestamps (requires JWT)
                     #   POST /auth/cambiar-password → any logged-in Usuario changes their own password (requires JWT)
  tenant.py          # GET /tenant/config — public, no JWT: nombre_comercial/branding/features/servicios/horario/sesion_cortesia
  pacientes.py       # Full CRUD /pacientes/ — require_admin
  citas.py           # Full CRUD /citas/ + background job procesar_citas_vencidas() — require_admin
                     #   CitaOut includes medico_id/medico_nombre/motivo_remision (resolved via _citas_out helper)
                     #   create_cita skips the active-plan check when medico_id is set (referral citas)
                     #   hora/tipo validity checked in the route body via core/servicios.py (not a Pydantic validator — see Multi-Tenancy)
  pagos.py           # POST /pagos/ + GET /pagos/?paciente_id= — require_admin
  portal.py          # Public (no JWT, but still tenant-resolved by TenantMiddleware): GET /portal/paciente/{cedula}
                     #   POST /portal/registro (nombre+cedula+telefono+email+habeas_data_aceptado REQUIRED true)
                     #   POST /portal/citas (new booking) · POST /portal/citas/recurrente
                     #   POST /portal/citas/{id}/cancelar (2h window enforced)
                     #   POST /portal/citas/{id}/reprogramar (2h window enforced)
  medicos.py         # require_feature("medicos"): GET/POST /medicos/ (list/create Usuario with es_medico=True)
  medico_portal.py   # require_feature("medico_portal") + require_medico: GET /medico/citas (own referrals only) · POST /medico/citas
                     #   (find-or-create Paciente by cédula + create Cita with medico_id/motivo_remision, no plan check)
  ventas.py          # require_feature("ventas") + require_admin: GET /ventas/ (filters: paciente_id, categoria, estado, fecha_desde, fecha_hasta)
                     #   POST /ventas/ → validates paciente, abono ≤ valor_total, computes saldo+estado, triggers send_confirmacion_pago in background
                     #   DELETE /ventas/{id}
  gastos.py          # require_feature("gastos") + require_admin: GET /gastos/ (date filters) · POST /gastos/ · DELETE /gastos/{id}
services/
  email.py           # send_confirmacion · send_recordatorio · send_confirmacion_pago via Resend API (HTTP, no SMTP)
                     #   reads RESEND_API_KEY + RESEND_FROM + PORTAL_URL + CLINIC_MAPS_URL at import time
                     #   send_confirmacion_pago: includes paquete, valor, abono, saldo, estado badge, 45-day expiry block (when total_sesiones set)
                     #   logs WARNING (not sent) when RESEND_API_KEY missing — still single-tenant (global env vars), not yet per-tenant branding
scripts/
  bootstrap_app_role.sql  # One-time per-environment: creates the app_user Postgres role RLS needs (see Multi-Tenancy)
```

> **bcrypt note:** `passlib[bcrypt]` is installed but NOT used — passlib 1.7.4 is incompatible with bcrypt 4.x (raises ValueError on startup). All password hashing uses `import bcrypt` directly.

### Frontend layout (`./frontend/src/`)

```
index.js                    # Entry, imports index.css (Tailwind)
App.js                      # TenantProvider > AuthProvider > Routes + HabeasDataModal
                            #   HabeasDataModal: z-[100] backdrop-blur overlay for habeas_data_aceptado=false
                            #   PolicyContent: reusable legal text component (Ley 1581/2012) — NOT tenant-dynamic (see Multi-Tenancy)
index.css                   # @tailwind base/components/utilities
api/
  client.js                 # Single axios instance — Authorization + X-Tenant-Slug (dev) injected via request interceptor.
                            #   Every other api/*.js file imports this instead of raw axios + local API_URL/authHeaders()
  tenant.js                 # getTenantConfig() → GET /tenant/config
  auth.js                   # loginRequest() · aceptarHabeasData() · cambiarPassword() — no longer take a token param,
                            #   client.js's interceptor reads sessionStorage itself
  pacientes.js              # getPacientes, getPaciente, createPaciente, updatePaciente, deletePaciente
  citas.js                  # getCitas, createCita, patchCitaEstado, updateCita, deleteCita
  pagos.js                  # getPagos, createPago
  portal.js                 # getPortalPaciente, portalRegistro, portalCrearCita, portalCrearCitaRecurrente,
                            #   portalCancelarCita, portalReprogramarCita
  medicos.js                # getMedicos, createMedico — admin médico management
  medicoPortal.js           # getMisCitas, crearCitaMedico — médico self-service
  ventas.js                 # getVentas, createVenta, deleteVenta
  gastos.js                 # getGastos, createGasto, deleteGasto
constants/
  packages.js               # METODOS_PAGO · CATEGORIAS · PACKAGES catalog (Pilates individual+x2, Fisioterapia, Combos, Prendas de Vestir)
                            #   Billing/catalog data — explicitly NOT converted to tenant config in Phase 1
context/
  AuthContext.js            # AuthProvider, useAuth() — JWT in sessionStorage (key: elysium_token)
                            # login() returns decoded payload · acceptHabeas() updates user state in-memory
  TenantContext.js          # TenantProvider, useTenant() — GET /tenant/config on mount, exposes
                            #   { tenant, features, servicios, horario, sesionCortesia, tiposCita, hasFeature() }
utils/
  schedule.js                # buildSlots(horario) — generates the time-slot list from horario.bloques/intervalo_min,
                            #   replaces the identical hardcoded loop that used to be copied in 3 pages
layouts/
  DashboardLayout.js        # Sidebar + TopBar + <Outlet />
components/
  Sidebar.js                # Dark (slate-900) sidebar, NavLink active = teal-600, lucide icons, "Cambiar contraseña" + logout
                            #   nav items filtered by hasFeature() (Médicos/Ventas/Gastos hidden if not in plan)
                            #   brand name/tagline read from tenant.nombre_comercial/tenant.branding.tagline
  CambiarPasswordModal.js   # Self-service password change (any Usuario) — POST /auth/cambiar-password
  TopBar.js                 # Page title bar, route → title map (fallback title = tenant.nombre_comercial)
  PrivateRoute.js           # Checks isAuthenticated AND user.es_admin=true; non-admin → /medico (es_medico) or /portal
  MedicoRoute.js             # Checks isAuthenticated AND user.es_medico=true; else → /login
  FeatureRoute.js            # Checks hasFeature(feature); redirects to /dashboard if the tenant's plan lacks it
                            #   (wraps /medicos, /ventas, /gastos in App.js)
pages/
  LoginPage.js              # Login form — redirects to /dashboard (admin), /medico (médico), or /portal (patient)
  DashboardHome.js          # Real stats: citas hoy/semana/mes by tipo, pacientes activos/inactivos, próxima cita,
                            #   "Citas de hoy" table shows médico remitente ("Directo" if none)
                            #   PieChart (recharts donut) of current-month ventas by categoria
  PacientesPage.js          # Searchable table + create/edit modal + delete confirm
  NuevaCitaPage.js          # Admin appointment booking form + optional "Médico en convenio" select + motivo_remision
                            #   tipo options + time slots from useTenant() (tiposCita/buildSlots), not hardcoded arrays
  AgendaPage.js             # Weekly view Lun–Sáb, slots from buildSlots(horario), capacity badges from useTenant().servicios,
                            #   estado modal (shows médico remitente)
  PortalPage.js             # Patient self-service: cedula entry OR auto-load (if logged in),
                            #   plan card + progress bar, upcoming citas with cancel/reschedule buttons,
                            #   booking form (tipo/slots from useTenant()), self-register form (email + habeas checkbox + policy modal)
                            #   Habeas Data checkbox text + policy modal content are NOT tenant-dynamic (legal text, out of scope)
  MedicosPage.js            # Admin: table of médicos + "Nuevo médico" modal (nombre/email/password)
  MedicoPortalPage.js       # Médico self-service: "Mis pacientes/citas" tab + "Agendar nuevo paciente" tab
                            #   tipo options + slots from useTenant() (no cortesía — servicios never include it)
  VentasPage.js             # Income module: NuevaVentaModal (patient search, categoria→paquete autofill, live saldo),
                            #   PAID/PENDING badges, summary cards (total, ingresos mes, pendientes)
  GastosPage.js             # Expense module: NuevoGastoModal (nombre, nit optional, valor, metodo_pago, descripcion)
```

### Routing structure

```
/login                    → LoginPage (public) — redirects by role after login
/portal                   → PortalPage (public) — anonymous (cedula) or authenticated (email+password)
/medico                   → MedicoRoute (es_medico=true required) → MedicoPortalPage
/ (PrivateRoute — admin only, es_admin=true required)
  /dashboard              → DashboardHome (real stats + PieChart ventas)
  /agenda                 → AgendaPage
  /pacientes              → PacientesPage
  /nueva-cita             → NuevaCitaPage
  /medicos                → FeatureRoute("medicos")    → MedicosPage
  /ventas                 → FeatureRoute("ventas")     → VentasPage
  /gastos                 → FeatureRoute("gastos")     → GastosPage
```

`FeatureRoute` redirects to `/dashboard` if the tenant's plan lacks the feature — independent of `PrivateRoute`'s auth check, both must pass. `/medico` (médico portal) is intentionally **not** wrapped in a `FeatureRoute` — `MedicoRoute`'s `es_medico` check is the only frontend gate there; the backend still 403s `/medico/*` calls via `require_feature("medico_portal")` if the tenant lacks it.

### JWT payload structure

```json
{
  "sub": "admin@elysium.com",
  "tenant_id": "7a1c8740-8ff3-4afd-8bd7-74d5da0ce9b8",
  "nombre": "Administrador",
  "es_admin": true,
  "es_medico": false,
  "medico_id": null,
  "paciente_id": null,
  "habeas_data_aceptado": false,
  "exp": 1234567890
}
```

- `tenant_id` — set at login from the **host-resolved** tenant (never client input). `get_current_user` 401s if it doesn't match `request.state.tenant_id` on every subsequent request — see "Multi-Tenancy" below.
- `es_admin=true` → admin, access to all protected routes
- `es_medico=true` + `medico_id=<usuario.id>` → médico externo en convenio, portal auto-scopes to their own referrals
- `es_admin=false` + `es_medico=false` + `paciente_id="00000001"` → patient, portal auto-loads their data
- `habeas_data_aceptado=false` → frontend shows `HabeasDataModal` blocking the UI until accepted
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
| tenant_id | UUID | FK → tenants.id |
| paciente_id | String | composite FK (tenant_id, paciente_id) → pacientes(tenant_id, "Paciente") |
| tipo_paquete | String | e.g. "Pilates", "Fisioterapia" |
| total_sesiones | Integer | |
| sesiones_restantes | Integer | decremented by backend only |
| fecha_pago | Date | when the payment was registered — admin-provided, may lag `fecha_inicio` (e.g. paid in installments) |
| fecha_inicio | Date | when the plan actually starts — admin-provided, independent of `fecha_pago` (added post-Phase-1, migration `0004`) |
| fecha_vencimiento | Date | computed server-side: `fecha_inicio + tenant.get_config("vigencia_plan_dias")` (Elysium: 45 days) — **not** `fecha_pago` |

### Data model — `ventas` table

| Column | Type | Notes |
|--------|------|-------|
| id | String (UUID) | PK |
| tenant_id | UUID | FK → tenants.id |
| paciente_id | String | composite FK (tenant_id, paciente_id) → pacientes(tenant_id, "Paciente") |
| nombre_paquete | String | e.g. "Plan Pro 8 Ses – Individual" |
| categoria | String | Pilates \| Fisioterapia \| Combos \| Prendas de Vestir — billing catalog, not tenant config (see Multi-Tenancy) |
| total_sesiones | Integer (nullable) | null for Prendas de Vestir |
| valor_total | Float | |
| abono | Float | amount paid up-front |
| saldo | Float | computed: valor_total − abono |
| fecha | Date | payment date (admin-provided) |
| metodo_pago | String | Efectivo \| Transferencia \| Tarjeta \| Otro |
| estado | String | pagada (saldo==0) \| pendiente (saldo>0) |

### Data model — `gastos` table

| Column | Type | Notes |
|--------|------|-------|
| id | String (UUID) | PK |
| tenant_id | UUID | FK → tenants.id |
| nombre | String | vendor/concept |
| nit | String (nullable) | vendor tax ID |
| valor | Float | |
| fecha | Date | |
| metodo_pago | String | Efectivo \| Transferencia \| Tarjeta \| Otro |
| descripcion | String (nullable) | free text |

### Data model — `tenants` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, `gen_random_uuid()` |
| slug | String | UNIQUE — subdomain, e.g. `"elysium"` |
| nombre_comercial | String | display name |
| plan | String | `"basico"` \| `"completo"` — see `core/features.py:PLAN_FEATURES` |
| estado | String | `"trial"` \| `"activo"` \| `"suspendido"` |
| custom_domain | String (nullable) | UNIQUE — whitelabel domain, not wired to real DNS yet |
| timezone | String | default `"America/Bogota"` |
| branding | JSONB | default `{}` — e.g. `{"tagline": "..."}`; colors not themed yet beyond the fallback zinc palette |
| config | JSONB | default `{}` — merged over `DEFAULT_CONFIG` in `models/tenant.py` via `Tenant.get_config()` |
| features_override | JSONB | default `{}` — `{"habilitadas": [...], "deshabilitadas": [...]}`, adjusts `plan` defaults per tenant |
| created_at | Timestamp | |

### Data model — `servicios` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants.id |
| nombre | String | e.g. "Pilates", "Fisioterapia" — `UNIQUE(tenant_id, nombre)` |
| capacidad | Integer | max concurrent patients per slot |
| duracion_min | Integer | session length |
| activo | Boolean | default true |

"Sesión de cortesía" has **no row here** — see "Multi-Tenancy" below.

### Patient registration flow

New patients self-register via `/portal` → "Crea tu perfil aquí":
1. `POST /portal/registro` — creates `pacientes` record with nombre, cedula, telefono, email (409 if cedula OR email already exists)
2. Portal shows their empty dashboard: no plan, no citas, welcome message
3. Admin completes full profile (fecha_nacimiento, antecedentes, cirugias) from PacientesPage when they attend their first session
4. Admin registers payment → plan activates → patient can book sessions

## Multi-Tenancy (Phase 1 of 4 — complete)

The app is being converted from single-tenant to a multi-tenant SaaS, on `feature/multi-tenant` (off `main`). **Phase 1** — data layer, tenant context, config system — is done. Elysium is still the only tenant in practice, but the whole stack is now tenant-aware. **Not yet built** (later phases): tenant admin UI, wildcard DNS / real subdomain routing, WhatsApp, self-service onboarding, billing.

### Tenant model

- `models/tenant.py` — `Tenant` (`tenants` table, see data model above). `Tenant.get_config(ruta, default)` reads a dotted path (e.g. `"horario.intervalo_min"`) from `config`, deep-merged over `DEFAULT_CONFIG` in the same file — a new tenant never needs to set the full JSON:
  ```json
  {
    "vigencia_plan_dias": 45,
    "ventana_cancelacion_horas": 2,
    "horario": {
      "bloques": [{"inicio": "07:00", "fin": "11:00"}, {"inicio": "14:00", "fin": "18:00"}],
      "intervalo_min": 30,
      "dias_activos": [1, 2, 3, 4, 5, 6]
    },
    "sesion_cortesia": {"habilitada": true, "duracion_min": 45, "max_por_paciente": 1}
  }
  ```
  `horario.bloques` is a **list** of blocks (not a single `hora_inicio`/`hora_fin` pair) specifically so a midday gap can be represented — Elysium's config keeps the 11:30–13:30 gap blocked this way.
- `models/servicio.py` — `Servicio` (see data model above). Replaces the old hardcoded `CAPACIDAD = {...}` dicts. **"Sesión de cortesía" has no row of its own** — it reuses the "Pilates" servicio's capacity (same physical class); its duration/limit come from `config.sesion_cortesia` instead.

### `tenant_id` and composite keys

All 6 original tables got a `tenant_id UUID NOT NULL` column (Alembic `0002`):
- `pacientes` PK became **composite** `(tenant_id, "Paciente")` — the cédula can legitimately repeat across tenants. Every `db.get(Paciente, x)` call in the codebase had to become `db.get(Paciente, (tenant_id, x))` — 14 call sites across `citas.py`, `portal.py`, `medico_portal.py`, `ventas.py`, `pacientes.py`, `main.py`.
- `usuarios` keeps its single-column PK on `id` (its own `uuid4()`, collision-safe across tenants) but gained `UNIQUE(tenant_id, id)` (needed so `citas.medico_id` can have a composite FK) and `UNIQUE(tenant_id, email)` (replacing the old global-unique `email`).
- `citas`, `pagos`, `ventas` got composite FKs `(tenant_id, paciente_id) → pacientes(tenant_id, "Paciente")`; `citas` also `(tenant_id, medico_id) → usuarios(tenant_id, id)`.
- `gastos` has no patient FK, just `tenant_id → tenants.id`.

Migration `0002` was tested reversible (`alembic downgrade -1`) against real data, but **only while a single tenant exists** — see the warning in the migration file's own docstring (downgrading after a second tenant exists would merge or reject their data).

### Row-Level Security

Alembic `0003` adds `ENABLE`/`FORCE ROW LEVEL SECURITY` + a `tenant_isolation` policy (`USING`/`WITH CHECK` on `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`) to every tenant-scoped table (`pacientes, usuarios, citas, pagos, ventas, gastos, servicios` — **not** `tenants`, which has no `tenant_id` of its own and is queried to resolve one in the first place).

**Empty-string gotcha (found by `tests/test_tenant_isolation.py`, not obvious from reading the SQL):** `current_setting('app.tenant_id', true)` returns NULL only when the GUC has *never* been touched on that physical connection. `SET LOCAL` reverts to the GUC's prior value when its transaction ends — and on a **pooled connection that previously had `app.tenant_id` set** (any earlier, committed request on that same connection), the prior value is an empty string `''`, not NULL. Casting `''::uuid` directly raises `invalid input syntax for type uuid` instead of cleanly filtering to zero rows. Verified empirically via `psql`: same session, `SET LOCAL app.tenant_id = '<uuid>'; COMMIT;` then a later transaction with no `SET LOCAL` sees `current_setting(...) = ''`. The `NULLIF(..., '')` wrapper folds that back to a real NULL before the cast — required for correctness on *any* pooled connection, i.e. always, in this app. Don't drop it if you ever touch this policy.

RLS only restricts a **non-superuser, non-table-owner** role — `admin` (the table owner in `docker-compose.yml`, a Postgres superuser) always bypasses it regardless of `FORCE`. The running app connects as `app_user` instead:

- `backend/scripts/bootstrap_app_role.sql` — creates the role + grants (`SELECT` on `tenants`; `SELECT/INSERT/UPDATE/DELETE` on the 7 RLS-protected tables). **Not** an Alembic migration on purpose — `CREATE ROLE` is cluster-wide (not per-database) and needs a real per-environment secret that must never live in a committed migration. Run once per environment:
  - Local: edit the `CHANGE_ME` password in the script, then `docker compose exec -T db psql -U admin -d elysium_agenda < backend/scripts/bootstrap_app_role.sql` — match the same password in `docker-compose.yml`'s `APP_DATABASE_URL`.
  - Railway: paste it into the Postgres plugin console with a real generated secret, then set `APP_DATABASE_URL` on the backend service.
- `database.py` — `APP_DATABASE_URL` is what `engine`/`SessionLocal` connect with at runtime; falls back to `DATABASE_URL` (admin) with a `logger.warning` if unset — same pattern as the existing `RESEND_API_KEY` fallback. Alembic (`alembic/env.py`) always uses `DATABASE_URL` directly, never `APP_DATABASE_URL` — migrations need full DDL rights and must work before `app_user`/RLS exist at all.

**`SET LOCAL` gotcha:** it only lasts for the current transaction, and most routes `db.commit()` mid-request and keep using the same session afterward (e.g. `db.refresh()` right after commit — `create_cita` does exactly this). Setting it once in `get_db()` would silently lose tenant context after the first commit. The actual mechanism: `database.py` registers `@event.listens_for(engine, "begin")`, which runs `SET LOCAL app.tenant_id = ...` on **every** new transaction, reading from a `contextvars.ContextVar` (`current_tenant_id`) — not `request.state`, since the event listener has no access to the `Request`. `TenantMiddleware` sets this ContextVar at the start of a request and resets it in a `finally`. Background jobs (`_job_citas_vencidas`, `_job_recordatorios` in `main.py`) don't go through the middleware, so they loop over every active tenant themselves, setting the ContextVar per iteration (with per-tenant error isolation, so one tenant failing doesn't skip the rest).

FK checks always bypass RLS (documented Postgres behavior) — the composite FKs above are what actually stop a `citas.tenant_id`-correct-but-`paciente_id`-wrong-tenant row; RLS and the composite FKs are complementary, not redundant.

### Tenant resolution (`TenantMiddleware`)

`backend/middleware/tenant.py`, registered before `CORSMiddleware` in `main.py`. Order, per request:
1. Subdomain of the `Host` header (or an exact match against a tenant's `custom_domain`).
2. `X-Tenant-Slug` header — **only** when `RAILWAY_ENVIRONMENT != "production"` (local/dev convenience — `localhost` has no real subdomain).
3. Otherwise: `404 {"detail": "No encontrado"}` — never reveals whether a slug exists.

`/health` is exempt (deployment healthchecks have no tenant context). The resolved tenant lands on `request.state.tenant`/`request.state.tenant_id`; `middleware/tenant.py:get_current_tenant` is a FastAPI dependency (`tenant: Tenant = Depends(get_current_tenant)`) for routes that need `tenant.get_config(...)`.

**Local dev:** the frontend sends `X-Tenant-Slug: elysium` on every request (`REACT_APP_TENANT_SLUG` env var, read by `frontend/src/api/client.js`'s axios interceptor).

### JWT ↔ tenant binding

JWT payload now includes `tenant_id` (set at login from the host-resolved tenant, never client input — see JWT payload structure above). `get_current_user` (`auth/jwt.py`) 401s (same generic message as an invalid signature) if `payload["tenant_id"] != request.state.tenant_id` — **the host is authoritative; the JWT is only ever validated against it.** `POST /auth/login` looks up `Usuario` by `(tenant_id, email)`, not email alone.

### Feature flags (plan gating)

`backend/core/features.py`:
```python
PLAN_FEATURES = {
    "basico":   {"citas", "pacientes", "pagos", "portal", "auth"},
    "completo": {"citas", "pacientes", "pagos", "portal", "auth",
                 "ventas", "gastos", "medicos", "medico_portal", "dashboard_metrics"},
}
```
`features_efectivas(tenant)` = plan defaults adjusted by `tenant.features_override`. `require_feature(nombre)` is a router-level dependency (`app.include_router(ventas.router, ..., dependencies=[Depends(require_feature("ventas"))])`) applied to `ventas`, `gastos`, `medicos`, `medico_portal` only — `basico`-tier routers (`citas`, `pacientes`, `pagos`, `portal`, `auth`) are intentionally never gated, since every plan includes them. `dashboard_metrics` has no dedicated backend endpoint — gated frontend-side only (`hasFeature('dashboard_metrics')`, not yet actually applied to `DashboardHome.js`'s PieChart — flagged as a follow-up, see below).

`GET /tenant/config` (public, no JWT) returns `nombre_comercial`, `branding`, `features` (list), `servicios` (active), `horario`, `sesion_cortesia`. **Never** exposes `plan`, `estado`, `id`, or `custom_domain`. Consumed by the frontend's `TenantContext`.

#### Features-by-plan reference

| Feature | básico | completo | Gates |
|---|:---:|:---:|---|
| `auth`, `citas`, `pacientes`, `pagos`, `portal` | ✅ | ✅ | never gated (every plan) |
| `ventas` | ❌ | ✅ | `/ventas/*`, Sidebar "Ventas", `/ventas` route |
| `gastos` | ❌ | ✅ | `/gastos/*`, Sidebar "Gastos", `/gastos` route |
| `medicos` | ❌ | ✅ | `/medicos/*`, Sidebar "Médicos", `/medicos` route |
| `medico_portal` | ❌ | ✅ | `/medico/*` (médico's own citas/booking) |
| `dashboard_metrics` | ❌ | ✅ | intended for the Dashboard PieChart — flag not yet wired into `DashboardHome.js` |

Override per tenant: `UPDATE tenants SET features_override = '{"habilitadas": ["ventas"]}'::jsonb WHERE slug = '...'`.

### Business-rule constants are now tenant config

`backend/core/servicios.py` replaces the old hardcoded `CAPACIDAD`/`TURNOS`/`TIPOS_VALIDOS` dicts that used to be copy-pasted (inconsistently — `medico_portal.py`'s `CAPACIDAD` was missing cortesía, `pagos.py`'s `TIPOS_VALIDOS` differed from `citas.py`'s) across `citas.py`, `portal.py`, `medico_portal.py`, `pagos.py`:
- `capacidad(db, tipo)` — reads from `servicios` (cortesía reuses Pilates').
- `tipos_validos(db, tenant, incluir_cortesia=True)` — active servicios + the cortesía pseudo-type when enabled; callers can pass `incluir_cortesia=False` (médico portal, pagos never offer it, by design, not a bug).
- `hora_valida(tenant, hora)` / `descripcion_ventana(tenant)` — schedule-window + slot-grid check, and a dynamically-built error message (no more hardcoded "07:00–11:00 · 14:00–18:00" string).

**Important gotcha:** `hora`/`tipo` validation used to live in Pydantic `@field_validator`s — those run before a DB session or tenant exists, so they **can't** call `tenant.get_config()` or query `servicios`. This validation moved into each route's body instead (still 422 on failure, via `HTTPException` rather than a Pydantic `ValueError` — actually more consistent with the rest of the codebase's style, which already used inline `HTTPException` for capacity/plan checks).

`VIGENCIA_DIAS`/`HORAS_CANCELACION` → `tenant.get_config("vigencia_plan_dias")` / `tenant.get_config("ventana_cancelacion_horas")`. `METODOS_PAGO` and the bcrypt `MAX_PASSWORD_BYTES` limit were also deduplicated into `backend/core/constants.py` — these are **not** tenant config, just code that used to be hand-copied identically in two files each.

**Explicitly out of scope for Phase 1** (seen, deliberately not touched): `frontend/src/constants/packages.js` (pricing/package catalog) and `routes/ventas.py`'s `CATEGORIAS_VALIDAS` — billing/catalog data, not scheduling config. Also the Habeas Data legal text (`PolicyContent` in `App.js`, and its near-duplicate inline in `PortalPage.js`) — regulatory copy specific to Colombia/Elysium, no tenant legal-config system exists yet.

### Adding a new tenant (still manual — no admin UI until a later phase)

```sql
INSERT INTO tenants (id, slug, nombre_comercial, plan, estado, timezone, config)
VALUES (gen_random_uuid(), 'nuevo-slug', 'Nombre Comercial', 'basico', 'activo',
        'America/Bogota', '{}'::jsonb);  -- {} inherits every DEFAULT_CONFIG value

INSERT INTO servicios (tenant_id, nombre, capacidad, duracion_min, activo)
VALUES ('<tenant id above>', 'Pilates', 6, 60, true),
       ('<tenant id above>', 'Fisioterapia', 2, 60, true);
```
Then create an admin `Usuario` for that tenant by hand (`tenant_id` + `email` + bcrypt `hashed_password` + `es_admin=true`) — there's no seed script for a second tenant yet; `_seed_admin()`/`_seed_paciente()` in `main.py` are still hardcoded to Elysium. Locally, test the new tenant with `X-Tenant-Slug: nuevo-slug`.

### Environment variables added

| Variable | Where | Purpose |
|---|---|---|
| `APP_DATABASE_URL` | backend | Runtime connection as `app_user` (non-superuser) — required for RLS to have any effect. Falls back to `DATABASE_URL` (admin, bypasses RLS) with a warning if unset. |
| `REACT_APP_TENANT_SLUG` | frontend (dev only) | Lets `localhost` resolve a tenant without real subdomains — sent as `X-Tenant-Slug`. |

## Current Status

**All core features complete:**
- [x] Full Docker Compose setup (db + backend + frontend) with healthcheck
- [x] JWT auth with role-based redirect: admin → `/dashboard`, patient → `/portal`
- [x] Admin and test patient auto-seeded on startup
- [x] Dashboard layout: dark sidebar, nav with icons, topbar, user info + logout
- [x] Dashboard home: real stats — citas hoy/semana/mes split by Pilates/Fisio, pacientes activos/inactivos, próxima cita + today's table
- [x] `backend/models/paciente.py` + full CRUD `routes/pacientes.py` (require_admin)
- [x] `frontend/src/pages/PacientesPage.js` — searchable table + create/edit modal + delete confirm
- [x] `backend/models/cita.py` + `routes/citas.py` — full CRUD + all validations + background auto-penalty job + PostgreSQL advisory lock
- [x] `backend/models/pago.py` + `routes/pagos.py` — plan management
- [x] `frontend/src/pages/NuevaCitaPage.js` — admin appointment booking form
- [x] `frontend/src/pages/AgendaPage.js` — weekly view + estado modal + capacity badges
- [x] `backend/routes/portal.py` — public routes: lookup, registro, booking, cancelar, reprogramar
- [x] `frontend/src/pages/PortalPage.js` — patient portal: anonymous + authenticated + self-register + cancel/reschedule modals
- [x] Email confirmación automática vía Resend API (booking + 24h reminder job) — `RESEND_API_KEY` / `RESEND_FROM` (Railway blocks SMTP port 587; HTTP API bypasses this)
- [x] Monochromatic zinc/gray brand identity across all pages and email templates
- [x] Deployed to Railway (backend + PostgreSQL plugin + frontend)
- [x] Security hardening: require_admin, sessionStorage JWT, rate limiting, /docs disabled in prod, advisory lock, input validation
- [x] **Habeas Data (Ley 1581/2012):** consent fields on `usuarios` and `pacientes`; `POST /auth/aceptar-habeas`; JWT carries `habeas_data_aceptado`; `HabeasDataModal` intercepts existing users; checkbox + policy modal on registration form
- [x] **Médicos Externos en Convenio (v2.0):** `es_medico` role on `Usuario`; `medico_id`/`motivo_remision` on `Cita`; `routes/medicos.py` (admin CRUD) + `routes/medico_portal.py` (médico self-service, no active-plan requirement); `/medico` and `/medicos` frontend routes; médico remitente visible in `AgendaPage`/`DashboardHome`/`NuevaCitaPage`
- [x] **Módulo financiero (Ventas + Gastos):** `models/venta.py` + `models/gasto.py`; `routes/ventas.py` + `routes/gastos.py` (require_admin); `VentasPage.js` (autofill catálogo, badges Pagado/Pendiente, abono/saldo live); `GastosPage.js`; PieChart en Dashboard (recharts donut, ventas del mes por categoría); `send_confirmacion_pago` con bloque de vigencia 45 días
- [x] **Multi-tenancy — Fase 1 de 4 (`feature/multi-tenant`):** Alembic (revisiones `0001`–`0003`); `models/tenant.py` + `models/servicio.py`; `tenant_id` + claves compuestas en las 6 tablas originales; Row-Level Security + rol `app_user`; `TenantMiddleware` + `SET LOCAL` vía `ContextVar`/event listener; JWT con `tenant_id`; `core/features.py` (feature flags por plan) + `GET /tenant/config`; `core/servicios.py` (constantes de negocio → config por tenant); `TenantContext` + `FeatureRoute` + `api/client.js` en el frontend; `tests/test_tenant_isolation.py` (7 tests, `pytest`/`httpx` agregados a `requirements.txt`) — cubre los criterios de aceptación 1–7, y fue lo que encontró el gotcha del string vacío en la política RLS documentado arriba. Ver sección "Multi-Tenancy" arriba.

**Next to build:**
- [ ] **Fases 2–4 del multi-tenant:** UI de administración de tenants, wildcard DNS/subdominios reales, onboarding self-service, facturación
- [ ] `dashboard_metrics` feature flag no está aplicada todavía en `DashboardHome.js` (el PieChart de ventas es visible para cualquier plan)
- [ ] `PortalPage.js`'s `canModify(cita)` sigue con 2h hardcodeado en vez de leer `useTenant()` (solo afecta cuándo se deshabilitan los botones en la UI — el backend ya usa `tenant.get_config`, así que no es un hueco de seguridad)
- [ ] **Notificaciones WhatsApp** — n8n webhook → WhatsApp API (Meta) recordatorio 24h antes de la cita
- [ ] Configurar `PORTAL_URL` en Railway apuntando al frontend (el correo de pago ya lo usa, pero el default es localhost)

## Critical Design Rules

1. **Database identifier:** Always use the column named `Paciente` (never `ID_Paciente` or any variant) as the primary key/identifier in patient-related tables. As of Phase 1 multi-tenant, `pacientes`' PK is **composite** `(tenant_id, "Paciente")` — the column name rule still holds, but any `db.get(Paciente, x)` needs the tuple `(tenant_id, x)`, not a bare cédula.

2. **Auth:** JWT via `python-jose`. Use `bcrypt` directly (not `passlib.CryptContext`). Token stored in `sessionStorage` under key `elysium_token`. JWT payload always includes `tenant_id` (str), `es_admin` (bool), `es_medico` (bool), `medico_id` (str | null), and `paciente_id` (str | null). Admin-only routes use `require_admin`; médico-only routes use `require_medico` (both in `auth/jwt.py`) — never bare `get_current_user` for role-gated routes. `get_current_user` also 401s if the JWT's `tenant_id` doesn't match the host-resolved tenant — see "Multi-Tenancy" above.

3. **Plan expiration:** Always computed server-side as `fecha_inicio + timedelta(days=tenant.get_config("vigencia_plan_dias"))` (Elysium: 45) — **based on `fecha_inicio` (the plan's start date), not `fecha_pago` (the payment date)**, since a client may start a plan before finishing payment on it. Never accept `fecha_vencimiento` from the client, never hardcode the day count — read it from tenant config (`routes/pagos.py:create_pago`).

4. **Session deduction:** `sesiones_restantes` is decremented by the backend only — never by the frontend. Triggered on estado = `"completada"` or `"No asistió con penalización"`. Booking does NOT deduct (only checks availability).

5. **Capacity/schedule/type constants (never hardcode inline):** As of Phase 1 multi-tenant, none of `CAPACIDAD`, `TURNOS`, `TIPOS_VALIDOS`, `HORAS_CANCELACION`, `VIGENCIA_DIAS` exist as hardcoded dicts anymore — they come from `servicios` (capacity, valid types) and `tenant.config` (schedule window, cancellation window, plan validity) via `backend/core/servicios.py`. Do not reintroduce a hardcoded copy in a route file — add a helper to `core/servicios.py` instead. `METODOS_PAGO` and `MAX_PASSWORD_BYTES` are the one exception: pure code dedup in `core/constants.py`, not tenant config, since they're not business rules that vary per tenant.

6. **Code style:** Modules small and focused: routes only route, models only define schema, business logic in routes. No excessive comments.

7. **Color palette:** zinc-800/900/950 (primary actions, sidebar background, brand dark), zinc-700 (active nav), slate-50 (page background), white (cards). Semantic colors kept: red (errors), green (success), amber (warnings).

8. **Timezone gotcha:** Never use `new Date().toISOString().split('T')[0]` — returns UTC date. Always use local date methods: `getFullYear() / getMonth() / getDate()`. Applied in `DashboardHome.js`, `AgendaPage.js`, and `PortalPage.js`.

9. **Schema migrations:** Every schema change is an Alembic revision (`backend/alembic/versions/`) — see "Database Migrations (Alembic)" above. `create_all`/`_run_migrations()` no longer exist; do not reintroduce ad hoc `ALTER TABLE` calls at startup.

10. **Portal cancellation window:** Cancel and reschedule from the patient portal are blocked server-side when `datetime.now() >= cita_datetime - tenant.get_config("ventana_cancelacion_horas")` (Elysium: 2h). The frontend's `canModify(cita)` in `PortalPage.js` still hardcodes 2h to disable buttons early (a pre-Phase-1 shortcut, not yet wired to `useTenant()`) — the backend is the source of truth regardless, so this is a display-only staleness, not a security gap.

11. **Habeas Data flow:** `habeas_data_aceptado` lives on both `Usuario` (for login-based users) and `Paciente` (for anonymous registrations). New patients: checkbox required in portal registration form (backend validates `habeas_data_aceptado=true`). Existing users: JWT carries the field; `HabeasDataModal` in `App.js` intercepts the UI when `user.habeas_data_aceptado === false` and calls `POST /auth/aceptar-habeas`. `acceptHabeas()` in `AuthContext` updates React state in-memory without requiring a re-login. Timestamp stored as UTC via `datetime.utcnow()`.

12. **Email background task + ORM detachment:** When passing ORM objects to FastAPI `background_tasks.add_task()`, always call `db.refresh(obj)` on any object loaded **before** `db.commit()`. After commit, SQLAlchemy expires those objects' attributes; by the time the background task runs the session is already closed, causing a silent `DetachedInstanceError`. Objects loaded **after** `db.commit()` are fresh and safe to pass directly.

13. **Médico referral citas skip the active-plan check:** A cita is a "referral" when `medico_id` is set (created via `POST /medico/citas` or `POST /citas/` with `medico_id`). These do **not** require an active `Pago` — the patient typically hasn't purchased a package yet. `_descuenta_sesion(db, paciente_id, required=...)` in `routes/citas.py` takes a `required` flag: `patch_estado` calls it with `required=(cita.medico_id is None)` so marking a referral cita as `completada`/no-show doesn't 422 when there's no plan — it just skips the deduction (same tolerant behavior `procesar_citas_vencidas` already had). When creating a `Paciente` and a `Cita` in the same request (see `medico_portal.py`), call `db.flush()` right after `db.add(paciente)` — there is no ORM `relationship()` between the two, so SQLAlchemy won't auto-order the inserts and the `Cita` insert will fail on the FK constraint if the `Paciente` row isn't flushed first.

14. **Every new row needs `tenant_id`:** Any `Paciente(...)`, `Usuario(...)`, `Cita(...)`, `Pago(...)`, `Venta(...)`, or `Gasto(...)` constructor must set `tenant_id` explicitly (`current_tenant_id.get()` inside a route, or the resolved `Tenant.id` in a background job/seed) — it's `NOT NULL` with no default. Forgetting it isn't caught until the `INSERT` fails (either a `NOT NULL` violation, or — worse, silently — an RLS `WITH CHECK` rejection if `tenant_id` were somehow `NULL` and a policy comparison happened to let it through, which it won't, but don't rely on RLS to catch a missing tenant_id at the ORM layer).

15. **RLS `SET LOCAL` must be re-applied every transaction, not once per request:** See "Multi-Tenancy → Row-Level Security" above for the full mechanism (`current_tenant_id` ContextVar + `@event.listens_for(engine, "begin")`). The short version: never assume a single `SET LOCAL app.tenant_id` at the top of `get_db()` is enough — any route that `db.commit()`s and keeps using the session (common in this codebase) opens a fresh transaction that needs its own `SET LOCAL`, which is exactly what the "begin" listener automates. Don't hand-roll a different tenant-context mechanism per route.

16. **Pydantic `@field_validator`s can't see the tenant:** They run during request parsing, before `get_db()`/`TenantMiddleware`'s dependencies resolve. Any validation that needs `tenant.get_config(...)` or a `servicios` lookup (schedule window, valid `tipo`, capacity) must happen in the route body, not a Pydantic validator — see `core/servicios.py` and how `routes/citas.py`/`portal.py`/`medico_portal.py`/`pagos.py` call it post-`Depends(get_current_tenant)`. Only tenant-independent structural checks (e.g. `hora.second == 0`, non-empty strings, email regex) belong in a validator now.
