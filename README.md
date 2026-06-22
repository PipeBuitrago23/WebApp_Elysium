# Contexto General del Proyecto: Agenda Elysium

## Descripción del Negocio
Sistema integral de agendamiento para Elysium Fisio-pilates (sede única). El sistema maneja dos tipos de usuarios:
1. **Administrador/Staff:** Control total de la agenda, asistencias, cancelaciones y métricas.
2. **Pacientes (Externos):** Autogestión de citas para Fisioterapia o Pilates, registro de datos básicos y anamnesis breve (antecedentes, cirugías).

## Arquitectura y Stack Tecnológico
* **Tipo de Aplicación:** Progressive Web App (PWA).
* **Frontend:** React.js (o Vue.js) interactivo y responsivo.
* **Backend:** Python con FastAPI.
* **Base de Datos:** PostgreSQL. *Nota estricta de diseño: Usar la columna `Paciente` (no ID_Paciente ni variaciones) como llave o identificador principal en las tablas relevantes para mantener coherencia con otros sistemas.*
* **Infraestructura:** Docker y Docker Compose para desarrollo local y futuro despliegue. 
* **Integraciones Futuras:** Webhooks vía n8n para enviar recordatorios por la API de WhatsApp de Meta.

## Reglas de Desarrollo para la IA
1.  **Código Limpio y Modular:** Separa la lógica de negocio, las rutas y la base de datos.
2.  **Seguridad Primero:** Las contraseñas y datos sensibles deben estar encriptados. Implementar autenticación JWT.
3.  **Respuestas Directas:** Al generar código, omite explicaciones excesivas a menos que se solicite. Provee el código estructurado por archivos.

---

## Estado del Desarrollo (2026-06-18)

### Completado

| Capa | Archivo | Descripción |
|------|---------|-------------|
| Infra | `docker-compose.yml` | Stack completo: db + backend + frontend con healthcheck |
| Backend | `main.py` | App factory, CORS, lifespan (create_all + seed admin) |
| Backend | `database.py` | Engine SQLAlchemy, SessionLocal, get_db() |
| Backend | `auth/jwt.py` | create_access_token, verify_token, **get_current_user** (dep. JWT) |
| Backend | `models/usuario.py` | Tabla usuarios con bcrypt |
| Backend | `models/paciente.py` | Tabla pacientes (PK = columna `Paciente`, anamnesis incluida) |
| Backend | `routes/auth.py` | POST /auth/login → JWT |
| Backend | `routes/pacientes.py` | **CRUD completo** (GET list+search, GET by id, POST, PUT, DELETE) — todas protegidas con JWT |
| Frontend | `api/auth.js` | loginRequest() con x-www-form-urlencoded |
| Frontend | `context/AuthContext.js` | AuthProvider, useAuth(), token en localStorage (`elysium_token`) |
| Frontend | `components/PrivateRoute.js` | Redirige a /login si no hay sesión |
| Frontend | `layouts/DashboardLayout.js` | Sidebar + TopBar + `<Outlet />` |
| Frontend | `components/Sidebar.js` | Sidebar oscuro slate-900, nav activo teal-600 |
| Frontend | `components/TopBar.js` | Barra de título por ruta |
| Frontend | `pages/LoginPage.js` | Formulario login, diseño teal/slate |
| Frontend | `pages/DashboardHome.js` | 4 tarjetas de estadísticas + tabla vacía de citas |

### Siguiente paso inmediato

**`frontend/src/api/pacientes.js`** — helpers Axios para los 5 endpoints CRUD de pacientes.
**`frontend/src/pages/PacientesPage.js`** — tabla buscable + formulario de registro/edición con anamnesis.

### Pendiente (en orden)

1. `frontend/src/api/pacientes.js` + `frontend/src/pages/PacientesPage.js`
2. `backend/models/cita.py` — modelo Cita (fecha, hora, tipo, FK paciente, notas)
3. `backend/routes/citas.py` — CRUD de citas protegido con JWT
4. `frontend/src/pages/NuevaCitaPage.js` — formulario de reserva
5. `frontend/src/pages/AgendaPage.js` — vista calendario semanal/diaria