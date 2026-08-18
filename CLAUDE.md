# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Elysium Fisio-Pilates** — appointment scheduling PWA for a single-location physiotherapy/pilates clinic. Access is primarily driven by scanning a QR Code or opening a direct link, guiding users to a lightweight registration screen.

> **Multi-tenant conversion in progress (`feature/multi-tenant` branch, off `main`):** Phase 1 of 4 (data layer, tenant context, config system) is **complete**. **Phase 2 (subdomain routing) is complete** (2.2 frontend runtime URL/tenant resolution, 2.3 backend reserved-slug + suspended-tenant checks, 2.4 dynamic CORS, 2.5 per-tenant email branding, 2.6 `crear_tenant.py` onboarding script) — see "Multi-Tenancy" section below, in particular "Phase 2". Elysium is still the only tenant in practice, but every table is now tenant-scoped with Row-Level Security, business rules are per-tenant config instead of hardcoded, and the app is ready to actually route by subdomain once wildcard DNS is connected. Not yet built: tenant admin UI, wildcard DNS itself, WhatsApp, self-service onboarding, billing — those are Phases 3–4.

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

> **Tenant header required for every request:** since Phase 1, every backend request must resolve a tenant (`TenantMiddleware`) or it 404s — including `curl`/Swagger testing. Locally this happens automatically for the frontend (`REACT_APP_DEV_TENANT_SLUG=elysium` in `docker-compose.yml`, read via `frontend/src/config/runtime.js`), but manual API calls (`curl`, Postman, `/docs`) need `-H "X-Tenant-Slug: elysium"` explicitly.

## Core Business Rules & Policies

> These describe Elysium's **current configured values** — as of Phase 1 they live in `tenants.config` (per-tenant, via `Tenant.get_config()`), not hardcoded constants. A different tenant could configure different numbers; see "Multi-Tenancy" below for where each value actually lives now.

1. **Plan Expiration Rule (45-Day Validity):**
   - When an Admin registers a payment or assigns a package, the system must log: package type, total sessions, the payment date, and the plan's **start date** (`fecha_inicio`) — clients don't always start using a plan the same day it's fully paid (e.g. start the 1st, finish paying in installments by the 10th/25th/30th), so the two dates are captured independently.
   - The expiration date must be automatically computed by the backend as exactly **45 calendar days** starting from the plan's **start date** (`fecha_inicio`), not the payment date.
   - Sessions can only be booked if the appointment date is less than or equal to the plan's expiration date.

