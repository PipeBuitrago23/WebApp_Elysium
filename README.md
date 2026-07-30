# Elysium Fisio-Pilates — Sistema de Agendamiento

Aplicación web para la gestión de citas, planes y pacientes de una clínica de fisioterapia y pilates. Incluye panel de administración completo y portal de autogestión para pacientes.

---

## Funcionalidades

### Panel de Administración
- Dashboard con métricas en tiempo real (citas hoy/semana/mes, pacientes activos/inactivos) + PieChart de ventas del mes por categoría
- Agenda semanal con slots de 30 minutos, badges de capacidad y cambio de estado de citas
- CRUD completo de pacientes (búsqueda, anamnesis, historial)
- Registro de pagos/planes (Pilates o Fisioterapia, 45 días de vigencia, sesiones restantes)
- Formulario de nueva cita con validación de capacidad por slot
- **Módulo de Ventas (`/ventas`):** registro de ingresos por paquete con autofill de catálogo de precios, badge Pagado/Pendiente, abono y saldo en tiempo real; envía correo de confirmación de pago al paciente con desglose y fecha de vencimiento del plan (45 días)
- **Módulo de Gastos (`/gastos`):** registro de egresos con proveedor, NIT, método de pago y descripción

### Portal del Paciente
- Acceso anónimo por número de cédula (flujo QR) o con email/contraseña
- Auto-registro con nombre, cédula, teléfono y email
- **Habeas Data (Ley 1581/2012):** checkbox de consentimiento obligatorio en el registro; modal de interceptación para usuarios existentes que no hayan aceptado aún, con texto legal completo de la Política de Privacidad
- Vista del plan activo: tipo, sesiones restantes, barra de progreso, fecha de vencimiento
- Reserva de citas (o Sesión de cortesía si no tiene plan)
- **Cancelación y reprogramación** de citas con restricción de 2 horas de anticipación
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

---

## Variables de entorno

### Backend
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | Cadena de conexión PostgreSQL | `postgresql://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | Clave secreta para firmar tokens JWT | cadena aleatoria de 32+ chars |
| `ALLOWED_ORIGINS` | URLs de frontend permitidas (CORS), separadas por coma | `https://mi-app.up.railway.app` |
| `RESEND_API_KEY` | API key de Resend para envío de correos transaccionales | `re_xxxxxxxxxxxx` |
| `RESEND_FROM` | Remitente (opcional) | `Elysium <hola@tudominio.com>` |
| `PORTAL_URL` | URL pública del portal del paciente (usada en botones de correo) | `https://frontend.up.railway.app/portal` |
| `CLINIC_MAPS_URL` | Link de Google Maps a la ubicación de la clínica | `https://share.google/EgQMvc66qfIIYYDZM` |
| `RAILWAY_ENVIRONMENT` | Activa modo producción (deshabilita /docs) | `production` |

> **Correos:** Si `RESEND_API_KEY` no está configurada, los correos se registran en el log con nivel `WARNING` y **no se envían**. Railway bloquea el puerto SMTP 587, por eso se usa Resend API (HTTP) en lugar de Gmail SMTP.

### Frontend
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `REACT_APP_API_URL` | URL pública del backend | `https://backend.up.railway.app` |

> `REACT_APP_API_URL` se bake en el bundle en tiempo de build — debe configurarse como variable de build en Railway antes de redesplegar el frontend.

---

## Cuentas de prueba

| Rol | Email | Contraseña | Redirige a |
|-----|-------|------------|-----------|
| Admin | `admin@elysium.com` | `admin123` | `/dashboard` |
| Paciente | `paciente@elysium.com` | `paciente123` | `/portal` (Carlos Pérez · cédula `00000001` · Pilates 8/12) |

Ambas cuentas se crean automáticamente en cada arranque si no existen. No hay cuenta de médico pre-creada — se crea desde `/medicos` (panel admin) o `POST /medicos/`.

---

## Arquitectura

