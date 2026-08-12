# Runbook de cutover — reemplazar `main` con `feature/multi-tenant` en Railway

Este documento es el procedimiento paso a paso para migrar la base de datos y
el despliegue reales de Railway (hoy corriendo el código de `main`,
single-tenant) al código de `feature/multi-tenant`, contra los mismos datos
reales de producción. No es un ejercicio — a diferencia del ensayo de
migración hecho antes en un entorno Docker aislado y desechable, estos pasos
tocan la base de datos y los servicios reales.

Antes de ejecutar esto, confirmar que `feature/multi-tenant` está en el
estado que se quiere desplegar (Fase 1 y Fase 2 completas — ver `CLAUDE.md`)
y que no hay trabajo pendiente sin comitear.

## 0. Resumen de lo que cambia

| | Antes (`main`, hoy en producción) | Después (`feature/multi-tenant`) |
|---|---|---|
| Esquema | `Base.metadata.create_all()` + `_run_migrations()` hand-rolled, sin historial de Alembic | Alembic (`0001`→`0005`), con Row-Level Security |
| Conexión runtime del backend | Superusuario/dueño de tablas (`DATABASE_URL`) | `app_user`, no-superusuario (`APP_DATABASE_URL`) — necesario para que RLS restrinja algo |
| Start Command backend | `sh -c 'uvicorn main:app --host 0.0.0.0 --port $PORT'` | `sh -c 'alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT'` |
| CORS | `ALLOWED_ORIGINS` (lista fija, coma-separada) | `ALLOWED_ORIGINS` (mismo formato, se sigue soportando) + `allow_origin_regex` opcional vía `BASE_DOMAIN` para cuando haya subdominios reales |
| Tenant | Implícito (una sola clínica) | Explícito — todo dato queda bajo el tenant `elysium`, creado por la migración `0002` |

Referencia de la configuración actual real de Railway (proyecto, IDs de
servicio, Start Command, env vars vigentes hoy): `DEPLOY_NOTES.md` en la
raíz del repo — fue el runbook del primer despliegue de `main` y describe el
estado que este cutover reemplaza.

## 1. Pre-requisitos

- [ ] Acceso al proyecto de Railway (dashboard + `railway` CLI o consola web de Postgres).
- [ ] `feature/multi-tenant` con todo comiteado y, idealmente, ya en GitHub.
- [ ] Ventana de mantenimiento comunicada — hay downtime real durante los pasos 3-7 (el backend no debe recibir escrituras mientras se migra el esquema).
- [ ] Docker disponible localmente (se usa un contenedor `postgres:18` para el backup/restore — Railway corre Postgres 18.4, y `pg_dump`/`pg_restore` exigen que la versión del cliente sea ≥ la del servidor).
- [ ] La `DATABASE_URL` pública de Railway (Postgres → pestaña "Connect" → "Public Network") a mano — es la conexión admin/dueña de las tablas, la misma que usa Alembic.

## 2. Backup

**No continuar sin esto.** Un `pg_dump` completo, guardado fuera del repo:

```bash
docker run --rm postgres:18 pg_dump "<DATABASE_URL pública de Railway>" -F c \
  > elysium_prod_backup_$(date +%Y%m%d_%H%M).dump
```

Verificar que el archivo no esté vacío y que el TOC liste las 6 tablas
esperadas antes de seguir:

```bash
docker run --rm -v "$(pwd):/backup" postgres:18 \
  pg_restore -l /backup/elysium_prod_backup_*.dump
```

Guardar este dump en un lugar seguro fuera del repo (no commitear). Es el
plan de rollback si algo sale mal más adelante.

## 3. Poner el backend en mantenimiento

Detener (o escalar a 0 réplicas) el servicio backend en Railway, o al menos
confirmar que no hay tráfico de escritura activo — desde este punto hasta el
final del paso 7, cualquier escritura contra la base real quedaría en un
estado intermedio inconsistente si el esquema cambia debajo.

## 4. Bootstrap del rol `app_user` (una sola vez, contra producción real)

`backend/scripts/bootstrap_app_role.sql` es idempotente — crea el rol solo
si no existe, y el resto son `GRANT`/`ALTER DEFAULT PRIVILEGES`, que Postgres
trata como no-op si ya están otorgados. Seguro correrlo aunque no se esté
seguro de si ya se corrió antes.

1. Generar un secreto real (no usar el `CHANGE_ME` del archivo):
   ```bash
   openssl rand -base64 24
   ```
2. Abrir la consola de Postgres en Railway (plugin Postgres → pestaña
   "Query" o `railway connect postgres`), pegar el contenido de
   `backend/scripts/bootstrap_app_role.sql` reemplazando `CHANGE_ME` por el
   secreto generado, y ejecutar.
3. Anotar la `APP_DATABASE_URL` resultante:
   `postgresql://app_user:<secreto>@<host>:<puerto>/<db>` (mismo host/puerto/db
   que la `DATABASE_URL` admin, solo cambia el usuario).

## 5. `alembic stamp 0001` — paso MANUAL, antes del deploy