2. **Strict Cancellation & No-Show Policy (2-Hour Window) — patient portal only:**
   - Patients can freely cancel or reschedule an appointment from their panel **only if there are more than 2 hours remaining** before the appointment's start time (`routes/portal.py`).
   - If a patient attempts to cancel within the 2-hour window, or fails to show up (No-Show), the system must mark the appointment status as `'No asistió con penalización'` and **automatically deduct 1 session** from their `sesiones_restantes`.
   - A background asyncio job runs every 5 minutes and auto-penalizes past appointments that were never resolved.
   - **The admin is not subject to this window.** `PATCH /citas/{id}/estado` (used by Agenda/Dashboard) no longer auto-converts a `"cancelada"` request into a penalty based on timing — that auto-conversion was removed because it applied the patient's rule to admin actions too, which felt like the app was silently "deciding" for the admin. The admin now picks explicitly between 5 actions, all in `frontend/src/components/CitaEstadoModal.js`: Confirmar, Completada (descuenta), No asistió (descuenta — also the button to use for a late cancellation that should be penalized), Reagendar (no descuenta, via `ajuste-admin`), Cancelar sin descontar (no descuenta, via `ajuste-admin`).

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
- `0004_pago_fecha_inicio` — adds `pagos.fecha_inicio` (nullable → backfilled from `fecha_pago` → `SET NOT NULL`), so `fecha_vencimiento` is computed from the plan's start date instead of its payment date (see Critical Design Rule #3). The backfill `DISABLE`s/`ENABLE`s+`FORCE`s RLS around the `UPDATE` — see Critical Design Rule #17 and the migration docstring.
- `0005_venta_pago_link` — renames `ventas.fecha`→`fecha_pago` (nullable), adds `ventas.fecha_inicio` (backfilled from `fecha_pago` → `SET NOT NULL`), makes `pagos.fecha_pago` nullable — lets a `Venta` create its linked `Pago`(s). Same RLS-bypass around the `ventas.fecha_inicio` backfill as `0004` (Critical Design Rule #17). This is the migration that crash-looped the real production deploy (backfill silently updated 0 rows under `FORCE` RLS when run as the non-superuser table owner) until the RLS-bypass was added — the fix was verified end-to-end against a copy of production data.

## Architecture

Three Docker containers (`docker-compose.yml`):

1. **`db`** — `postgres:15`, credentials `admin / password_seguro`, DB `elysium_agenda`. Has a healthcheck; backend waits for it.
2. **`backend`** — FastAPI, `./backend/`, entry `main:app`, uvicorn hot-reload. Runs `alembic upgrade head` on container start (before uvicorn), then seeds admin + test patient via `lifespan`.
3. **`frontend`** — CRA React, `./frontend/`, `npm start`. Volume-mounted for hot-reload.

### Backend layout (`./backend/`)

```
main.py              # App factory, CORS (dynamic via BASE_DOMAIN — see Multi-Tenancy → Phase 2), TenantMiddleware,
                     #   lifespan (seeds + per-tenant background jobs)
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
  planes.py          # plan_disponible() / descontar_sesion() / crear_pago() — a patient can have 2+ active
                     #   Pago at once (different tipo, or a renewal); plan_disponible matches by tipo_paquete
                     #   exactly and, among several that qualify, picks the one expiring soonest (FIFO by
                     #   fecha_vencimiento) so sessions don't go to waste on a plan about to lapse.
                     #   crear_pago() is shared by routes/pagos.py and routes/ventas.py (a Venta with
                     #   sesiones creates its Pago(s) through this same helper)
  constants.py        # METODOS_PAGO, MAX_PASSWORD_BYTES, RESERVED_SLUGS — deduplicated / infra reservations,
                     #   NOT tenant config (see Multi-Tenancy)
middleware/
  tenant.py          # TenantMiddleware (subdomain → X-Tenant-Slug [non-prod] → 404) + get_current_tenant dep
                     #   a RESERVED_SLUGS slug is never looked up; a resolved tenant with estado="suspendido"
                     #   404s the same as not-found (Phase 2.3)
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
                     #   create_cita skips the active-plan check when medico_id is set (referral citas) or
                     #   tipo is "Sesión de cortesía" (never backed by a Pago)
                     #   hora/tipo validity checked in the route body via core/servicios.py (not a Pydantic validator — see Multi-Tenancy)
                     #   patch_estado: no time-window auto-penalty (admin picks the outcome explicitly — see
                     #   Core Business Rule #2); descontar_sesion()/plan_disponible() come from core/planes.py
  pagos.py           # POST /pagos/ (via core/planes.py:crear_pago) + GET /pagos/?paciente_id= — require_admin
                     #   fecha_pago optional (nullable, migration 0005) — a plan can exist before it's paid
  portal.py          # Public (no JWT, but still tenant-resolved by TenantMiddleware): GET /portal/paciente/{cedula}
                     #   POST /portal/registro (nombre+cedula+telefono+email+habeas_data_aceptado REQUIRED true)
                     #   POST /portal/citas (new booking) · POST /portal/citas/recurrente
                     #   POST /portal/citas/{id}/cancelar (2h window enforced)
                     #   POST /portal/citas/{id}/reprogramar (2h window enforced)
  medicos.py         # require_feature("medicos"): GET/POST /medicos/ (list/create Usuario with es_medico=True)
  medico_portal.py   # require_feature("medico_portal") + require_medico: GET /medico/citas (own referrals only) · POST /medico/citas
                     #   (find-or-create Paciente by cédula + create Cita with medico_id/motivo_remision, no plan check)
  ventas.py          # require_feature("ventas") + require_admin: GET /ventas/ (filters: paciente_id, categoria, estado, fecha_desde, fecha_hasta — the
                     #   latter two now filter on fecha_pago; list ordered by fecha_inicio.desc(), never null unlike fecha_pago)
                     #   POST /ventas/ → validates paciente, abono ≤ valor_total, computes saldo+estado, creates the linked Pago(s) from
                     #   `planes` via core/planes.py:crear_pago() (see "Data model — ventas" above), triggers send_confirmacion_pago in background
                     #   DELETE /ventas/{id} — does NOT cascade-delete the linked Pago(s); they're independent rows once created
  gastos.py          # require_feature("gastos") + require_admin: GET /gastos/ (date filters) · POST /gastos/ · DELETE /gastos/{id}
services/
  email.py           # send_confirmacion · send_recordatorio · send_confirmacion_pago via Resend API (HTTP, no SMTP)
                     #   reads RESEND_API_KEY + RESEND_FROM + PORTAL_URL + BASE_DOMAIN + CLINIC_MAPS_URL at import time
                     #   send_confirmacion_pago: includes paquete, valor, abono, saldo, estado badge, 45-day expiry block (when total_sesiones set)
                     #   logs WARNING (not sent) when RESEND_API_KEY missing
                     #   Phase 2.5: the 3 send_* functions take the full Tenant object — every literal
                     #   "Elysium"/"Elysium Fisio-Pilates" interpolates tenant.nombre_comercial; _portal_url(slug)
                     #   builds https://<slug>.<BASE_DOMAIN>/portal once BASE_DOMAIN is set (PORTAL_URL still wins
                     #   as an explicit override, e.g. local dev); _brand_color(tenant) reads
                     #   tenant.branding.color_primario (default "#27272a", matches what was already hardcoded on
                     #   CTA buttons/card gradients — the header's separate fixed color, "#0f172a", was left
                     #   untouched since it never shared the same literal, to guarantee zero visual change for
                     #   Elysium). FROM_EMAIL/RESEND_API_KEY stay global on purpose (per-tenant sender domains are
                     #   a billing/onboarding concern, out of scope)
scripts/
  bootstrap_app_role.sql  # One-time per-environment: creates the app_user Postgres role RLS needs (see Multi-Tenancy)
  crear_tenant.py    # Phase 2.6 — CLI to onboard a tenant: creates Tenant + 2 Servicio (Pilates/Fisioterapia,
                     #   same base capacity/duration as Elysium) + admin Usuario in one transaction. Validates
                     #   slug format, RESERVED_SLUGS, and duplicates before writing anything (--dry-run to just
                     #   check). Connects with DATABASE_URL directly (own engine/session, not database.py) —
                     #   never APP_DATABASE_URL, since a brand-new tenant has no RLS context yet and the
                     #   non-superuser app_user connection would have its INSERTs silently rejected by RLS's
                     #   WITH CHECK. Admin password: secrets.token_urlsafe(12), printed once, never logged.
```

> **bcrypt note:** `passlib[bcrypt]` is installed but NOT used — passlib 1.7.4 is incompatible with bcrypt 4.x (raises ValueError on startup). All password hashing uses `import bcrypt` directly.

### Frontend layout (`./frontend/src/`)

```
index.js                    # Entry, imports index.css (Tailwind)
App.js                      # TenantProvider > AuthProvider > Routes + HabeasDataModal
                            #   HabeasDataModal: z-[100] backdrop-blur overlay for habeas_data_aceptado=false
                            #   PolicyContent: reusable legal text component (Ley 1581/2012) — NOT tenant-dynamic (see Multi-Tenancy)
index.css                   # @tailwind base/components/utilities
config/
  runtime.js                 # NEW (Fase 2.2) — derives apiUrl/tenantSlug from window.location.hostname at
                            #   runtime (not build time): on localhost, falls back to REACT_APP_API_URL /
                            #   REACT_APP_DEV_TENANT_SLUG; otherwise apiUrl = https://<slug>.api.<REACT_APP_BASE_DOMAIN>,
                            #   slug = the leftmost label of the browser's own hostname. One frontend build
                            #   now serves every tenant — nothing tenant-specific is baked into the bundle.
api/
  client.js                 # Single axios instance — imports apiUrl/tenantSlug from config/runtime.js (not
                            #   process.env directly); Authorization + X-Tenant-Slug (dev only) injected via
                            #   request interceptor. Every other api/*.js file imports this instead of raw axios
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
  CitaEstadoModal.js         # Extracted from AgendaPage.js so DashboardHome.js's "Citas de hoy" table can
                            #   reuse the exact same modal — 5 explicit actions (Confirmar/Completada/No
                            #   asistió/Reagendar/Cancelar sin descontar), no auto-penalty by timing
pages/
  LoginPage.js              # Login form — redirects to /dashboard (admin), /medico (médico), or /portal (patient)
  DashboardHome.js          # Real stats: citas hoy/semana/mes by tipo, pacientes activos/inactivos, próxima cita,
                            #   "Citas de hoy" table shows médico remitente ("Directo" if none) — now INTERACTIVE:
                            #   clicking a row opens CitaEstadoModal, same as AgendaPage; reloadTick re-fetches
                            #   PieChart (recharts donut) of current-month ventas by categoria
  PacientesPage.js          # Searchable table + create/edit modal + delete confirm. Modal is patient-data-only
                            #   now — the old "Agregar nuevo plan" toggle was removed; plans are only created
                            #   from VentasPage.js. The table itself still shows Plan/Sesiones/Vence per patient
                            #   (read-only, one row per active plan — a patient can have 2+ at once)
  NuevaCitaPage.js          # Admin appointment booking form + optional "Médico en convenio" select + motivo_remision
                            #   tipo options + time slots from useTenant() (tiposCita/buildSlots), not hardcoded arrays
  AgendaPage.js             # Weekly view Lun–Sáb, slots from buildSlots(horario), capacity badges from useTenant().servicios,
                            #   estado modal is now the shared CitaEstadoModal component (shows médico remitente)
  PortalPage.js             # Patient self-service: cedula entry OR auto-load (if logged in),
                            #   ONE plan card PER active plan (paciente.planes_activos is a list — a patient can
                            #   have Pilates + Fisioterapia simultaneously, or a renewal bought before expiry),
                            #   upcoming citas with cancel/reschedule buttons,
                            #   booking form (tipo/slots from useTenant()), self-register form (email + habeas checkbox + policy modal)
                            #   Habeas Data checkbox text + policy modal content are NOT tenant-dynamic (legal text, out of scope)
  MedicosPage.js            # Admin: table of médicos + "Nuevo médico" modal (nombre/email/password)
  MedicoPortalPage.js       # Médico self-service: "Mis pacientes/citas" tab + "Agendar nuevo paciente" tab
                            #   tipo options + slots from useTenant() (no cortesía — servicios never include it)
  VentasPage.js             # Income module: NuevaVentaModal (patient search, categoria→paquete autofill, live saldo,
                            #   Pagó/Abonó/Pendiente selector that toggles whether fecha_pago/abono are required,
                            #   fecha_inicio field for the linked Pago(s), Combos auto-split into 2 planes entries)
                            #   PAID/PENDING badges (pendiente now orange, not red — red is reserved for errors),
                            #   summary cards (total, ingresos mes, pendientes)
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
"cancelada"                     # patient portal: free if > 2h before appointment. Admin (Agenda/Dashboard): always free, no time check.
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
| fecha_pago | Date (nullable) | when the payment was registered — admin-provided, may lag `fecha_inicio` (e.g. paid in installments); **null while a linked `Venta` is still `pendiente`** (added migration `0005`) |
| fecha_inicio | Date | when the plan actually starts — admin-provided, independent of `fecha_pago` |
| fecha_vencimiento | Date | computed server-side: `fecha_inicio + tenant.get_config("vigencia_plan_dias")` (Elysium: 45 days) — **not** `fecha_pago` |

A patient can have **more than one active `Pago` at once** (e.g. Pilates + Fisioterapia simultaneously, or a renewal bought before the old one expires) — see `core/planes.py` under Multi-Tenancy → "Business-rule constants" below for how booking/deduction picks which one applies.

### Data model — `ventas` table

| Column | Type | Notes |
|--------|------|-------|
| id | String (UUID) | PK |
| tenant_id | UUID | FK → tenants.id |
| paciente_id | String | composite FK (tenant_id, paciente_id) → pacientes(tenant_id, "Paciente") |
| nombre_paquete | String | e.g. "Plan Pro 8 Ses – Individual" |
| categoria | String | Pilates \| Fisioterapia \| Combos \| Prendas de Vestir — billing catalog, not tenant config (see Multi-Tenancy) |
| total_sesiones | Integer (nullable) | null for Prendas de Vestir; for Combos this is the combined total (see `frontend/src/constants/packages.js`'s `split` field) |
| valor_total | Float | |
| abono | Float | amount paid up-front — `0` when `estado_pago` was "Pendiente" in the admin form |
| saldo | Float | computed: valor_total − abono |
| fecha_inicio | Date | when the plan starts — always required, drives the linked `Pago`'s `fecha_inicio` (migration `0005`, renamed/added alongside the `fecha`→`fecha_pago` change below) |
| fecha_pago | Date (nullable) | payment date — **null when `estado` is `pendiente` with nothing paid yet** (renamed from `fecha`, migration `0005`) |
| metodo_pago | String | Efectivo \| Transferencia \| Tarjeta \| Otro |
| estado | String | pagada (saldo==0) \| pendiente (saldo>0) |

**`POST /ventas/` creates the linked `Pago`(s) automatically** — the frontend sends a `planes: [{tipo_paquete, sesiones}, ...]` list (1 entry for a plain Pilates/Fisioterapia sale, 2 for a Combo split via each package's `split` field in `packages.js`, 0 for Prendas de Vestir); the backend validates each `tipo_paquete` against the tenant's real `servicios` and calls `core/planes.py:crear_pago()` for each one, using the venta's own `fecha_inicio`/`fecha_pago`. This replaced the old flow where an admin had to separately open Pacientes and manually "Agregar nuevo plan" with the same package info — that toggle no longer exists in `PacientesPage.js`.

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
- `database.py` — `APP_DATABASE_URL` is what `engine`/`SessionLocal` connect with at runtime; falls back to `DATABASE_URL` (admin) with a `logger.warning` if unset in dev, but **when `RAILWAY_ENVIRONMENT == "production"` a missing `APP_DATABASE_URL` is a hard `RuntimeError` at startup** — silently running as the superuser in prod would bypass RLS entirely (a cross-tenant leak), so the app must refuse to boot instead. Alembic (`alembic/env.py`) always uses `DATABASE_URL` directly, never `APP_DATABASE_URL` — migrations need full DDL rights and must work before `app_user`/RLS exist at all.

**RLS-vs-migration gotcha (found crash-looping the real production deploy, documented in `0004`/`0005` docstrings):** a migration that runs a **data backfill** (`UPDATE`) on an RLS-`FORCE`d table only works if the connection **bypasses RLS** — i.e. runs as a superuser (or a `BYPASSRLS` role). Alembic is *designed* to connect via `DATABASE_URL` = the superuser/table-owner, exactly so backfills see every row. If migrations instead run as a **non-superuser that merely owns the tables** (e.g. someone did `ALTER TABLE ... OWNER TO app_user` and pointed `DATABASE_URL` at `app_user`), `FORCE ROW LEVEL SECURITY` subjects even the owner to the policy, and since a migration never sets `app.tenant_id`, the `tenant_isolation` policy filters **every row out** → the `UPDATE` touches 0 rows → a subsequent `SET NOT NULL` on the just-backfilled column fails with `column ... contains null values`. This is silent and easy to misdiagnose as "missing backfill". Two independent guards now exist: (1) migrations should run as the superuser (the intended `DATABASE_URL` role); (2) defensively, `0004`/`0005` wrap their backfill in `DISABLE ROW LEVEL SECURITY` → `UPDATE` → `ENABLE`+`FORCE ROW LEVEL SECURITY` so the backfill is correct regardless of the running role (a superuser bypasses RLS anyway, making the toggle a harmless no-op there). See Critical Design Rule #17.

**`SET LOCAL` gotcha:** it only lasts for the current transaction, and most routes `db.commit()` mid-request and keep using the same session afterward (e.g. `db.refresh()` right after commit — `create_cita` does exactly this). Setting it once in `get_db()` would silently lose tenant context after the first commit. The actual mechanism: `database.py` registers `@event.listens_for(engine, "begin")`, which runs `SET LOCAL app.tenant_id = ...` on **every** new transaction, reading from a `contextvars.ContextVar` (`current_tenant_id`) — not `request.state`, since the event listener has no access to the `Request`. `TenantMiddleware` sets this ContextVar at the start of a request and resets it in a `finally`. Background jobs (`_job_citas_vencidas`, `_job_recordatorios` in `main.py`) don't go through the middleware, so they loop over every active tenant themselves, setting the ContextVar per iteration (with per-tenant error isolation, so one tenant failing doesn't skip the rest).

FK checks always bypass RLS (documented Postgres behavior) — the composite FKs above are what actually stop a `citas.tenant_id`-correct-but-`paciente_id`-wrong-tenant row; RLS and the composite FKs are complementary, not redundant.

### Tenant resolution (`TenantMiddleware`)

`backend/middleware/tenant.py`, registered before `CORSMiddleware` in `main.py`. Order, per request:
1. Subdomain of the `Host` header (or an exact match against a tenant's `custom_domain`).
2. `X-Tenant-Slug` header — **only** when `RAILWAY_ENVIRONMENT != "production"` (local/dev convenience — `localhost` has no real subdomain).
3. Otherwise: `404 {"detail": "No encontrado"}` — never reveals whether a slug exists.

`/health` is exempt (deployment healthchecks have no tenant context). The resolved tenant lands on `request.state.tenant`/`request.state.tenant_id`; `middleware/tenant.py:get_current_tenant` is a FastAPI dependency (`tenant: Tenant = Depends(get_current_tenant)`) for routes that need `tenant.get_config(...)`.

**Local dev:** the frontend sends `X-Tenant-Slug: elysium` on every request (`REACT_APP_DEV_TENANT_SLUG` env var, resolved by `frontend/src/config/runtime.js` and injected by `frontend/src/api/client.js`'s axios interceptor — see "Phase 2" below).

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
A second tenant no longer needs any of the manual SQL above — `backend/scripts/crear_tenant.py` does all three inserts (tenant + 2 servicios + admin Usuario) in one transaction (see "Phase 2 → 2.6" below). The manual SQL is kept here only as a reference for what the script actually does under the hood.

### Phase 2 (subdomain routing) — complete

Target domain scheme, once wildcard DNS is actually connected (not part of this phase — that's a Railway/DNS configuration step, not code): `<slug>.<BASE_DOMAIN>` for the frontend, `<slug>.api.<BASE_DOMAIN>` for the backend, `admin.<BASE_DOMAIN>` reserved for a future superadmin panel.

**Correction to an earlier premise (superseded — see below):** a `DEFAULT_TENANT_SLUG` "bridge" value was assumed to exist from Phase 1 and need removing — at the time, it never existed anywhere in the code (confirmed via a full-repo `grep`). The real underlying gap was that the backend's `Host` header never carries the tenant subdomain when frontend/backend are separate Railway services with no wildcard DNS wired up — a deploy/infra gap, not a hardcoded value to delete. **This held only until the production cutover was scheduled to happen *before* wildcard DNS for the client's real domain — at that point `DEFAULT_TENANT_SLUG` was deliberately (re)introduced as a temporary bridge, see "DEFAULT_TENANT_SLUG — temporary cutover bridge" below.** Acceptance criterion #8 from the original Phase 2 brief (verified via a clean `grep -rn "DEFAULT_TENANT_SLUG" .`) no longer holds as originally stated, and won't again until wildcard DNS is connected and this bridge is retired (`docs/CUTOVER.md` has the explicit removal step).

- **2.2 — frontend runtime URL/tenant resolution:** `frontend/src/config/runtime.js` derives `apiUrl`/`tenantSlug` from `window.location.hostname` at runtime instead of a build-time env var. On `localhost`/`127.0.0.1` it falls back to `REACT_APP_API_URL`/`REACT_APP_DEV_TENANT_SLUG` (same behavior as before, just renamed); anywhere else, `tenantSlug` is the hostname's leftmost label and `apiUrl` is `https://<tenantSlug>.api.<REACT_APP_BASE_DOMAIN>`. `frontend/src/api/client.js` now imports from here instead of reading `process.env` directly — it's the only file that ever did. One frontend build now works for every tenant; nothing tenant-specific is baked into the bundle at build time.

- **2.3 — backend host resolution:** `RESERVED_SLUGS` (`core/constants.py`: `admin`/`api`/`www`/`app`/`mail`/`static`) is never looked up against `tenants.slug` — whether the candidate came from the `Host` subdomain or the dev `X-Tenant-Slug` header — so those subdomains can never resolve to a tenant even if a stray row existed with that slug. A tenant resolved with `estado == "suspendido"` now 404s the same as not-found (`middleware/tenant.py`) — previously a suspended tenant still resolved and served requests normally, a real gap. `_subdomain_from_host` needed no logic change — it already took the leftmost label regardless of how many labels follow, so `<slug>.<BASE>` and `<slug>.api.<BASE>` both resolved correctly before this sub-phase too.

- **2.4 — dynamic CORS:** `main.py` replaced the fixed `ALLOWED_ORIGINS` env var/list with `allow_origin_regex=rf"^https://[a-z0-9-]+\.{re.escape(BASE_DOMAIN)}$"` (only built when `BASE_DOMAIN` is set), alongside `allow_origins=["http://localhost:3000"]` kept explicit for local dev. Starlette evaluates `allow_origins` and `allow_origin_regex` together, not exclusively. Never `allow_origins=["*"]` (incompatible with `allow_credentials=True` anyway).

- **2.5 — per-tenant email branding:** `services/email.py`'s `send_confirmacion`/`send_recordatorio`/`send_confirmacion_pago` now take the full `Tenant` object (not just name/slug — most call sites already had it in scope, and branding color needs the object too). Every literal "Elysium"/"Elysium Fisio-Pilates" interpolates `tenant.nombre_comercial`. New `_portal_url(tenant_slug)`: `PORTAL_URL` env var wins if set (explicit override, keeps local dev unchanged); otherwise builds `https://<slug>.<BASE_DOMAIN>/portal` once `BASE_DOMAIN` is set; falls back to `localhost:3000` before either is configured. New `_brand_color(tenant)` reads `tenant.branding.color_primario`, default `"#27272a"` — applied to CTA buttons and the card-gradient's first stop, the two spots that already hardcoded that exact value, so Elysium (unconfigured `branding`) renders pixel-identical to before. The base template's header background (`#0f172a`) was deliberately **not** themed — it's a different hardcoded literal than the buttons/cards, and reusing one shared default for both would have changed Elysium's actual header color; left alone until a real second color token is worth adding. `FROM_EMAIL`/`RESEND_API_KEY` stay global on purpose — per-tenant sender domains are a billing/onboarding concern, out of scope here.

- **2.6 — tenant onboarding script:** `backend/scripts/crear_tenant.py` — `--slug`/`--nombre`/`--plan`/`--admin-email`/`--admin-nombre`/`--dry-run`. Validates slug format (`[a-z0-9-]{3,30}`), `RESERVED_SLUGS`, and duplicates before writing anything. Creates `Tenant` + 2 `Servicio` (Pilates 6/60min, Fisioterapia 2/60min — same base values as Elysium) + an admin `Usuario` in one transaction, with a `secrets.token_urlsafe(12)` temporary password printed once (never logged, never stored in plaintext). Connects with `DATABASE_URL` directly via its own engine/session — deliberately **not** `database.py` (whose engine is wired to `APP_DATABASE_URL` and the tenant-context "begin" listener, neither applicable here) and **not** `APP_DATABASE_URL` itself, since a brand-new tenant has no RLS context yet and the non-superuser `app_user` connection would have every INSERT silently rejected by the RLS policy's `WITH CHECK`.

Full plan with verification steps for each sub-phase: `C:\Users\User_house\.claude\plans\sunny-puzzling-lovelace.md`.

### DEFAULT_TENANT_SLUG — temporary cutover bridge (added after Phase 2, not part of it)

The production cutover (`docs/CUTOVER.md`) goes live **before** wildcard DNS
for the client's real domain is connected — so the backend's real Railway
host (e.g. `elysium-backend-production.up.railway.app`) never carries a
tenant subdomain, and every request would 404 without some fallback. Added
a 4th step to `TenantMiddleware.dispatch` (`middleware/tenant.py`), after
the existing 3:

1. `Host` subdomain / `custom_domain` match (unchanged, 2.3).
2. `X-Tenant-Slug` header, non-production only (unchanged, 2.3).
3. **`DEFAULT_TENANT_SLUG` env var** — only if set and steps 1-2 resolved
   nothing. Deliberately **not** gated by `RAILWAY_ENVIRONMENT` — production
   is exactly where it's needed, precisely because step 2 is disabled
   there. Logs a `WARNING` every time it's used, including the `Host` that
   failed to resolve, so it's visible in Railway logs when this bridge is
   actually being exercised. A slug that doesn't exist or resolves to a
   `suspendido` tenant just falls through to the same generic 404 as any
   other miss — no exception. `RESERVED_SLUGS` does **not** apply to this
   value — it's operator-set deployment config, not attacker-controlled
   input like the `Host` header or `X-Tenant-Slug`.
4. Otherwise: 404 (unchanged).

**This is temporary and must be removed once wildcard DNS is actually
connected** — leaving it configured after that point would mean any request
that fails to resolve a real subdomain (e.g. a typo'd tenant slug) silently
falls back to whichever tenant `DEFAULT_TENANT_SLUG` points at instead of a
clean 404, which stops being a safety bridge and starts being a data
mixup risk. `docs/CUTOVER.md` has an explicit "retirar DEFAULT_TENANT_SLUG"
step for the DNS cutover phase. Tests: `tests/test_tenant_isolation.py`
(fallback resolves when `Host` doesn't; 404 when unset; a real subdomain
match still takes precedence over it).

### Environment variables added

| Variable | Where | Purpose |
|---|---|---|
| `APP_DATABASE_URL` | backend | Runtime connection as `app_user` (non-superuser) — required for RLS to have any effect. Falls back to `DATABASE_URL` (admin, bypasses RLS) with a warning if unset. |
| `REACT_APP_DEV_TENANT_SLUG` | frontend (dev only) | Renamed from `REACT_APP_TENANT_SLUG` in Phase 2.2. Lets `localhost` resolve a tenant without real subdomains — sent as `X-Tenant-Slug`. Read by `config/runtime.js`, not `client.js` directly anymore. |
| `REACT_APP_BASE_DOMAIN` | frontend | Phase 2.2. The real base domain (e.g. `elysium.app`) used to build `https://<slug>.api.<REACT_APP_BASE_DOMAIN>` outside `localhost`. Currently a harmless placeholder (`localhost`) in `docker-compose.yml` since local dev never takes that code path. |
| `BASE_DOMAIN` | backend | Phase 2.4/2.5. Drives the CORS `allow_origin_regex` (`main.py`) and the email `_portal_url()` fallback (`services/email.py`). Unset in local dev (`docker-compose.yml` doesn't set it for the backend) — CORS falls back to `localhost:3000`-only and emails fall back to the `PORTAL_URL`/localhost default, both unchanged from before Phase 2. |
| `DEFAULT_TENANT_SLUG` | backend | **Temporary, cutover-only** (see above) — production fallback tenant slug used only when the `Host`/`X-Tenant-Slug` resolution fails. Not set in local dev. Must be removed once wildcard DNS is connected — `docs/CUTOVER.md` has the removal step. |

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
- [x] **Migración de datos de producción ensayada:** dump/restore de la base real de Railway (81 pacientes, 3 usuarios, 17 citas, 17 pagos, 12 ventas) contra un entorno Docker completamente aislado y desechable, corriendo las migraciones Alembic 0001→0005 encima. Encontró y arregló un bug real de idempotencia en `0004` (ver su docstring). Cero escrituras contra la base real; todo el entorno de ensayo fue destruido al terminar.
- [x] **Planes múltiples por paciente + vínculo Venta→Pago:** un paciente puede tener 2+ `Pago` activos a la vez (`core/planes.py`, selección FIFO por `fecha_vencimiento`); `POST /ventas/` crea su(s) `Pago` vinculado(s) automáticamente vía `planes: [...]`, reemplazando el flujo manual "Agregar nuevo plan" en Pacientes (removido de `PacientesPage.js`).
- [x] **Ventana de cancelación solo aplica al portal del paciente:** `PATCH /citas/{id}/estado` (admin, vía `CitaEstadoModal.js`) ya no auto-convierte una cancelación en penalización por horario — el admin elige explícitamente entre 5 acciones (ver Regla de negocio #2).
- [x] **Dashboard interactivo:** la tabla "Citas de hoy" de `DashboardHome.js` reutiliza `CitaEstadoModal.js` (extraído de `AgendaPage.js`) — clic en una fila abre el mismo modal de gestión de estado.
- [x] **Multi-tenancy — Fase 2 completa (`feature/multi-tenant`):** 2.2 frontend deriva `apiUrl`/`tenantSlug` de `window.location.hostname` en runtime (`config/runtime.js`) — un solo build sirve a cualquier tenant; 2.3 `RESERVED_SLUGS` + chequeo de tenant `suspendido` en `TenantMiddleware`; 2.4 CORS dinámico vía `allow_origin_regex` sobre `BASE_DOMAIN`; 2.5 correos (`services/email.py`) reciben el `Tenant` completo — nombre, URL de portal y color de marca ya no están hardcodeados a Elysium; 2.6 `backend/scripts/crear_tenant.py` da de alta un tenant nuevo (tenant + 2 servicios + admin) en una transacción, sin SQL a mano. Ver "Multi-Tenancy → Phase 2" arriba para el detalle completo de cada sub-fase.
- [x] **`feature/multi-tenant` mergeado a `main`:** todo el stack multi-tenant (Fase 1+2, prep de cutover, `DEFAULT_TENANT_SLUG`) está en `main` — Railway despliega desde `main`. Un solo commit de `main` divergía (`ebad4e9`, planes múltiples + `fecha_inicio`), funcionalmente equivalente a la Fase A ya incluida; los 7 conflictos se resolvieron a favor de `feature/multi-tenant`.
- [x] **Revisión de seguridad (pre-lanzamiento):** matriz de ataque RLS cross-tenant (SELECT/UPDATE/DELETE/INSERT/tenant-hop, todos bloqueados); `X-Tenant-Slug` ignorado en `production`; JWT de otro tenant → 401; paciente → rutas admin → 403; `/docs` off en prod; rate limiting presente. **Bloqueador encontrado y resuelto:** `JWT_SECRET_KEY` de producción estaba en `DEPLOY_NOTES.md` en un repo público — demostrado explotable (forjar token admin sin login). Rotada en Railway + archivo redactado (la clave vieja queda en el historial de git pero, rotada, es inservible).
- [x] **Fix de migración RLS (0004/0005):** el backfill de `fecha_inicio` corría 0 filas bajo `FORCE` RLS cuando la migración corre como el dueño no-superuser (`app_user`), crasheando el deploy real. Resuelto envolviendo el backfill en `DISABLE`/`ENABLE`+`FORCE` RLS. Ver "Row-Level Security → RLS-vs-migration gotcha" y Critical Design Rule #17.

**Cutover a producción — EN PROGRESO (no verificado en vivo todavía):**
- [x] Backup de la base real, `alembic stamp 0001`, rol `app_user` bootstrapeado, `APP_DATABASE_URL`/`DEFAULT_TENANT_SLUG`/`JWT_SECRET_KEY` seteadas en Railway, Start Command del backend con `alembic upgrade head`, fix de migración 0004/0005 pusheado a `main`.
- [ ] **Verificar el redeploy en vivo:** que alembic llegue a `0005`, existan `tenants`/`servicios`, `/health` OK y los conteos de datos coincidan. Ver `docs/CUTOVER.md`.
- [ ] **Nota de config (recomendado):** en producción las tablas quedaron con dueño `app_user` y las migraciones corren como `app_user`; el diseño previsto es que Alembic corra como el superuser `postgres` (`DATABASE_URL=${{Postgres.DATABASE_URL}}`). El fix 0004/0005 lo hace funcionar igual, pero conviene alinear la config. Ver Critical Design Rule #17.
- [ ] **Retirar `DEFAULT_TENANT_SLUG`** cuando se conecte el wildcard DNS real — ver `docs/CUTOVER.md` sección 11.

**Next to build:**
- [ ] **Fases 3–4 del multi-tenant:** UI de administración de tenants, wildcard DNS/subdominios reales conectados (el código ya soporta el esquema, falta la infraestructura), onboarding self-service, facturación
- [ ] `dashboard_metrics` feature flag no está aplicada todavía en `DashboardHome.js` (el PieChart de ventas es visible para cualquier plan)
- [ ] `PortalPage.js`'s `canModify(cita)` sigue con 2h hardcodeado en vez de leer `useTenant()` (solo afecta cuándo se deshabilitan los botones en la UI — el backend ya usa `tenant.get_config`, así que no es un hueco de seguridad)
- [ ] **Notificaciones WhatsApp** — n8n webhook → WhatsApp API (Meta) recordatorio 24h antes de la cita
- [ ] Configurar `PORTAL_URL` en Railway apuntando al frontend (el correo de pago ya lo usa, pero el default es localhost)

## Critical Design Rules

1. **Database identifier:** Always use the column named `Paciente` (never `ID_Paciente` or any variant) as the primary key/identifier in patient-related tables. As of Phase 1 multi-tenant, `pacientes`' PK is **composite** `(tenant_id, "Paciente")` — the column name rule still holds, but any `db.get(Paciente, x)` needs the tuple `(tenant_id, x)`, not a bare cédula.

2. **Auth:** JWT via `python-jose`. Use `bcrypt` directly (not `passlib.CryptContext`). Token stored in `sessionStorage` under key `elysium_token`. JWT payload always includes `tenant_id` (str), `es_admin` (bool), `es_medico` (bool), `medico_id` (str | null), and `paciente_id` (str | null). Admin-only routes use `require_admin`; médico-only routes use `require_medico` (both in `auth/jwt.py`) — never bare `get_current_user` for role-gated routes. `get_current_user` also 401s if the JWT's `tenant_id` doesn't match the host-resolved tenant — see "Multi-Tenancy" above.

3. **Plan expiration:** Always computed server-side as `fecha_inicio + timedelta(days=tenant.get_config("vigencia_plan_dias"))` (Elysium: 45) — **based on `fecha_inicio` (the plan's start date), not `fecha_pago` (the payment date)**, since a client may start a plan before finishing payment on it. Never accept `fecha_vencimiento` from the client, never hardcode the day count — read it from tenant config. Both `routes/pagos.py` and `routes/ventas.py` create `Pago` rows through the single shared `core/planes.py:crear_pago()` helper, so this rule only needs to be correct in one place.

4. **Session deduction:** `sesiones_restantes` is decremented by the backend only — never by the frontend. Triggered on estado = `"completada"` or `"No asistió con penalización"`. Booking does NOT deduct (only checks availability).

5. **Capacity/schedule/type constants (never hardcode inline):** As of Phase 1 multi-tenant, none of `CAPACIDAD`, `TURNOS`, `TIPOS_VALIDOS`, `HORAS_CANCELACION`, `VIGENCIA_DIAS` exist as hardcoded dicts anymore — they come from `servicios` (capacity, valid types) and `tenant.config` (schedule window, cancellation window, plan validity) via `backend/core/servicios.py`. Do not reintroduce a hardcoded copy in a route file — add a helper to `core/servicios.py` instead. `METODOS_PAGO` and `MAX_PASSWORD_BYTES` are the one exception: pure code dedup in `core/constants.py`, not tenant config, since they're not business rules that vary per tenant.

6. **Code style:** Modules small and focused: routes only route, models only define schema, business logic in routes. No excessive comments.

7. **Color palette:** zinc-800/900/950 (primary actions, sidebar background, brand dark), zinc-700 (active nav), slate-50 (page background), white (cards). Semantic colors kept: red (errors), green (success), amber (warnings).

8. **Timezone gotcha:** Never use `new Date().toISOString().split('T')[0]` — returns UTC date. Always use local date methods: `getFullYear() / getMonth() / getDate()`. Applied in `DashboardHome.js`, `AgendaPage.js`, and `PortalPage.js`.

9. **Schema migrations:** Every schema change is an Alembic revision (`backend/alembic/versions/`) — see "Database Migrations (Alembic)" above. `create_all`/`_run_migrations()` no longer exist; do not reintroduce ad hoc `ALTER TABLE` calls at startup.

10. **Portal cancellation window is patient-only:** Cancel and reschedule from the patient portal (`routes/portal.py`) are blocked server-side when `datetime.now() >= cita_datetime - tenant.get_config("ventana_cancelacion_horas")` (Elysium: 2h). The frontend's `canModify(cita)` in `PortalPage.js` still hardcodes 2h to disable buttons early (a pre-Phase-1 shortcut, not yet wired to `useTenant()`) — the backend is the source of truth regardless, so this is a display-only staleness, not a security gap. **The admin is exempt from this window entirely** — see Core Business Rule #2 and `CitaEstadoModal.js`'s 5 explicit actions; don't reintroduce a timing-based auto-penalty into `PATCH /citas/{id}/estado`, that was deliberately removed.

11. **Habeas Data flow:** `habeas_data_aceptado` lives on both `Usuario` (for login-based users) and `Paciente` (for anonymous registrations). New patients: checkbox required in portal registration form (backend validates `habeas_data_aceptado=true`). Existing users: JWT carries the field; `HabeasDataModal` in `App.js` intercepts the UI when `user.habeas_data_aceptado === false` and calls `POST /auth/aceptar-habeas`. `acceptHabeas()` in `AuthContext` updates React state in-memory without requiring a re-login. Timestamp stored as UTC via `datetime.utcnow()`.

12. **Email background task + ORM detachment:** When passing ORM objects to FastAPI `background_tasks.add_task()`, always call `db.refresh(obj)` on any object loaded **before** `db.commit()`. After commit, SQLAlchemy expires those objects' attributes; by the time the background task runs the session is already closed, causing a silent `DetachedInstanceError`. Objects loaded **after** `db.commit()` are fresh and safe to pass directly.

13. **Médico referral citas skip the active-plan check:** A cita is a "referral" when `medico_id` is set (created via `POST /medico/citas` or `POST /citas/` with `medico_id`) — same exemption as `tipo == "Sesión de cortesía"`, which is never backed by a `Pago` either (`plan_disponible`'s callers must not invoke it for that tipo — see its docstring). `core/planes.py:descontar_sesion(db, paciente_id, tipo, required=True)` takes a `required` flag: callers pass `required=False` for a referral/cortesía cita so marking it `completada`/no-show doesn't 422 when there's no plan — it just skips the deduction (same tolerant behavior `procesar_citas_vencidas` already had). When creating a `Paciente` and a `Cita` in the same request (see `medico_portal.py`), call `db.flush()` right after `db.add(paciente)` — there is no ORM `relationship()` between the two, so SQLAlchemy won't auto-order the inserts and the `Cita` insert will fail on the FK constraint if the `Paciente` row isn't flushed first.

14. **Every new row needs `tenant_id`:** Any `Paciente(...)`, `Usuario(...)`, `Cita(...)`, `Pago(...)`, `Venta(...)`, or `Gasto(...)` constructor must set `tenant_id` explicitly (`current_tenant_id.get()` inside a route, or the resolved `Tenant.id` in a background job/seed) — it's `NOT NULL` with no default. Forgetting it isn't caught until the `INSERT` fails (either a `NOT NULL` violation, or — worse, silently — an RLS `WITH CHECK` rejection if `tenant_id` were somehow `NULL` and a policy comparison happened to let it through, which it won't, but don't rely on RLS to catch a missing tenant_id at the ORM layer).

15. **RLS `SET LOCAL` must be re-applied every transaction, not once per request:** See "Multi-Tenancy → Row-Level Security" above for the full mechanism (`current_tenant_id` ContextVar + `@event.listens_for(engine, "begin")`). The short version: never assume a single `SET LOCAL app.tenant_id` at the top of `get_db()` is enough — any route that `db.commit()`s and keeps using the session (common in this codebase) opens a fresh transaction that needs its own `SET LOCAL`, which is exactly what the "begin" listener automates. Don't hand-roll a different tenant-context mechanism per route.

16. **Pydantic `@field_validator`s can't see the tenant:** They run during request parsing, before `get_db()`/`TenantMiddleware`'s dependencies resolve. Any validation that needs `tenant.get_config(...)` or a `servicios` lookup (schedule window, valid `tipo`, capacity) must happen in the route body, not a Pydantic validator — see `core/servicios.py` and how `routes/citas.py`/`portal.py`/`medico_portal.py`/`pagos.py` call it post-`Depends(get_current_tenant)`. Only tenant-independent structural checks (e.g. `hora.second == 0`, non-empty strings, email regex) belong in a validator now.

17. **A migration backfill on an RLS-`FORCE`d table must bypass RLS:** Migrations run as the `DATABASE_URL` role, which is *meant* to be the superuser/table-owner that bypasses RLS. But do not *rely* on that alone for `UPDATE` backfills on tenant-scoped tables — if migrations ever run as a non-superuser that merely owns the tables, `FORCE ROW LEVEL SECURITY` filters every row out (no `app.tenant_id` in a migration) and the backfill silently updates 0 rows, breaking a following `SET NOT NULL`. Wrap any such backfill in `ALTER TABLE <t> DISABLE ROW LEVEL SECURITY` → `UPDATE ...` → `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` (the exact pattern in `0004`/`0005`). This is correct for both a superuser (harmless no-op) and a non-superuser owner. See "Multi-Tenancy → Row-Level Security → RLS-vs-migration gotcha". This actually crash-looped the production cutover deploy before being fixed.
