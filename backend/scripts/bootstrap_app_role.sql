-- Bootstraps the non-superuser Postgres role the running backend connects as
-- at runtime (APP_DATABASE_URL). Row-Level Security (alembic revision 0003)
-- has no effect on a superuser or on the table owner — `admin` is a
-- superuser in docker-compose today, so migrations/manual admin queries keep
-- working through `DATABASE_URL`, but the app itself must connect as this
-- separate role for the tenant_isolation policy to actually restrict rows.
--
-- Deliberately NOT an Alembic migration: CREATE ROLE is cluster-wide (not
-- per-database — running this twice against two databases on the same
-- cluster would collide without the guard below) and needs a real secret
-- per environment that must never live in a version-controlled migration.
--
-- Run ONCE per environment/database:
--
--   Local (docker-compose):
--     docker compose exec -T db psql -U admin -d elysium_agenda < backend/scripts/bootstrap_app_role.sql
--
--   Railway: open the Postgres plugin's console (or `railway connect postgres`),
--     replace CHANGE_ME below with a real generated secret for that
--     environment, paste this in, then set APP_DATABASE_URL on the backend
--     service to postgresql://app_user:<that secret>@<host>:<port>/<db>.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH
            LOGIN
            PASSWORD 'CHANGE_ME'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE elysium_agenda TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;

-- tenants has no RLS (it's how a tenant gets resolved in the first place) —
-- app_user only ever needs to read it, never write.
GRANT SELECT ON tenants TO app_user;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON pacientes, usuarios, citas, pagos, ventas, gastos, servicios
    TO app_user;

-- No sequence grants needed: every PK here is either an app-side uuid4() or
-- gen_random_uuid() (a pg_catalog function, executable by `public` by
-- default) — nothing in this schema uses serial/identity columns.

-- Covers tables a *future* Alembic migration adds (e.g. a new tenant-scoped
-- table) so a schema change doesn't silently 403 the app at runtime until
-- someone remembers to re-run this script and update the GRANT list above.
-- Applies only to tables CREATED FROM NOW ON by whichever role executes this
-- statement (the migration/table-owner role — `admin` locally, the Postgres
-- plugin's owner role on Railway) — it does not retroactively grant on
-- tables that already exist, which the explicit GRANT above already covers.
-- Idempotent like every GRANT-family statement: safe to run twice. Assumes
-- a future table follows the same tenant-scoped CRUD pattern as the 7
-- above, not the `tenants` table's SELECT-only exception — if a future
-- migration adds another table like `tenants`, revisit this.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;

-- Belt-and-braces: ON TABLES above does NOT cover a serial/identity column's
-- backing sequence. Nothing in this schema uses one today (see the comment
-- above), but if a future migration does, app_user would otherwise get a
-- silent "permission denied for sequence ..." at runtime despite this
-- script having already run — cheap to grant up front instead of waiting
-- to discover it that way.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
