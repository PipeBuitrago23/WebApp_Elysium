# Elysium Fisio-Pilates — Sistema de Agendamiento

Aplicación web para la gestión de citas, planes y pacientes de una clínica de fisioterapia y pilates. Incluye panel de administración completo y portal de autogestión para pacientes.

> **En conversión a multi-tenant** (rama `feature/multi-tenant`, sobre `main`) — Fase 1 de 4 completa: capa de datos, Row-Level Security y sistema de configuración por tenant. **Fase 2 (routing por subdominio) completa** — frontend resuelve la URL del backend y el tenant en runtime, backend rechaza slugs reservados/tenants suspendidos, CORS dinámico por subdominio, correos con branding real por tenant, y script `crear_tenant.py` para dar de alta un tenant sin SQL a mano. Elysium sigue siendo el único tenant en la práctica — falta conectar wildcard DNS real (Fase 3+) para que el esquema de subdominios funcione en producción. Ver la sección "Multi-tenancy" más abajo.

---

## Funcionalidades

### Panel de Administración
- Dashboard con métricas en tiempo real (citas hoy/semana/mes, pacientes activos/inactivos) + PieChart de ventas del mes por categoría
- Agenda semanal con slots de 30 minutos, badges de capacidad y cambio de estado de citas
- CRUD completo de pacientes (búsqueda, anamnesis, historial)
- Registro de pagos/planes (Pilates o Fisioterapia, 45 días de vigencia, sesiones restantes). Un paciente puede tener varios planes activos a la vez (distinto tipo, o una renovación comprada antes de vencer) — el consumo de sesiones elige automáticamente el que vence primero
- Formulario de nueva cita con validación de capacidad por slot
- Gestión de estado de cita (Agenda o Dashboard) con 5 acciones explícitas — Confirmar, Completada, No asistió, Reagendar, Cancelar sin descontar — sin conversión automática por horario (esa ventana solo aplica al portal del paciente)
- **Módulo de Ventas (`/ventas`):** registro de ingresos por paquete con autofill de catálogo de precios, selector Pagó/Abonó/Pendiente, fecha de inicio del plan, abono y saldo en tiempo real; crea automáticamente el/los plan(es) de sesiones vinculados (sin pasar por Pacientes); envía correo de confirmación de pago al paciente con desglose y fecha de vencimiento del plan (45 días)
- **Módulo de Gastos (`/gastos`):** registro de egresos con proveedor, NIT, método de pago y descripción

### Portal del Paciente
- Acceso anónimo por número de cédula (flujo QR) o con email/contraseña
- Auto-registro con nombre, cédula, teléfono y email
- **Habeas Data (Ley 1581/2012):** checkbox de consentimiento obligatorio en el registro; modal de interceptación para usuarios existentes que no hayan aceptado aún, con texto legal completo de la Política de Privacidad
- Vista de uno o más planes activos (una tarjeta por plan — puede tener Pilates y Fisioterapia a la vez): tipo, sesiones restantes, barra de progreso, fecha de vencimiento
- Reserva de citas (o Sesión de cortesía si no tiene plan)
- **Cancelación y reprogramación** de citas con restricción de 2 horas de anticipación (esta ventana es exclusiva del portal del paciente — el admin no está sujeto a ella)
- Correo de confirmación automático al reservar

### Médicos Externos en Convenio (v2.0)
- Acceso propio por email/contraseña (creado por el admin, sin flujo anónimo)
- Panel `/medico`: "Mis pacientes / citas agendadas" + formulario "Agendar nuevo paciente" con motivo de remisión
- Al agendar, busca la cédula del paciente (reutiliza el perfil si ya existe) o crea uno nuevo
- Las citas remitidas por un médico **no exigen plan de pago activo** (son consultas de remisión)
- Solo ve las citas que él mismo remitió — nunca la agenda completa

