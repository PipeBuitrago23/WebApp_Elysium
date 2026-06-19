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