**Esto es obligatorio y no lo hace el Start Command.** El Start Command del
backend corre `alembic upgrade head`, que aplica migraciones *desde donde
Alembic cree que está la base* — pero esta base de datos nunca corrió
Alembic: sus 6 tablas fueron creadas por el `_run_migrations()`/`create_all()`
de `main`, así que no existe tabla `alembic_version` todavía. Si se despliega
sin este paso, `alembic upgrade head` intentará ejecutar la revisión `0001`
desde cero — que hace `CREATE TABLE pacientes`, `CREATE TABLE usuarios`,
etc. — sobre un esquema donde esas tablas **ya existen**, y fallará con un
error de tabla duplicada. El servicio no arranca. **Esto está verificado: es
exactamente lo que pasó en el ensayo de migración** (documentado en el
docstring de `backend/alembic/versions/0004_pago_fecha_inicio.py` — ahí fue
`0004` el que chocó por una razón distinta, pero confirma que un esquema que
ya tiene columnas/tablas sin que Alembic lo sepa rompe el arranque).

`alembic stamp 0001` marca la base como "ya está en la revisión 0001" sin
ejecutar su `upgrade()` — crea la tabla `alembic_version` con ese valor. A
partir de ahí, `alembic upgrade head` (ya sea corrido a mano ahora para
verificar, o automáticamente por el Start Command en el deploy) aplica
`0002`→`0003`→`0004`→`0005` en orden, que es exactamente lo que necesita esta
base real.

**No usar `alembic stamp head`** — con `0002`-`0005` ya existiendo en el
repo, `head` apunta a `0005`, y stampear head marcaría la base como si ya
tuviera todo el esquema multi-tenant sin haberlo aplicado nunca. El propio
docstring de `0001_baseline.py` tenía este error (decía "stamp head" de
cuando 0001 era la única revisión) — se corrigió en esta misma preparación,
ver commit correspondiente.

```bash
# Corrido una sola vez, manualmente, ANTES de desplegar feature/multi-tenant.
# Usa DATABASE_URL (admin), no APP_DATABASE_URL — igual que Alembic siempre.
# En Windows/Git Bash: anteponer MSYS_NO_PATHCONV=1 — sin eso, Git Bash
# reescribe silenciosamente el `-w /app` a una ruta de Windows inválida
# (mismo gotcha documentado en el ensayo de migración, ver CLAUDE.md).
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd)/backend:/app" -w /app \
  -e DATABASE_URL="<DATABASE_URL pública de Railway>" \
  webapp_elysium-backend:latest \
  alembic stamp 0001

# Verificar antes de seguir:
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd)/backend:/app" -w /app \
  -e DATABASE_URL="<DATABASE_URL pública de Railway>" \
  webapp_elysium-backend:latest \
  alembic current
# Debe imprimir: 0001 (head)  ← "(head)" acá es relativo a 0001 mismo, no al head real del repo
```

(Si `webapp_elysium-backend:latest` no existe localmente: `docker compose
build backend` primero, o usar `python:3.11-slim` con `pip install -r
backend/requirements.txt` y correr `alembic` directo — cualquier entorno con
el código de `backend/` y sus dependencias sirve, no hace falta el
contenedor real de producción.)

## 6. Variables de entorno requeridas en Railway (backend)

| Variable | Acción | Nota |
|---|---|---|
| `DATABASE_URL` | Ya existe (`${{Postgres.DATABASE_URL}}`) | Sin cambios — sigue siendo la conexión admin que usa Alembic |
| `APP_DATABASE_URL` | **Agregar** | El valor generado en el paso 4. Sin esta variable el backend en producción **ya no arranca** (falla duro — ver `database.py`, agregado en esta misma preparación) |
| `RAILWAY_ENVIRONMENT` | Verificar que ya esté en `production` | Railway la setea sola normalmente; confirmarla — de ella depende el fallo duro de `APP_DATABASE_URL` y el bloqueo de `/docs` |
| `ALLOWED_ORIGINS` | Ya existe, dejar como está | `https://webappelysium-production.up.railway.app,https://marvelous-illumination-production-a83b.up.railway.app` (o los dominios reales vigentes) — se sigue leyendo igual que antes, sumado ahora a `localhost:3000` internamente |
| `BASE_DOMAIN` | **No configurar todavía** | Solo tiene sentido una vez haya wildcard DNS real apuntando a Railway (Fase 3+). Configurarla antes de tener esos subdominios no rompe nada (`ALLOWED_ORIGINS` sigue cubriendo el frontend real), pero tampoco aporta nada todavía |
| `JWT_SECRET_KEY` | Sin cambios | |
| `RESEND_API_KEY` / `RESEND_FROM` | Verificar que sigan configuradas | Si no lo están, los correos quedan en modo log (no se envían) — mismo comportamiento de siempre, no bloquea el arranque |
| `PORTAL_URL` | **Agregar si no existe** | Apuntar al frontend real (`https://marvelous-illumination-production-a83b.up.railway.app/portal` o el dominio vigente) — sin esto, el link "Ver mi portal" de los correos apunta a `localhost:3000` en producción. Ya estaba pendiente antes de este cutover (ver `CLAUDE.md` → "Next to build") |
| `CLINIC_MAPS_URL` | Verificar que siga configurada | |

