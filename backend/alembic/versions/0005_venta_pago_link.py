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
    # Backfill fecha_inicio from fecha_pago (the pre-rename `fecha`, which was
    # NOT NULL, so every existing row gets a real value — fecha_inicio is the
    # plan's start date and drives fecha_vencimiento in core/planes.py, so the
    # sale date is the right historical value).
    #
    # RLS gotcha (found migrating real production data): this migration may run
    # as a NON-superuser role that owns the tables (app_user), and 0003 put
    # FORCE ROW LEVEL SECURITY on `ventas`, which subjects even the owner to
    # the tenant_isolation policy. A migration sets no `app.tenant_id`, so the
    # policy filters every row out and this UPDATE would touch 0 rows, leaving
    # fecha_inicio NULL and making the SET NOT NULL below fail with
    # "column ... contains null values". Dropping RLS enforcement just for the
    # backfill (restored immediately after) makes it see every row regardless
    # of the running role. A superuser (the DATABASE_URL role Alembic is meant
    # to use) already bypasses RLS, so there this is a harmless no-op.
    op.execute("ALTER TABLE ventas DISABLE ROW LEVEL SECURITY")
    op.execute("UPDATE ventas SET fecha_inicio = fecha_pago WHERE fecha_inicio IS NULL")
    op.execute("ALTER TABLE ventas ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ventas FORCE ROW LEVEL SECURITY")
    op.alter_column("ventas", "fecha_inicio", existing_type=sa.Date(), nullable=False)
    op.alter_column("pagos", "fecha_pago", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    op.alter_column("pagos", "fecha_pago", existing_type=sa.Date(), nullable=False)
    op.drop_column("ventas", "fecha_inicio")
    op.alter_column("ventas", "fecha_pago", existing_type=sa.Date(), nullable=False)
    op.alter_column("ventas", "fecha_pago", new_column_name="fecha")
