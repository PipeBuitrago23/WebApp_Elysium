# Universal constants, not tenant config — deduplicated from where they used
# to be hand-copied verbatim in multiple route files (ventas.py/gastos.py had
# an identical METODOS_PAGO; auth.py/medicos.py an identical password limit).

METODOS_PAGO = {"Efectivo", "Transferencia", "Tarjeta", "Otro"}

# bcrypt's own hard limit — not a business rule.
MAX_PASSWORD_BYTES = 72