### Panel de Administración — Médicos
- Módulo `/medicos`: listado + creación de cuentas de médico en convenio
- Selector opcional de "Médico en convenio" al agendar cita desde el admin (`NuevaCitaPage`)
- La agenda y el dashboard muestran el "Médico remitente" de cada cita (o "Directo" si no aplica)

### Automatizaciones
- Job cada 5 min: penaliza citas pasadas sin resolver (`No asistió con penalización`)
- Job cada hora: envía recordatorio por email 24h antes de cada cita

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 · Tailwind CSS 3 · React Router 6 · Axios · Lucide React · Recharts |
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2.x · python-jose · bcrypt · slowapi |
| Base de datos | PostgreSQL 15 |
| Email | Resend API (HTTP) — `RESEND_API_KEY` + `RESEND_FROM` opcionales |
| Infraestructura local | Docker + Docker Compose |
| Producción | Railway (backend + PostgreSQL plugin + frontend) |

---

## Ejecutar en local

```bash
# Primera vez o tras cambiar dependencias
docker compose up -d --build
docker compose exec frontend npm install

# Arranque normal
docker compose up -d

# Detener (conserva la BD)
docker compose down

# Detener y borrar datos
docker compose down -v
```

| Servicio | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 · DB: `elysium_agenda` |

> **Windows / Docker en D:** Si los cambios no se reflejan en el frontend, ejecuta `docker compose restart frontend`.

> **Primera vez tras el multi-tenant (`feature/multi-tenant`):** además de `docker compose up -d --build`, hay que crear una sola vez el rol `app_user` que usa Row-Level Security — ver "Multi-tenancy" más abajo. Sin ese paso el backend arranca pero cualquier request que toque la base de datos falla (el rol `app_user` que `docker-compose.yml` ya configura en `APP_DATABASE_URL` no existe todavía en Postgres). Para probar la API a mano (`curl`, Postman, Swagger) hace falta el header `X-Tenant-Slug: elysium` en cada request — el frontend ya lo manda automático.

---

## Variables de entorno

### Backend
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | Cadena de conexión PostgreSQL | `postgresql://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT | cadena aleatoria de 32+ chars |
| `RESEND_API_KEY` | API key de Resend para envío de correos transaccionales | `re_xxxxxxxxxxxx` |
| `RESEND_FROM` | Remitente (opcional) | `Elysium <hola@tudominio.com>` |
| `PORTAL_URL` | Override explícito de la URL del portal en los correos (si no se configura, se arma con `BASE_DOMAIN` + el slug del tenant; si tampoco hay `BASE_DOMAIN`, cae a localhost) | `https://frontend.up.railway.app/portal` |
| `CLINIC_MAPS_URL` | Link de Google Maps a la ubicación de la clínica | `https://share.google/EgQMvc66qfIIYYDZM` |
| `RAILWAY_ENVIRONMENT` | Activa modo producción (deshabilita /docs) | `production` |
| `APP_DATABASE_URL` | Conexión de la app en runtime como `app_user` (no-superusuario) — necesaria para que Row-Level Security restrinja algo. Sin ella cae a `DATABASE_URL` (admin) con un warning en el log. | `postgresql://app_user:pass@host:5432/db` |
| `BASE_DOMAIN` | Dominio base real (Fase 2.4/2.5) — controla el `allow_origin_regex` de CORS (`https://<slug>.<BASE_DOMAIN>` queda permitido automáticamente) y el link de portal en los correos por tenant. Sin configurar, CORS solo permite `localhost:3000` y los correos caen al comportamiento anterior. Reemplaza a `ALLOWED_ORIGINS` (ya no se lee). | `elysium.app` |

> **Correos:** Si `RESEND_API_KEY` no está configurada, los correos se registran en el log con nivel `WARNING` y **no se envían**. Railway bloquea el puerto SMTP 587, por eso se usa Resend API (HTTP) en lugar de Gmail SMTP.