### Frontend

| Variable | Acción | Nota |
|---|---|---|
| `REACT_APP_API_URL` | Sin cambios | Sigue siendo build-time; `config/runtime.js` solo cambia a resolución por hostname fuera de `localhost`, y hoy el frontend real sigue viviendo en un dominio de Railway sin subdominio de tenant, así que sigue usando esta variable igual que antes |

## 7. Actualizar el Start Command del backend

En Railway: servicio backend → Settings → Deploy → Start Command:

```
sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"
```

(antes: `sh -c 'uvicorn main:app --host 0.0.0.0 --port $PORT'` — ver
`DEPLOY_NOTES.md`). Esto es lo que aplicará `0002`→`0005` automáticamente en
cada arranque a partir de acá; el `stamp 0001` del paso 5 es lo que le
permite arrancar desde el punto correcto la primera vez.

## 8. Deploy

Apuntar el servicio backend (y el frontend) de Railway a la rama
`feature/multi-tenant` — o mergear `feature/multi-tenant` a `main` primero y
dejar el deploy apuntando a `main`, si esa es la rama que Railway ya sigue.
Cualquiera de las dos funciona; lo importante es que el commit desplegado
sea el mismo que se validó en los pasos anteriores.

Disparar el deploy. Observar los Deploy Logs: debe verse `alembic upgrade
head` corriendo `0002`→`0003`→`0004`→`0005` (no `0001` — ya está stampeada) y
después `Uvicorn running on...`.

## 9. Verificación post-deploy

```bash
# Health check
curl -s https://<backend-real>/health
# → {"status":"ok"}

# Tenant resuelve (dev header, mientras no haya subdominio real)
curl -s https://<backend-real>/tenant/config -H "X-Tenant-Slug: elysium"
# → nombre_comercial, features, servicios, horario reales de Elysium

# Login admin real sigue funcionando
curl -s -X POST https://<backend-real>/auth/login -H "X-Tenant-Slug: elysium" \
  -d "username=admin@elysium.com&password=<password real>"
# → JWT con tenant_id de elysium

# Conteos de datos — deben coincidir con los de antes del cutover
curl -s https://<backend-real>/pacientes/ -H "Authorization: Bearer <token>" | jq length
curl -s https://<backend-real>/citas/ -H "Authorization: Bearer <token>" | jq length
```

- [ ] Frontend real carga y el login funciona desde el navegador (confirma que CORS con `ALLOWED_ORIGINS` está bien).
- [ ] Un paciente real puede ver su portal (`/portal`, cédula real).
- [ ] `pytest` corrido contra este ambiente si es posible, o al menos localmente contra el mismo commit antes de desplegar.
- [ ] Revisar logs del backend por cualquier `WARNING`/`ERROR` inesperado en los primeros minutos (jobs de recordatorio/penalización corriendo, ausencia de excepciones de RLS).

## 10. Rollback

Si algo falla entre el paso 5 y el 9:

1. **Antes de tocar datos de nuevo:** revertir el Start Command y la rama de
   deploy de Railway al estado de `main` (ver `DEPLOY_NOTES.md` para los
   valores exactos previos).
2. Si el esquema quedó a medio migrar (falló en medio de `0002`-`0005`):
   restaurar el backup del paso 2 —
   ```bash
   docker run --rm -v "$(pwd):/backup" postgres:18 \
     pg_restore --clean --if-exists -d "<DATABASE_URL pública de Railway>" \
     /backup/elysium_prod_backup_*.dump
   ```
   Alembic corre cada revisión dentro de una transacción, así que un fallo a
   mitad de una revisión individual ya revierte solo esa revisión — pero si
   ya se aplicaron una o más revisiones completas antes del fallo, restaurar
   el dump es la vía segura para volver exactamente al estado pre-cutover.
3. Redesplegar el código de `main` contra la base restaurada.
4. Confirmar `/health`, login y conteos de datos antes de reabrir tráfico.

`0002_multi_tenant_schema` tiene su propio `downgrade()` reversible, pero
**solo mientras Elysium sea el único tenant** (ver la advertencia en el
docstring de esa migración) — no usarlo como plan de rollback una vez haya
un segundo tenant real; a partir de ahí, restaurar backup es el único
camino seguro.

## Notas / referencias

- Detalle completo de RLS, el gotcha del string vacío en la política, `SET
  LOCAL` por transacción, JWT↔tenant: `CLAUDE.md` → "Multi-Tenancy".
- Configuración y URLs reales del primer despliegue (`main`), que este
  cutover reemplaza: `DEPLOY_NOTES.md`.
- El ensayo de migración que validó este mismo procedimiento (dump/restore
  + `alembic stamp 0001 && alembic upgrade head`) contra una copia real de
  producción, en un entorno completamente aislado y desechable: ver
  `CLAUDE.md` → "Current Status" → "Migración de datos de producción
  ensayada".
