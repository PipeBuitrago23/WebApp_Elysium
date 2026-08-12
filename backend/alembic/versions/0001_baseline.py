"""baseline — current single-tenant schema (pacientes, usuarios, citas, pagos, ventas, gastos)

This revision is a faithful, hand-written snapshot of the schema that
`Base.metadata.create_all()` + the old `_run_migrations()` in main.py already
produced in production. It is never actually executed there: the real
production database is marked as already being on this revision with
`alembic stamp 0001` (this exact revision — NOT `alembic stamp head`; head
now points at the latest revision, e.g. 0005, and stamping head would mark
production as already having every later revision's schema changes applied
without ever actually running them, silently skipping 0002-000N against
real data) — the tables already exist and must not be recreated. It exists
so that (a) a brand-new dev/CI database can be built from nothing with
plain `alembic upgrade head`, and (b) every later revision has a correct
starting point to diff against. See docs/CUTOVER.md for the full cutover
procedure this is a part of.

Revision ID: 0001
Revises:
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pacientes",
        sa.Column("Paciente", sa.String(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("antecedentes", sa.Text(), nullable=True),
        sa.Column("cirugias", sa.Text(), nullable=True),
        sa.Column("habeas_data_aceptado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fecha_aceptacion_habeas", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("es_admin", sa.Boolean(), nullable=True),
        sa.Column("es_medico", sa.Boolean(), nullable=True),
        sa.Column("habeas_data_aceptado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fecha_aceptacion_habeas", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email", name="usuarios_email_key"),
    )

    op.create_table(
        "citas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paciente_id", sa.String(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hora", sa.Time(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False, server_default="programada"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("recordatorio_enviado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("medico_id", sa.String(), nullable=True),
        sa.Column("motivo_remision", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.Paciente"], name="citas_paciente_id_fkey"),
        sa.ForeignKeyConstraint(["medico_id"], ["usuarios.id"], name="citas_medico_id_fkey"),
    )

    op.create_table(
        "pagos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paciente_id", sa.String(), nullable=False),
        sa.Column("tipo_paquete", sa.String(), nullable=False),
        sa.Column("total_sesiones", sa.Integer(), nullable=False),
        sa.Column("sesiones_restantes", sa.Integer(), nullable=False),
        sa.Column("fecha_pago", sa.Date(), nullable=False),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.Paciente"], name="pagos_paciente_id_fkey"),
    )

    op.create_table(
        "ventas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("paciente_id", sa.String(), nullable=False),
        sa.Column("nombre_paquete", sa.String(), nullable=False),
        sa.Column("categoria", sa.String(), nullable=False),
        sa.Column("total_sesiones", sa.Integer(), nullable=True),
        sa.Column("valor_total", sa.Float(), nullable=False),
        sa.Column("abono", sa.Float(), nullable=False),
        sa.Column("saldo", sa.Float(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("metodo_pago", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.Paciente"], name="ventas_paciente_id_fkey"),
    )

    op.create_table(
        "gastos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("nit", sa.String(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("metodo_pago", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("gastos")
    op.drop_table("ventas")
    op.drop_table("pagos")
    op.drop_table("citas")
    op.drop_table("usuarios")
    op.drop_table("pacientes")