### Frontend
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `REACT_APP_API_URL` | Solo desarrollo — URL del backend cuando se corre en `localhost` (fuera de `localhost`, la URL se deriva en runtime del propio hostname, ver `config/runtime.js`) | `http://localhost:8000` |
| `REACT_APP_DEV_TENANT_SLUG` | Solo desarrollo (renombrada desde `REACT_APP_TENANT_SLUG` en la Fase 2.2) — permite que `localhost` resuelva un tenant sin subdominio real (se manda como header `X-Tenant-Slug`) | `elysium` |
| `REACT_APP_BASE_DOMAIN` | Dominio base real, usado fuera de `localhost` para armar `https://<slug>.api.<REACT_APP_BASE_DOMAIN>` | `elysium.app` |

> Desde la Fase 2.2, ninguna de estas variables se "hornea" en el bundle como URL fija — `config/runtime.js` las lee en runtime vía `window.location.hostname`, así que un solo build de producción sirve a cualquier tenant/subdominio.

---

## Cuentas de prueba

| Rol | Email | Contraseña | Redirige a |
|-----|-------|------------|-----------|
| Admin | `admin@elysium.com` | `admin123` | `/dashboard` |
| Paciente | `paciente@elysium.com` | `paciente123` | `/portal` (Carlos Pérez · cédula `00000001` · Pilates 8/12) |

Ambas cuentas se crean automáticamente en cada arranque si no existen (siempre para el tenant Elysium). No hay cuenta de médico pre-creada — se crea desde `/medicos` (panel admin) o `POST /medicos/`.

---

## Arquitectura

