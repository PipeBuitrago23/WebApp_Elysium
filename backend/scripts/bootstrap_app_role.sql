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
