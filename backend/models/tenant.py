from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text
from database import Base

# Defaults every tenant.config is merged over — a new tenant only needs to
# set the keys it wants to override, not the full structure.
DEFAULT_CONFIG = {
    "vigencia_plan_dias": 45,
    "ventana_cancelacion_horas": 2,
    "horario": {
        # Two fixed blocks (not one hora_inicio/hora_fin range) so the
        # midday gap (11:30-13:30 today) can be represented — see CLAUDE.md.
        "bloques": [
            {"inicio": "07:00", "fin": "11:00"},
            {"inicio": "14:00", "fin": "18:00"},
        ],
        "intervalo_min": 30,
        "dias_activos": [1, 2, 3, 4, 5, 6],
    },
    "sesion_cortesia": {
        "habilitada": True,
        "duracion_min": 45,
        "max_por_paciente": 1,
    },
}


def _merge(base: dict, override: dict) -> dict:
    """Deep-merge override onto base without mutating either input."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    slug = Column(String, unique=True, nullable=False)
    nombre_comercial = Column(String, nullable=False)
    plan = Column(String, nullable=False)
    estado = Column(String, nullable=False)
    custom_domain = Column(String, unique=True, nullable=True)
    timezone = Column(String, nullable=False, default="America/Bogota", server_default="America/Bogota")
    branding = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    config = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    features_override = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))

    def get_config(self, ruta: str, default=None):
        """Read a dotted path (e.g. 'horario.intervalo_min') from self.config,
        merged over DEFAULT_CONFIG so tenants never need to set the full JSON."""
        merged = _merge(DEFAULT_CONFIG, self.config or {})
        node = merged
        for part in ruta.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node