```
WebApp_Elysium/
├── backend/
│   ├── main.py              # App factory · CORS dinámico (BASE_DOMAIN) · TenantMiddleware · lifespan (seeds + jobs asyncio por tenant)
│   ├── database.py          # Engine SQLAlchemy (APP_DATABASE_URL) · SessionLocal · get_db() · current_tenant_id
│   ├── alembic/             # Migraciones (0001 baseline · 0002 multi-tenant schema · 0003 Row-Level Security)
│   ├── limiter.py           # Instancia compartida de slowapi
│   ├── scripts/
│   │   ├── bootstrap_app_role.sql  # Crea el rol app_user que necesita RLS — correr una vez por ambiente
│   │   └── crear_tenant.py  # CLI de alta de tenant (Fase 2.6) — tenant + 2 servicios + admin en una transacción,
│   │                        #   valida slug contra RESERVED_SLUGS, --dry-run, imprime contraseña temporal
│   ├── auth/
│   │   └── jwt.py           # create_access_token · get_current_user (valida tenant_id del JWT) · require_admin · require_medico
│   ├── core/
│   │   ├── features.py      # PLAN_FEATURES · features_efectivas() · require_feature() — feature flags por plan
│   │   ├── servicios.py     # capacidad() · tipos_validos() · hora_valida() — reemplaza los dicts hardcodeados
│   │   ├── planes.py        # plan_disponible() · descontar_sesion() · crear_pago() — FIFO por fecha_vencimiento
│   │   │                    #   cuando un paciente tiene 2+ planes activos del mismo tipo; compartido por
│   │   │                    #   routes/pagos.py y routes/ventas.py
│   │   └── constants.py     # METODOS_PAGO · MAX_PASSWORD_BYTES · RESERVED_SLUGS (deduplicados/reservas de
│   │                        #   infraestructura, no son config de tenant)
│   ├── middleware/
│   │   └── tenant.py        # TenantMiddleware — resuelve el tenant por subdominio / X-Tenant-Slug (dev);
│   │                        #   slug reservado o tenant suspendido → 404 igual que no encontrado (Fase 2.3)
│   ├── models/
│   │   ├── tenant.py        # Tenant · DEFAULT_CONFIG · get_config(ruta, default)
│   │   ├── servicio.py      # Servicio por tenant: nombre, capacidad, duracion_min
│   │   ├── paciente.py      # PK compuesta (tenant_id, 'Paciente') · habeas_data_aceptado · fecha_aceptacion_habeas
│   │   ├── usuario.py       # Usuarios admin/paciente/médico con bcrypt · tenant_id · es_admin · es_medico · habeas_data_aceptado
│   │   ├── cita.py          # tenant_id · fecha · hora · tipo · estado · recordatorio_enviado · medico_id · motivo_remision
│   │   ├── pago.py          # Plan: tenant_id · tipo · sesiones · vigencia (tenant.config)
│   │   ├── venta.py         # Ingresos: tenant_id · paciente_id · nombre_paquete · categoria · valor_total · abono · saldo · estado
│   │   └── gasto.py         # Egresos: tenant_id · nombre · nit · valor · fecha · metodo_pago · descripcion
│   ├── routes/
│   │   ├── auth.py          # POST /auth/login (JWT+tenant_id+habeas+es_medico) · POST /auth/aceptar-habeas · rate-limited 5/min
│   │   ├── tenant.py        # GET /tenant/config — público: branding, features, servicios, horario
│   │   ├── pacientes.py     # CRUD /pacientes/ — solo admin
│   │   ├── citas.py         # CRUD /citas/ — solo admin · job penalización · medico_id/motivo_remision opcionales
│   │   │                    #   patch_estado ya no auto-penaliza por horario (5 acciones explícitas — ver arriba)
│   │   ├── pagos.py         # /pagos/ — solo admin, vía core/planes.py:crear_pago()
│   │   ├── portal.py        # /portal/* — público (tenant resuelto igual) · rate-limited 10/min · habeas requerido en registro
│   │   ├── medicos.py       # /medicos/ — feature "medicos" + admin · crear/listar cuentas de médico en convenio
│   │   ├── medico_portal.py # /medico/* — feature "medico_portal" + médico · agendar (sin plan requerido) + ver sus propias citas
│   │   ├── ventas.py        # CRUD /ventas/ — feature "ventas" + admin · crea Pago(s) vinculado(s) vía core/planes.py
│   │   │                    #   · envía correo de pago al paciente al crear
│   │   └── gastos.py        # CRUD /gastos/ — feature "gastos" + admin
│   └── services/
│       └── email.py         # send_confirmacion · send_recordatorio · send_confirmacion_pago — Resend API (HTTP)
│                            #   reciben el Tenant completo (Fase 2.5): nombre, color y URL de portal por tenant,
│                            #   ya no hardcodeados a Elysium
└── frontend/
    └── src/
        ├── config/
        │   └── runtime.js   # NUEVO (Fase 2.2) — deriva apiUrl/tenantSlug de window.location.hostname en
        │                    #   runtime, no en build-time; en localhost cae a REACT_APP_API_URL /
        │                    #   REACT_APP_DEV_TENANT_SLUG. Un solo build sirve a cualquier tenant.
        ├── api/
        │   ├── client.js    # Instancia única de Axios — importa apiUrl/tenantSlug de config/runtime.js,
        │   │                #   inyecta Authorization + X-Tenant-Slug (dev) en cada request
        │   ├── tenant.js    # getTenantConfig()
        │   └── ...          # auth, pacientes, citas, pagos, portal, medicos, medicoPortal, ventas, gastos (usan client.js)
        ├── constants/
        │   └── packages.js  # Catálogo de precios: Pilates (individual/x2), Fisioterapia, Combos, Prendas de Vestir
        ├── context/
        │   ├── AuthContext.js    # JWT en sessionStorage
        │   └── TenantContext.js  # GET /tenant/config al montar — tenant, features, servicios, horario, hasFeature()
        ├── utils/
        │   └── schedule.js   # buildSlots(horario) — genera los horarios disponibles desde la config del tenant
        ├── components/      # Sidebar (filtrado por feature) · TopBar · PrivateRoute · MedicoRoute · FeatureRoute
        │                    # CitaEstadoModal.js — extraído de AgendaPage.js, reusado por DashboardHome.js
        ├── layouts/         # DashboardLayout
        └── pages/
            ├── LoginPage.js
            ├── DashboardHome.js      # + PieChart de ventas del mes por categoría (recharts); tabla "Citas de
            │                        #   hoy" interactiva vía CitaEstadoModal
            ├── PacientesPage.js      # El modal ya no crea planes ("Agregar nuevo plan" se removió) — eso
            │                        #   ahora solo pasa desde VentasPage.js
            ├── NuevaCitaPage.js
            ├── AgendaPage.js
            ├── PortalPage.js         # Una tarjeta de plan por cada plan activo (planes_activos es una lista)
            ├── MedicosPage.js        # Admin: gestión de médicos en convenio
            ├── MedicoPortalPage.js   # Portal del médico: mis citas + agendar nuevo paciente
            ├── VentasPage.js         # Módulo de ingresos: autofill de catálogo, selector Pagó/Abonó/Pendiente,
            │                        #   fecha de inicio del plan, badges Pagado/Pendiente
            └── GastosPage.js         # Módulo de egresos
```

