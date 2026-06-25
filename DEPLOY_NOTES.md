# Notas de Despliegue — WebApp Elysium en Railway

> Fecha: 24 de junio de 2026

---

## Resumen

Despliegue completo de la aplicacion **Elysium Fisio Pilates** en Railway.
Stack: **React (CRA)** + **FastAPI** + **PostgreSQL** en monorepo `PipeBuitrago23/WebApp_Elysium`.

---

## URLs en produccion

| Servicio | URL |
|---|---|
| **Frontend** | https://marvelous-illumination-production-a83b.up.railway.app |
| **Backend** | https://webappelysium-production.up.railway.app |
| **Swagger** | https://webappelysium-production.up.railway.app/docs |

---

## Credenciales de prueba

| Rol | Email | Contrasena |
|---|---|---|
| Administrador | admin@elysium.com | admin123 |
| Paciente demo | paciente@elysium.com | paciente123 |

---

## IDs del proyecto Railway

- Project ID: f4e59715-8f0c-4830-8ba1-8cc69ea353a5
- Environment ID: 7af081fd-4e2b-40a8-bc3d-39677024a5c4
- Backend Service ID: fccdbd93-d9b2-4b9c-bcf9-78b5d1128fc2
- Frontend Service ID: 3cdb4f5d-a71f-4c74-a673-a8c115a68f72

---

## Configuracion de servicios en Railway

### Backend (WebApp_Elysium)

| Parametro | Valor |
|---|---|
| Root Directory | /backend |
| Builder | Dockerfile (auto-detectado) |
| Start Command | `sh -c 'uvicorn main:app --host 0.0.0.0 --port $PORT'` |

Variables de entorno del backend:
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
JWT_SECRET_KEY=elysium-secret-key-produccion-2026-muy-segura
ALLOWED_ORIGINS=https://webappelysium-production.up.railway.app,https://marvelous-illumination-production-a83b.up.railway.app
```

### Frontend (marvelous-illumination)

| Parametro | Valor |
|---|---|
| Root Directory | /frontend |
| Builder | Dockerfile (auto-detectado) |
| Start Command | `sh -c 'npx serve -s build -l $PORT'` |
| Networking Port | 8080 (asignado dinamicamente por Railway) |

Variables de entorno del frontend:
```
REACT_APP_API_URL=https://webappelysium-production.up.railway.app
```

---

## Errores encontrados y soluciones

### Error 1 — $PORT no se expande en el Start Command

**Sintoma backend:**
```
Error: Invalid value for '--port': '$PORT' is not a valid integer.
```

**Sintoma frontend:**
```
Error: Unknown --listen endpoint scheme (protocol): undefined
```

**Causa:** Railway no expande variables de shell en el campo Start Command directamente. La shell no se invoca, por lo que `$PORT` llega como string literal.

**Solucion:** Envolver con `sh -c '...'`:
```bash
# Backend - antes (no funcionaba)
uvicorn main:app --host 0.0.0.0 --port $PORT

# Backend - despues (correcto)
sh -c 'uvicorn main:app --host 0.0.0.0 --port $PORT'

# Frontend - antes (no funcionaba)
npx serve -s build -l $PORT

# Frontend - despues (correcto)
sh -c 'npx serve -s build -l $PORT'
```

---

### Error 2 — "Application failed to respond" en la URL del frontend

**Sintoma:** La URL del frontend mostraba el error de Railway "Application failed to respond".

**Causa:** El proxy de Railway estaba configurado para enrutar al puerto **3000**, pero `serve` estaba escuchando en el puerto **8080** (el valor real de `$PORT` asignado por Railway).

**Solucion:** En Railway: Settings → Networking → editar dominio → cambiar puerto destino de **3000** a **8080**. Railway lo detecto automaticamente como "8080 (node)".

---

### Error 3 — 404 "The requested path could not be found"

**Sintoma:** La URL del frontend respondia pero mostraba 404 en todas las rutas.

**Causa:** El `/frontend/Dockerfile` original NO tenia el paso `RUN npm run build`. Solo instalaba dependencias, nunca compilaba React. La carpeta `/app/build` no existia y `serve -s build` no encontraba nada.

**Dockerfile original (incompleto):**
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 3000
# Faltaba: RUN npm run build y CMD
```

**Solucion:**
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["sh", "-c", "npx serve -s build -l $PORT"]
```

---

### Error 4 — Login queda en "Ingresando..." y nunca completa

**Sintoma:** El frontend cargaba pero el login quedaba colgado indefinidamente.

**Diagnostico del bundle JS compilado:**
- `"localhost:8000"` aparecia 4 veces en el bundle
- `"webappelysium-production.up.railway.app"` NO aparecia

**Causa:** Create React App (CRA) embebe las variables `REACT_APP_*` en el bundle **en tiempo de build**, no en runtime. Como el Dockerfile no declaraba `ARG REACT_APP_API_URL`, la variable de Railway no se pasaba a `npm run build`. El bundle quedaba con `localhost:8000` hardcodeado.

**Solucion:** Agregar `ARG` y `ENV` en el Dockerfile ANTES de `RUN npm run build`:
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
RUN npm run build
EXPOSE 3000
CMD ["sh", "-c", "npx serve -s build -l $PORT"]
```

Railway pasa automaticamente las variables de entorno del servicio como `--build-arg` cuando el Dockerfile declara el `ARG` correspondiente.

---

## Dockerfile final de produccion (/frontend/Dockerfile)

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
RUN npm run build
EXPOSE 3000
CMD ["sh", "-c", "npx serve -s build -l $PORT"]
```

---

## Lecciones aprendidas

1. **Siempre usar `sh -c '...'` en Railway** para Start Commands que usen variables de entorno como `$PORT`.

2. **CRA bake env vars en build-time**: Las variables `REACT_APP_*` deben estar disponibles cuando corre `npm run build`. No sirve pasarlas solo en runtime.

3. **Docker ARG + ENV**: Para pasar variables de CI/CD al build de Docker se declara `ARG` (recibe el `--build-arg`) y luego `ENV` para exponerla al proceso `RUN`.

4. **Railway pasa env vars como build-args automaticamente**: Si el Dockerfile declara `ARG NOMBRE`, Railway inyecta el valor de esa variable del servicio como Docker build argument.

5. **Puerto de Networking debe coincidir con el puerto real**: Railway asigna el puerto via `$PORT` dinamicamente. Mismatch entre el puerto real y el configurado en Networking = "Application failed to respond".

6. **Revisar Build Logs y Deploy Logs por separado**: Muchos errores de runtime se originan en el build. Los Build Logs revelan si el builder ejecuto todos los pasos del Dockerfile.

---

## Historial de commits de correcciones

| Commit | Cambio realizado | Resultado |
|---|---|---|
| Add build step and serve command to Dockerfile | RUN npm run build + CMD en Dockerfile | Frontend carga, pero API URL = localhost (login falla) |
| Add support for REACT_APP_API_URL in Dockerfile | ARG + ENV antes del RUN npm run build | Todo funcional correctamente |

---

## Tests de verificacion realizados

- `GET /health` → `{"status":"ok"}` OK
- `POST /auth/login` (admin@elysium.com / admin123) → 200 OK + JWT token
- `GET /pacientes/` → 200 OK, lista de pacientes con datos seed
- `GET /citas/` → 200 OK
- `GET /pagos/` → 200 OK, 1 pago
- `GET /docs` → Swagger UI carga correctamente
- Login en frontend → Dashboard carga con datos reales de la BD
