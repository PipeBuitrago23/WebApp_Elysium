# Universal constants, not tenant config — deduplicated from where they used
# to be hand-copied verbatim in multiple route files (ventas.py/gastos.py had
# an identical METODOS_PAGO; auth.py/medicos.py an identical password limit).

METODOS_PAGO = {"Efectivo", "Transferencia", "Tarjeta", "Otro"}

# bcrypt's own hard limit — not a business rule.
MAX_PASSWORD_BYTES = 72

# Subdomains reserved for infrastructure — must never resolve to a tenant,
# regardless of what's in the tenants table (e.g. admin.<BASE_DOMAIN> is
# reserved for a future superadmin panel, api.<BASE_DOMAIN> is the bare
# backend host with no tenant of its own). Shared by TenantMiddleware
# (middleware/tenant.py) and crear_tenant.py's slug validation.
RESERVED_SLUGS = {"admin", "api", "www", "app", "mail", "static"}