### Endpoint de configuración de tenant

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/tenant/config` | Público (sin JWT) — `nombre_comercial`, `branding`, `features`, `servicios`, `horario`, `sesion_cortesia`. Nunca expone `plan`/`estado`/`id`/`custom_domain`. |

### Endpoints del portal (público)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/portal/paciente/{cedula}` | Carga plan y citas del paciente |
| POST | `/portal/registro` | Auto-registro — requiere `habeas_data_aceptado: true` |
| POST | `/portal/citas` | Reservar nueva cita |
| POST | `/portal/citas/{id}/cancelar` | Cancelar cita (bloquea si faltan < 2h) |
| POST | `/portal/citas/{id}/reprogramar` | Cambiar fecha/hora (bloquea si faltan < 2h) |

### Endpoints de autenticación

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/login` | Login — devuelve JWT con `habeas_data_aceptado`, `es_medico`, `medico_id` |
| POST | `/auth/aceptar-habeas` | Persiste aceptación Habeas Data (requiere JWT) |
| POST | `/auth/cambiar-password` | Cualquier usuario autenticado cambia su propia contraseña (requiere `password_actual`) |

### Endpoints de médicos en convenio

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/medicos/` | Lista médicos en convenio — solo admin |
| POST | `/medicos/` | Crea una cuenta de médico (email+contraseña+nombre) — solo admin |
| GET | `/medico/citas` | Citas remitidas por el médico autenticado — solo médico |
| POST | `/medico/citas` | Agenda paciente (find-or-create por cédula) + cita, sin exigir plan activo — solo médico |

