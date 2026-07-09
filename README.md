# Elysium Fisio-Pilates — Sistema de Agendamiento

Aplicación web para la gestión de citas, planes y pacientes de una clínica de fisioterapia y pilates. Incluye panel de administración completo y portal de autogestión para pacientes.

---

## Funcionalidades

### Panel de Administración
- Dashboard con métricas en tiempo real (citas hoy/semana/mes, pacientes activos/inactivos)
- Agenda semanal con slots de 30 minutos, badges de capacidad y cambio de estado de citas
- CRUD completo de pacientes (búsqueda, anamnesis, historial)
- Registro de pagos/planes (Pilates o Fisioterapia, 45 días de vigencia, sesiones restantes)
- Formulario de nueva cita con validación de capacidad por slot

### Portal del Paciente
- Acceso anónimo por número de cédula (flujo QR) o con email/contraseña
- Auto-registro con nombre, cédula, teléfono y email
- Vista del plan activo: tipo, sesiones restantes, barra de progreso, fecha de vencimiento
- Reserva de citas (o Sesión de cortesía si no tiene plan)
- **Cancelación y reprogramación** de citas con restricción de 2 horas de anticipación
- Correo de confirmación automático al reservar

### Automatizaciones
- Job cada 5 min: penaliza citas pasadas sin resolver (`No asistió con penalización`)
- Job cada hora: envía recordatorio por email 24h antes de cada cita

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 · Tailwind CSS 3 · React Router 6 · Axios · Lucide React |
| Backend | Python 3.11 · FastAPI · SQLAlchemy 2.x · python-jose · bcrypt · slowapi |
| Base de datos | PostgreSQL 15 |
| Email | Gmail SMTP (smtplib, STARTTLS, port 587) |
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
| `GMAIL_USER` | Cuenta Gmail para envío de correos | `elysium@gmail.com` |
| `GMAIL_APP_PASSWORD` | App Password de Google (no la contraseña de la cuenta) | `abcd efgh ijkl mnop` |
| `RAILWAY_ENVIRONMENT` | Activa modo producción (deshabilita /docs) | `production` |

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

Ambas cuentas se crean automáticamente en cada arranque si no existen.

---

## Arquitectura

```
WebApp_Elysium/
├── backend/
│   ├── main.py              # App factory · CORS · lifespan · migraciones · jobs asyncio
│   ├── database.py          # Engine SQLAlchemy · SessionLocal · get_db()
│   ├── limiter.py           # Instancia compartida de slowapi
│   ├── auth/
│   │   └── jwt.py           # create_access_token · get_current_user · require_admin
│   ├── models/
│   │   ├── paciente.py      # PK = columna 'Paciente' (string/cédula)
│   │   ├── usuario.py       # Usuarios admin y pacientes con bcrypt
│   │   ├── cita.py          # fecha · hora · tipo · estado · recordatorio_enviado
│   │   └── pago.py          # Plan: tipo · sesiones · vigencia 45 días
│   ├── routes/
│   │   ├── auth.py          # POST /auth/login — rate-limited 5/min
│   │   ├── pacientes.py     # CRUD /pacientes/ — solo admin
│   │   ├── citas.py         # CRUD /citas/ — solo admin · job penalización
│   │   ├── pagos.py         # /pagos/ — solo admin
│   │   └── portal.py        # /portal/* — público · rate-limited 10/min
│   └── services/
│       └── email.py         # send_confirmacion · send_recordatorio (Gmail SMTP)
└── frontend/
    └── src/
        ├── api/             # Clientes Axios por recurso
        ├── context/
        │   └── AuthContext.js   # JWT en sessionStorage
        ├── components/      # Sidebar · TopBar · PrivateRoute
        ├── layouts/         # DashboardLayout
        └── pages/
            ├── LoginPage.js
            ├── DashboardHome.js
            ├── PacientesPage.js
            ├── NuevaCitaPage.js
            ├── AgendaPage.js
            └── PortalPage.js
```

### Endpoints del portal (público)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/portal/paciente/{cedula}` | Carga plan y citas del paciente |
| POST | `/portal/registro` | Auto-registro (nombre · cédula · teléfono · email) |
| POST | `/portal/citas` | Reservar nueva cita |
| POST | `/portal/citas/{id}/cancelar` | Cancelar cita (bloquea si faltan < 2h) |
| POST | `/portal/citas/{id}/reprogramar` | Cambiar fecha/hora (bloquea si faltan < 2h) |

---

## Reglas de negocio clave

- **Vigencia del plan:** 45 días desde `fecha_pago`, calculado en el servidor.
- **Descuento de sesiones:** Solo al marcar como `completada` o `No asistió con penalización` — no al reservar.
- **Ventana de cancelación:** Libre si faltan > 2h. Dentro de las 2h → penalización automática.
- **Capacidad:** Pilates 6 pacientes/slot · Fisioterapia 2 pacientes/slot · validado en backend.
- **Sesión de cortesía:** Máximo una por paciente (excluye canceladas).
- **Migraciones:** Columnas nuevas en modelos existentes deben declararse en `_run_migrations()` en `main.py` con `ADD COLUMN IF NOT EXISTS`.

---

## Pendiente

- [ ] **Notificaciones WhatsApp** — n8n webhook → API de WhatsApp (Meta) · recordatorio 24h antes de la cita