```
WebApp_Elysium/
├── backend/
│   ├── main.py              # App factory · CORS · lifespan · migraciones · jobs asyncio
│   ├── database.py          # Engine SQLAlchemy · SessionLocal · get_db()
│   ├── limiter.py           # Instancia compartida de slowapi
│   ├── auth/
│   │   └── jwt.py           # create_access_token · get_current_user · require_admin · require_medico
│   ├── models/
│   │   ├── paciente.py      # PK = columna 'Paciente' · habeas_data_aceptado · fecha_aceptacion_habeas
│   │   ├── usuario.py       # Usuarios admin/paciente/médico con bcrypt · es_admin · es_medico · habeas_data_aceptado
│   │   ├── cita.py          # fecha · hora · tipo · estado · recordatorio_enviado · medico_id · motivo_remision
│   │   ├── pago.py          # Plan: tipo · sesiones · vigencia 45 días
│   │   ├── venta.py         # Ingresos: paciente_id · nombre_paquete · categoria · valor_total · abono · saldo · estado
│   │   └── gasto.py         # Egresos: nombre · nit · valor · fecha · metodo_pago · descripcion
│   ├── routes/
│   │   ├── auth.py          # POST /auth/login (JWT+habeas+es_medico) · POST /auth/aceptar-habeas · rate-limited 5/min
│   │   ├── pacientes.py     # CRUD /pacientes/ — solo admin
│   │   ├── citas.py         # CRUD /citas/ — solo admin · job penalización · medico_id/motivo_remision opcionales
│   │   ├── pagos.py         # /pagos/ — solo admin
│   │   ├── portal.py        # /portal/* — público · rate-limited 10/min · habeas requerido en registro
│   │   ├── medicos.py       # /medicos/ — solo admin · crear/listar cuentas de médico en convenio
│   │   ├── medico_portal.py # /medico/* — solo médico · agendar (sin plan requerido) + ver sus propias citas
│   │   ├── ventas.py        # CRUD /ventas/ — solo admin · envía correo de pago al paciente al crear
│   │   └── gastos.py        # CRUD /gastos/ — solo admin
│   └── services/
│       └── email.py         # send_confirmacion · send_recordatorio · send_confirmacion_pago — Resend API (HTTP)
└── frontend/
    └── src/
        ├── api/             # Clientes Axios por recurso (auth, pacientes, citas, pagos, portal, medicos, medicoPortal, ventas, gastos)
        ├── constants/
        │   └── packages.js  # Catálogo de precios: Pilates (individual/x2), Fisioterapia, Combos, Prendas de Vestir
        ├── context/
        │   └── AuthContext.js   # JWT en sessionStorage
        ├── components/      # Sidebar · TopBar · PrivateRoute · MedicoRoute
        ├── layouts/         # DashboardLayout
        └── pages/
            ├── LoginPage.js
            ├── DashboardHome.js      # + PieChart de ventas del mes por categoría (recharts)
            ├── PacientesPage.js
            ├── NuevaCitaPage.js
            ├── AgendaPage.js
            ├── PortalPage.js
            ├── MedicosPage.js        # Admin: gestión de médicos en convenio
            ├── MedicoPortalPage.js   # Portal del médico: mis citas + agendar nuevo paciente
            ├── VentasPage.js         # Módulo de ingresos con autofill de catálogo y badges Pagado/Pendiente
            └── GastosPage.js         # Módulo de egresos
```

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

- **Vigencia del plan:** 45 días desde `fecha_pago`, calculado en el servidor.
- **Descuento de sesiones:** Solo al marcar como `completada` o `No asistió con penalización` — no al reservar.
- **Ventana de cancelación:** Libre si faltan > 2h. Dentro de las 2h → penalización automática.
- **Capacidad:** Pilates 6 pacientes/slot · Fisioterapia 2 pacientes/slot · validado en backend.
- **Sesión de cortesía:** Máximo una por paciente (excluye canceladas).
- **Habeas Data (Ley 1581/2012):** `habeas_data_aceptado` requerido en registro. Usuarios existentes ven un modal de interceptación al iniciar sesión hasta aceptar. Se persiste con `fecha_aceptacion_habeas` en UTC.
- **Migraciones:** Columnas nuevas en modelos existentes deben declararse en `_run_migrations()` en `main.py` con `ADD COLUMN IF NOT EXISTS`.
- **Médicos en convenio:** citas con `medico_id` no exigen plan de pago activo (son remisiones). Si luego se marcan como `completada` o `No asistió con penalización` y el paciente sigue sin plan, simplemente no se descuenta sesión.

---

## Pendiente

- [ ] **Notificaciones WhatsApp** — n8n webhook → API de WhatsApp (Meta) · recordatorio 24h antes de la cita
- [ ] Configurar `PORTAL_URL` en Railway apuntando al frontend para que el botón "Ver mi portal" en los correos lleve a la URL correcta en producción