### Endpoints financieros

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ventas/` | Lista ventas con filtros (paciente, categoría, estado, fechas) — solo admin |
| POST | `/ventas/` | Registra venta · calcula saldo · envía correo de confirmación al paciente — solo admin |
| DELETE | `/ventas/{id}` | Elimina venta — solo admin |
| GET | `/gastos/` | Lista gastos con filtros de fecha — solo admin |
| POST | `/gastos/` | Registra gasto — solo admin |
| DELETE | `/gastos/{id}` | Elimina gasto — solo admin |

---

## Reglas de negocio clave

> Desde la Fase 1 del multi-tenant, estos valores son la **configuración actual de Elysium** (`tenants.config`), no constantes globales — ver "Multi-tenancy" abajo para dónde vive cada uno.

- **Vigencia del plan:** 45 días desde `fecha_inicio` — no `fecha_pago`, un cliente puede empezar el plan antes de terminar de pagarlo (`tenant.get_config("vigencia_plan_dias")`), calculado en el servidor vía `core/planes.py:crear_pago()`.
- **Descuento de sesiones:** Solo al marcar como `completada` o `No asistió con penalización` — no al reservar. Si el paciente tiene 2+ planes activos del mismo tipo, se descuenta del que vence primero (`core/planes.py:plan_disponible`).
- **Ventana de cancelación — solo portal del paciente:** Libre si faltan > 2h (`tenant.get_config("ventana_cancelacion_horas")`). Dentro de la ventana → penalización automática. El admin (Agenda/Dashboard) no está sujeto a esta ventana — elige explícitamente entre 5 acciones en `CitaEstadoModal.js`.
- **Capacidad:** Pilates 6 pacientes/slot · Fisioterapia 2 pacientes/slot — tabla `servicios` por tenant, validado en backend (`core/servicios.py`).
- **Sesión de cortesía:** Máximo una por paciente (excluye canceladas) — límite configurable (`sesion_cortesia.max_por_paciente`).
- **Habeas Data (Ley 1581/2012):** `habeas_data_aceptado` requerido en registro. Usuarios existentes ven un modal de interceptación al iniciar sesión hasta aceptar. Se persiste con `fecha_aceptacion_habeas` en UTC. Texto legal **no** es dinámico por tenant todavía.
- **Migraciones:** Todo cambio de esquema es una revisión de Alembic (`backend/alembic/versions/`) — ya no existe `_run_migrations()`/`create_all()`.
- **Médicos en convenio:** citas con `medico_id` no exigen plan de pago activo (son remisiones). Si luego se marcan como `completada` o `No asistió con penalización` y el paciente sigue sin plan, simplemente no se descuenta sesión.

---

## Multi-tenancy (Fase 1 y 2 completas)

Conversión de single-tenant a SaaS multi-tenant, en `feature/multi-tenant`. Fase 1 (capa de datos, contexto de tenant, config) está completa; Elysium sigue siendo el único tenant real hoy.

- **Modelo:** `tenants` (slug, plan, config JSONB, branding JSONB, features_override JSONB) + `servicios` (catálogo por tenant: nombre, capacidad, duración). "Sesión de cortesía" no tiene fila en `servicios` — reutiliza la capacidad de Pilates; su duración/límite salen de `config.sesion_cortesia`.
- **Aislamiento de datos:** las 6 tablas originales tienen `tenant_id`; `pacientes` pasó a PK compuesta `(tenant_id, "Paciente")` (la cédula puede repetirse entre tenants). Row-Level Security (Postgres) refuerza el aislamiento a nivel de base de datos — la app corre como el rol `app_user` (no-superusuario), nunca como el dueño de las tablas.
- **Resolución de tenant:** por subdominio del header `Host`, o por header `X-Tenant-Slug` en desarrollo (`RAILWAY_ENVIRONMENT != production`). Sin tenant resuelto → `404` genérico.
- **Plan y features:** `plan` (`basico` | `completo`) determina qué módulos están disponibles (`ventas`, `gastos`, `medicos`, `medico_portal`); `features_override` permite excepciones por tenant. `GET /tenant/config` expone esto al frontend.

### Fase 2 — routing por subdominio (completa)

Esquema objetivo (el código ya lo soporta; falta conectar DNS real, eso es Fase 3+): `<slug>.<BASE_DOMAIN>` para el frontend, `<slug>.api.<BASE_DOMAIN>` para el backend, `admin.<BASE_DOMAIN>` reservado para un futuro panel superadmin.

- **2.2:** el frontend deriva `apiUrl`/`tenantSlug` de `window.location.hostname` en runtime (`frontend/src/config/runtime.js`) en vez de una variable de build — un solo build de producción sirve a cualquier tenant.
- **2.3:** `RESERVED_SLUGS` (`core/constants.py`) nunca resuelve a un tenant real, y un tenant con `estado = "suspendido"` da 404 igual que uno inexistente (`TenantMiddleware`).
- **2.4:** CORS dinámico — `allow_origin_regex` permite cualquier `https://<slug>.<BASE_DOMAIN>` automáticamente, sin listar cada tenant; `localhost:3000` se mantiene explícito para desarrollo.
- **2.5:** los correos transaccionales (`services/email.py`) reciben el `Tenant` completo — nombre comercial, color de marca (`tenant.branding.color_primario`) y URL de portal (`<slug>.<BASE_DOMAIN>/portal`) ya no están hardcodeados a Elysium.
- **2.6:** `backend/scripts/crear_tenant.py` da de alta un tenant nuevo (tenant + 2 servicios + admin) sin SQL a mano — ver más abajo.

