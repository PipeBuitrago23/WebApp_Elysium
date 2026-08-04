"""
Demo seed script — wipes all patient/appointment/payment data and inserts 3 fictional
patients with plans and upcoming appointments.

Usage (run from the backend folder with the correct DATABASE_URL set):
    python seed_demo.py
"""

import os
import sys
import uuid
from datetime import date, time, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL env var not set.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

print("🗑️  Borrando datos reales...")
db.execute(text("DELETE FROM citas"))
db.execute(text("DELETE FROM pagos"))
# ventas and gastos reference patients indirectly — clear them too
db.execute(text("DELETE FROM ventas"))
db.execute(text("DELETE FROM gastos"))
db.execute(text("DELETE FROM pacientes"))
db.commit()
print("✅ Tablas limpiadas.")

# ── 3 Demo patients ───────────────────────────────────────────────────────────

today = date.today()

pacientes = [
    {
        "cedula": "1000000001",
        "nombre": "Laura Martínez Ruiz",
        "telefono": "3001234567",
        "email": "laura.demo@example.com",
        "antecedentes": "Lumbalgia crónica leve.",
    },
    {
        "cedula": "1000000002",
        "nombre": "Carlos Herrera Gómez",
        "telefono": "3109876543",
        "email": "carlos.demo@example.com",
        "antecedentes": None,
    },
    {
        "cedula": "1000000003",
        "nombre": "Sofía Ramírez Torres",
        "telefono": "3157654321",
        "email": "sofia.demo@example.com",
        "antecedentes": "Rehabilitación post-operatoria rodilla izquierda.",
    },
]

print("👤 Insertando pacientes demo...")
for p in pacientes:
    db.execute(text("""
        INSERT INTO pacientes (
            "Paciente", nombre, telefono, email, antecedentes,
            habeas_data_aceptado, fecha_aceptacion_habeas
        ) VALUES (
            :cedula, :nombre, :telefono, :email, :antecedentes,
            true, NOW()
        )
    """), {
        "cedula": p["cedula"],
        "nombre": p["nombre"],
        "telefono": p["telefono"],
        "email": p["email"],
        "antecedentes": p["antecedentes"],
    })

db.commit()

# ── Pagos (plans) ─────────────────────────────────────────────────────────────

print("💳 Insertando planes demo...")
planes = [
    # Laura — Pilates 10 sesiones, 4 usadas
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000001",
        "tipo_paquete": "Pilates",
        "total_sesiones": 10,
        "sesiones_restantes": 6,
        "fecha_pago": today - timedelta(days=10),
        "fecha_vencimiento": today + timedelta(days=35),
        "monto": 350000,
        "saldo": 0,
    },
    # Carlos — Fisioterapia 8 sesiones, recién comprado
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000002",
        "tipo_paquete": "Fisioterapia",
        "total_sesiones": 8,
        "sesiones_restantes": 8,
        "fecha_pago": today - timedelta(days=2),
        "fecha_vencimiento": today + timedelta(days=43),
        "monto": 480000,
        "saldo": 0,
    },
    # Sofía — Pilates 5 sesiones, saldo pendiente
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000003",
        "tipo_paquete": "Pilates",
        "total_sesiones": 5,
        "sesiones_restantes": 4,
        "fecha_pago": today - timedelta(days=5),
        "fecha_vencimiento": today + timedelta(days=40),
        "monto": 180000,
        "saldo": 60000,
    },
]

for plan in planes:
    db.execute(text("""
        INSERT INTO pagos (
            id, paciente_id, tipo_paquete, total_sesiones, sesiones_restantes,
            fecha_pago, fecha_vencimiento, monto, saldo
        ) VALUES (
            :id, :paciente_id, :tipo_paquete, :total_sesiones, :sesiones_restantes,
            :fecha_pago, :fecha_vencimiento, :monto, :saldo
        )
    """), plan)

db.commit()

# ── Citas próximas ────────────────────────────────────────────────────────────

print("📅 Insertando citas demo...")

# Next Monday
next_monday = today + timedelta(days=(7 - today.weekday()))

citas = [
    # Laura — 2 citas Pilates próximas semana
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000001",
        "fecha": next_monday,
        "hora": time(8, 0),
        "tipo": "Pilates",
        "estado": "programada",
    },
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000001",
        "fecha": next_monday + timedelta(days=3),
        "hora": time(9, 0),
        "tipo": "Pilates",
        "estado": "confirmada",
    },
    # Carlos — 1 cita Fisioterapia esta semana
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000002",
        "fecha": today + timedelta(days=2),
        "hora": time(14, 0),
        "tipo": "Fisioterapia",
        "estado": "programada",
    },
    # Sofía — 1 cita Pilates próxima semana
    {
        "id": str(uuid.uuid4()),
        "paciente_id": "1000000003",
        "fecha": next_monday + timedelta(days=1),
        "hora": time(10, 0),
        "tipo": "Pilates",
        "estado": "programada",
    },
]

for c in citas:
    db.execute(text("""
        INSERT INTO citas (
            id, paciente_id, fecha, hora, tipo, estado, recordatorio_enviado
        ) VALUES (
            :id, :paciente_id, :fecha, :hora, :tipo, :estado, false
        )
    """), {**c, "hora": c["hora"].strftime("%H:%M:%S")})

db.commit()
db.close()

print("\n✅ Seed demo completado.")
print("   Pacientes: Laura Martínez · Carlos Herrera · Sofía Ramírez")
print("   Cada uno con plan activo y citas próximas.")
