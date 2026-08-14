"""ventas.fecha_inicio + nullable fecha_pago on ventas/pagos — let a Venta create a linked Pago

Ventas and Pagos were fully independent records: an admin had to enter the
same package twice (once in Pacientes to create the Pago session-plan, once
in Ventas to record the money). To let create_venta create the linked
Pago(s) directly, Venta needs the same fecha_inicio/fecha_pago split Pago
already has (see 0004), and both fecha_pago columns need to become nullable
since a "pendiente" venta (nothing paid yet) has no payment date at all.

`ventas.fecha` (payment date, previously NOT NULL) is renamed to
`fecha_pago` for consistency with `pagos.fecha_pago`, then relaxed to
nullable. `fecha_inicio` is backfilled from the existing `fecha_pago` value
(pre-rename this was every row's `fecha`, always populated) so historical
ventas keep an accurate fecha_inicio instead of an arbitrary default.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("ventas", "fecha", new_column_name="fecha_pago")
    op.alter_column("ventas", "fecha_pago", existing_type=sa.Date(), nullable=True)
    op.add_column("ventas", sa.Column("fecha_inicio", sa.Date(), nullable=True))
    op.execute("UPDATE ventas SET fecha_inicio = fecha_pago WHERE fecha_inicio IS NULL")
    op.alter_column("ventas", "fecha_inicio", existing_type=sa.Date(), nullable=False)
    op.alter_column("pagos", "fecha_pago", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.alter_column("pagos", "fecha_pago", existing_type=sa.Date(), nullable=False)
    op.drop_column("ventas", "fecha_inicio")
    op.alter_column("ventas", "fecha_pago", existing_type=sa.Date(), nullable=False)
    op.alter_column("ventas", "fecha_pago", new_column_name="fecha")