Ensayo de migración de datos reales (realizado, sin tocar producción): se restauró un dump de la base real de Railway (81 pacientes, 3 usuarios, 17 citas, 17 pagos, 12 ventas) en un entorno Docker aislado y desechable, y se corrieron las migraciones Alembic completas encima — encontró y corrigió un bug de idempotencia real en la migración `0004`. El entorno de ensayo fue destruido por completo al terminar; la base real de Railway nunca recibió una escritura.

Detalle completo de las 5 sub-fases y su verificación: `CLAUDE.md` → sección "Multi-Tenancy → Phase 2".

### Bootstrap del rol `app_user` (una vez por ambiente)

```bash
# Local — edita la contraseña CHANGE_ME en el script primero, y ajusta
# APP_DATABASE_URL en docker-compose.yml para que coincida
docker compose exec -T db psql -U admin -d elysium_agenda < backend/scripts/bootstrap_app_role.sql
```
En Railway: pegar el script en la consola del plugin de Postgres con una contraseña real generada para ese ambiente, y configurar `APP_DATABASE_URL` en el servicio backend.

### Dar de alta un tenant nuevo

```bash
docker compose exec backend python scripts/crear_tenant.py \
  --slug pilatesmed --nombre "Pilates Medellín" --plan completo \
  --admin-email admin@pilatesmed.com --admin-nombre "Ana Ruiz"

# --dry-run valida (formato de slug, RESERVED_SLUGS, duplicados) sin escribir nada
```
Crea el `Tenant`, sus 2 `servicios` por defecto (Pilates 6/60min, Fisioterapia 2/60min — mismos valores base que Elysium) y un `Usuario` admin en una sola transacción; imprime una contraseña temporal una sola vez (no se guarda en texto plano). No hay UI de administración de tenants todavía — eso es Fase 3+.

Detalle completo (RLS, el gotcha de `SET LOCAL`, JWT↔tenant, etc.) está documentado en `CLAUDE.md`.

### Tests

`backend/tests/test_tenant_isolation.py` (pytest + httpx) cubre los 7 criterios de aislamiento automatizables: aislamiento por `SELECT` sin `WHERE`, rechazo de `INSERT` cross-tenant, 0 filas sin contexto, JWT rechazado entre tenants, 403/permisos por plan, `features_override`, y cédula/email duplicados entre tenants sin colisión. Corre contra el Postgres real de docker-compose (RLS no es testeable en SQLite) y crea/borra sus propios tenants de prueba — nunca toca los datos reales de Elysium:

```bash
docker compose exec backend pytest tests/test_tenant_isolation.py -v
```

---

## Pendiente

- [ ] **Fases 3–4 del multi-tenant** — UI de administración de tenants, conectar wildcard DNS/subdominios reales (el código ya soporta el esquema desde la Fase 2), onboarding self-service, facturación
- [ ] **Notificaciones WhatsApp** — n8n webhook → API de WhatsApp (Meta) · recordatorio 24h antes de la cita
- [ ] Configurar `PORTAL_URL` en Railway apuntando al frontend para que el botón "Ver mi portal" en los correos lleve a la URL correcta en producción
- [ ] Actualizar el Start Command del backend en Railway para incluir `alembic upgrade head` antes de `uvicorn` (cambio manual pendiente en el dashboard de Railway)
- [ ] Reemplazar `main` en Railway con `feature/multi-tenant` para el cliente real — requiere su propio plan (backup, ventana de mantenimiento, Start Command)
