from fastapi import HTTPException, Request

from models.tenant import Tenant

# Which routers/capabilities each plan tier includes. "basico" gets the
# core scheduling flow; "completo" adds the financial module and the
# médicos-en-convenio module on top of it.
PLAN_FEATURES: dict[str, set[str]] = {
    "basico": {"citas", "pacientes", "pagos", "portal", "auth"},
    "completo": {
        "citas", "pacientes", "pagos", "portal", "auth",
        "ventas", "gastos", "medicos", "medico_portal", "dashboard_metrics",
    },
}


def features_efectivas(tenant: Tenant) -> set[str]:
    """The tenant's plan features, adjusted by features_override (per-tenant
    exceptions to the plan default — e.g. a "basico" tenant piloting "ventas")."""
    base = set(PLAN_FEATURES.get(tenant.plan, PLAN_FEATURES["basico"]))
    overrides = tenant.features_override or {}
    base |= set(overrides.get("habilitadas", []))
    base -= set(overrides.get("deshabilitadas", []))
    return base


def require_feature(nombre: str):
    """Dependency factory for gating an entire router by feature — use as
    `dependencies=[Depends(require_feature("ventas"))]` on `include_router`.
    Reads request.state.tenant (set by TenantMiddleware), so it works
    independently of whether the caller is authenticated."""

    def _dep(request: Request) -> None:
        if nombre not in features_efectivas(request.state.tenant):
            raise HTTPException(status_code=403, detail="Esta función no está disponible en tu plan.")

    return _dep
