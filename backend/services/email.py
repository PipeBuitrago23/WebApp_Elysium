import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote

import resend

from models.tenant import Tenant

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL     = os.getenv("RESEND_FROM", "Elysium Fisio-Pilates <onboarding@resend.dev>")

if not RESEND_API_KEY:
    logger.warning(
        "⚠️  RESEND_API_KEY no configurada — "
        "los correos se registrarán en el log pero NO se enviarán."
    )
else:
    resend.api_key = RESEND_API_KEY

# PORTAL_URL is an explicit override — kept for local dev, where BASE_DOMAIN
# isn't wired to a real domain yet, so this is the only way to get a working
# link. Once BASE_DOMAIN is set (Phase 2.4/2.5), each tenant's emails link to
# their own subdomain via _portal_url() below instead of one shared URL.
_PORTAL_URL_OVERRIDE = os.getenv("PORTAL_URL")
BASE_DOMAIN          = os.getenv("BASE_DOMAIN", "")
CLINIC_MAPS_URL      = os.getenv("CLINIC_MAPS_URL", "https://maps.google.com")

_DAYS_ES   = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_DURACION  = {"Pilates": 60, "Fisioterapia": 60, "Sesión de cortesía": 45}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_fecha(d) -> str:
    return f"{_DAYS_ES[d.weekday()]} {d.day} de {_MONTHS_ES[d.month - 1]} de {d.year}"


def _portal_url(tenant_slug: str) -> str:
    """PORTAL_URL wins if set (local dev override). Otherwise, once
    BASE_DOMAIN is configured, each tenant gets its own portal link —
    <slug>.<BASE_DOMAIN>/portal — instead of one shared URL. Falls back to
    localhost so nothing breaks before either is configured."""
    if _PORTAL_URL_OVERRIDE:
        return _PORTAL_URL_OVERRIDE
    if BASE_DOMAIN:
        return f"https://{tenant_slug}.{BASE_DOMAIN}/portal"
    return "http://localhost:3000/portal"


def _brand_color(tenant: Tenant) -> str:
    """tenant.branding.color_primario overrides the buttons/card accent —
    defaults to the zinc-800 already hardcoded everywhere below, so a tenant
    that hasn't configured branding (Elysium included) renders identically
    to before this existed."""
    return (tenant.branding or {}).get("color_primario", "#27272a")


def _google_cal_url(cita, tenant_nombre: str) -> str:
    dt_start = datetime.combine(cita.fecha, cita.hora)
    dt_end   = dt_start + timedelta(minutes=_DURACION.get(cita.tipo, 60))
    fmt      = "%Y%m%dT%H%M%S"
    dates    = f"{dt_start.strftime(fmt)}/{dt_end.strftime(fmt)}"
    text     = quote(f"Cita {cita.tipo} – {tenant_nombre}")
    details  = quote(f"Cita de {cita.tipo} en {tenant_nombre}.")
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={text}&dates={dates}&details={details}"
        f"&location={quote(tenant_nombre)}"
    )


def _plan_block(plan) -> str:
    if not plan:
        return ""
    return f"""
      <div style="background:#f0fdf4;border-radius:12px;padding:20px;margin-bottom:24px;border:1px solid #bbf7d0;">
        <p style="color:#15803d;font-size:12px;font-weight:700;margin:0 0 10px;text-transform:uppercase;letter-spacing:0.5px;">📊 Estado de tu plan</p>
        <p style="color:#166534;font-size:14px;margin:0;line-height:1.9;">
          Esta cita descontará <strong>1 sesión</strong> de tu plan al ser completada.<br>
          Sesiones vigentes: <strong>{plan.sesiones_restantes} de {plan.total_sesiones}</strong><br>
          Plan válido hasta: <strong>{_fmt_fecha(plan.fecha_vencimiento)}</strong>
        </p>
      </div>"""


# ── Base template ─────────────────────────────────────────────────────────────

def _base_template(title: str, content: str, tenant_nombre: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
         style="background-color:#f1f5f9;padding:48px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
               style="max-width:580px;">

          <!-- Header -->
          <tr>
            <td style="background-color:#0f172a;border-radius:16px 16px 0 0;padding:32px;text-align:center;">
              <p style="margin:0;font-size:22px;font-weight:300;color:#ffffff;letter-spacing:6px;text-transform:uppercase;">{tenant_nombre}</p>
              <p style="margin:6px 0 0;font-size:10px;color:#a1a1aa;letter-spacing:3px;text-transform:uppercase;">
                Fisioterapia &amp; Pilates
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background-color:#ffffff;padding:40px 40px 36px;">
              {content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#e2e8f0;border-radius:0 0 16px 16px;padding:24px 40px;text-align:center;">
              <p style="margin:0 0 4px;font-size:12px;color:#94a3b8;font-weight:600;">{tenant_nombre}</p>
              <p style="margin:0;font-size:11px;color:#cbd5e1;">
                Este mensaje fue generado automáticamente. Por favor no respondas a este correo.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ── Confirmation template ─────────────────────────────────────────────────────

def _build_confirmacion_html(nombre: str, cita, plan, tenant: Tenant) -> str:
    hora_fmt  = cita.hora.strftime("%H:%M")
    fecha_fmt = _fmt_fecha(cita.fecha)
    cal_url   = _google_cal_url(cita, tenant.nombre_comercial)
    color     = _brand_color(tenant)
    portal    = _portal_url(tenant.slug)

    content = f"""
      <p style="color:#64748b;font-size:15px;margin:0 0 6px;">
        Hola, <strong style="color:#0f172a;">{nombre}</strong> 👋
      </p>
      <h2 style="color:#0f172a;font-size:22px;font-weight:800;margin:0 0 8px;line-height:1.3;">
        ¡Tu cita está confirmada!
      </h2>
      <p style="color:#64748b;font-size:15px;margin:0 0 32px;">
        Aquí tienes el resumen de tu reserva en {tenant.nombre_comercial}.
      </p>

      <!-- Cita card -->
      <div style="background:linear-gradient(135deg,{color} 0%,#3f3f46 100%);border-radius:16px;padding:28px;margin-bottom:28px;">
        <p style="color:#d4d4d8;font-size:11px;text-transform:uppercase;letter-spacing:2px;font-weight:700;margin:0 0 20px;">
          Detalles de la cita
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Servicio</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{cita.tipo}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Fecha</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{fecha_fmt}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Hora</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{hora_fmt}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Instructor</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">Equipo {tenant.nombre_comercial}</span>
            </td>
          </tr>
        </table>
      </div>

      <!-- Calendar button -->
      <div style="text-align:center;margin-bottom:28px;">
        <a href="{cal_url}"
           style="display:inline-block;background-color:#f8fafc;border:2px solid #e2e8f0;border-radius:12px;padding:13px 28px;font-size:14px;font-weight:600;color:#3f3f46;text-decoration:none;">
          📅 Añadir a Google Calendar
        </a>
      </div>

      {_plan_block(plan)}

      <!-- Logistics -->
      <div style="background:#f8fafc;border-radius:12px;padding:20px;margin-bottom:24px;border-left:4px solid #71717a;">
        <p style="color:#0f172a;font-size:14px;font-weight:700;margin:0 0 12px;">Antes de llegar, recuerda:</p>
        <table cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:4px 0;color:#475569;font-size:14px;vertical-align:top;">👕&nbsp;</td>
            <td style="padding:4px 0;color:#475569;font-size:14px;line-height:1.6;">Ropa cómoda y medias antideslizantes</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#475569;font-size:14px;vertical-align:top;">💧&nbsp;</td>
            <td style="padding:4px 0;color:#475569;font-size:14px;line-height:1.6;">Trae tu botella de agua</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#475569;font-size:14px;vertical-align:top;">⏰&nbsp;</td>
            <td style="padding:4px 0;color:#475569;font-size:14px;line-height:1.6;">Llega 5 minutos antes de tu hora</td>
          </tr>
        </table>
      </div>

      <!-- Maps button -->
      <div style="text-align:center;margin-bottom:28px;">
        <a href="{CLINIC_MAPS_URL}"
           style="display:inline-block;background-color:#f8fafc;border:2px solid #e2e8f0;border-radius:12px;padding:13px 28px;font-size:14px;font-weight:600;color:#475569;text-decoration:none;">
          📍 Cómo llegar
        </a>
      </div>

      <!-- Cancellation policy -->
      <div style="background:#fff7ed;border-radius:12px;padding:16px 20px;margin-bottom:28px;border:1px solid #fed7aa;">
        <p style="color:#92400e;font-size:13px;margin:0;line-height:1.7;">
          ⚠️ <strong>Política de cancelación:</strong> Puedes cancelar o reagendar hasta
          <strong>2 horas antes</strong> de tu cita desde tu portal.
          Cancelaciones tardías o inasistencias descuentan 1 sesión de tu plan.
        </p>
      </div>

      <!-- Portal CTA -->
      <div style="text-align:center;">
        <a href="{portal}"
           style="display:inline-block;background-color:{color};border-radius:12px;padding:16px 40px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
          Ver mi portal
        </a>
      </div>"""

    return _base_template(f"Confirmación de cita – {tenant.nombre_comercial}", content, tenant.nombre_comercial)


# ── Reminder template ─────────────────────────────────────────────────────────

def _build_recordatorio_html(nombre: str, cita, plan, tenant: Tenant) -> str:
    hora_fmt  = cita.hora.strftime("%H:%M")
    fecha_fmt = _fmt_fecha(cita.fecha)
    cal_url   = _google_cal_url(cita, tenant.nombre_comercial)
    color     = _brand_color(tenant)
    portal    = _portal_url(tenant.slug)

    content = f"""
      <p style="color:#64748b;font-size:15px;margin:0 0 6px;">
        Hola, <strong style="color:#0f172a;">{nombre}</strong>
      </p>
      <h2 style="color:#0f172a;font-size:22px;font-weight:800;margin:0 0 8px;line-height:1.3;">
        🔔 Recuerda: mañana tienes una cita
      </h2>
      <p style="color:#64748b;font-size:15px;margin:0 0 32px;">
        Te enviamos este recordatorio 24 horas antes para que te prepares.
      </p>

      <!-- Cita card — reminder -->
      <div style="background:linear-gradient(135deg,{color} 0%,#3f3f46 100%);border-radius:16px;padding:28px;margin-bottom:28px;">
        <p style="color:#d4d4d8;font-size:11px;text-transform:uppercase;letter-spacing:2px;font-weight:700;margin:0 0 20px;">
          Tu cita de mañana
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Servicio</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{cita.tipo}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Fecha</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{fecha_fmt}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Hora</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{hora_fmt}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Instructor</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">Equipo {tenant.nombre_comercial}</span>
            </td>
          </tr>
        </table>
      </div>

      <!-- Calendar button -->
      <div style="text-align:center;margin-bottom:28px;">
        <a href="{cal_url}"
           style="display:inline-block;background-color:#f8fafc;border:2px solid #e2e8f0;border-radius:12px;padding:13px 28px;font-size:14px;font-weight:600;color:#3f3f46;text-decoration:none;">
          📅 Añadir a Google Calendar
        </a>
      </div>

      {_plan_block(plan)}

      <!-- Logistics reminder -->
      <div style="background:#f8fafc;border-radius:12px;padding:20px;margin-bottom:24px;border-left:4px solid #71717a;">
        <p style="color:#0f172a;font-size:14px;font-weight:700;margin:0 0 12px;">Para mañana no olvides:</p>
        <table cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:4px 0;color:#475569;font-size:14px;vertical-align:top;">👕&nbsp;</td>
            <td style="padding:4px 0;color:#475569;font-size:14px;line-height:1.6;">Ropa cómoda y medias antideslizantes</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#475569;font-size:14px;vertical-align:top;">💧&nbsp;</td>
            <td style="padding:4px 0;color:#475569;font-size:14px;line-height:1.6;">Botella de agua</td>
          </tr>
          <tr>
            <td style="padding:4px 0;color:#475569;font-size:14px;vertical-align:top;">⏰&nbsp;</td>
            <td style="padding:4px 0;color:#475569;font-size:14px;line-height:1.6;">Llega 5 minutos antes</td>
          </tr>
        </table>
      </div>

      <!-- Maps -->
      <div style="text-align:center;margin-bottom:28px;">
        <a href="{CLINIC_MAPS_URL}"
           style="display:inline-block;background-color:#f8fafc;border:2px solid #e2e8f0;border-radius:12px;padding:13px 28px;font-size:14px;font-weight:600;color:#475569;text-decoration:none;">
          📍 Cómo llegar
        </a>
      </div>

      <!-- Cancellation warning — more urgent for reminder -->
      <div style="background:#fef2f2;border-radius:12px;padding:16px 20px;margin-bottom:28px;border:1px solid #fecaca;">
        <p style="color:#991b1b;font-size:13px;margin:0;line-height:1.7;">
          🚨 <strong>¿No puedes asistir?</strong> Solo puedes cancelar hasta
          <strong>2 horas antes</strong> de tu cita.
          Después de esa hora, o si no asistes, se descontará 1 sesión de tu plan.
        </p>
      </div>

      <!-- Portal CTA -->
      <div style="text-align:center;">
        <a href="{portal}"
           style="display:inline-block;background-color:{color};border-radius:12px;padding:16px 40px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
          Gestionar mi cita
        </a>
      </div>"""

    return _base_template(f"Recordatorio de cita – {tenant.nombre_comercial}", content, tenant.nombre_comercial)


# ── Public API ────────────────────────────────────────────────────────────────

def _send(to_email: str, subject: str, html: str) -> None:
    if not RESEND_API_KEY:
        logger.warning(
            "📧 [EMAIL - modo log | RESEND_API_KEY no configurada]\n  Para: %s\n  Asunto: %s",
            to_email, subject,
        )
        return

    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html,
        })
        logger.info("📧 Email enviado a %s — %s", to_email, subject)
    except Exception as exc:
        logger.error("📧 Error Resend enviando a %s: %s", to_email, exc)
        raise


def _build_pago_html(nombre: str, venta, vigencia_dias: int, tenant: Tenant) -> str:
    _MONTHS = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    _DAYS   = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    color   = _brand_color(tenant)
    portal  = _portal_url(tenant.slug)
    if venta.fecha_pago:
        fecha_fmt = f"{_DAYS[venta.fecha_pago.weekday()]} {venta.fecha_pago.day} de {_MONTHS[venta.fecha_pago.month-1]} de {venta.fecha_pago.year}"
    else:
        fecha_fmt = "Pendiente de pago"

    def cop(v):
        return f"${v:,.0f}".replace(",", ".")

    sesiones_row = ""
    vencimiento_row = ""
    vencimiento_block = ""
    if venta.total_sesiones:
        venc = venta.fecha_inicio + timedelta(days=vigencia_dias)
        venc_fmt = f"{_DAYS[venc.weekday()]} {venc.day} de {_MONTHS[venc.month-1]} de {venc.year}"
        sesiones_row = f"""
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Sesiones incluidas</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{venta.total_sesiones}</span>
            </td>
          </tr>"""
        vencimiento_row = f"""
          <tr>
            <td style="padding:10px 0;">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Plan válido hasta</span>
              <span style="color:#facc15;font-size:16px;font-weight:700;">{venc_fmt}</span>
            </td>
          </tr>"""
        vencimiento_block = f"""
      <div style="background:#f0fdf4;border-radius:12px;padding:20px;margin-bottom:28px;border:1px solid #bbf7d0;">
        <p style="color:#15803d;font-size:12px;font-weight:700;margin:0 0 10px;text-transform:uppercase;letter-spacing:0.5px;">📅 Vigencia del plan</p>
        <p style="color:#166534;font-size:14px;margin:0;line-height:1.9;">
          Tienes <strong>{vigencia_dias} días</strong> para usar todas tus sesiones.<br>
          Tu plan vence el <strong>{venc_fmt}</strong>.<br>
          Pasada esta fecha, las sesiones no utilizadas no podrán recuperarse.
        </p>
      </div>"""

    saldo_color = "#ef4444" if venta.saldo > 0 else "#22c55e"
    saldo_label = "Saldo pendiente" if venta.saldo > 0 else "Saldo"
    estado_badge = (
        '<span style="background:#fef2f2;color:#991b1b;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">⚠️ Pendiente de pago</span>'
        if venta.saldo > 0 else
        '<span style="background:#f0fdf4;color:#166534;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;">✅ Pagado en su totalidad</span>'
    )

    content = f"""
      <p style="color:#64748b;font-size:15px;margin:0 0 6px;">
        Hola, <strong style="color:#0f172a;">{nombre}</strong> 👋
      </p>
      <h2 style="color:#0f172a;font-size:22px;font-weight:800;margin:0 0 8px;line-height:1.3;">
        Confirmación de pago
      </h2>
      <p style="color:#64748b;font-size:15px;margin:0 0 32px;">
        Hemos registrado tu pago en {tenant.nombre_comercial}. Aquí tienes el resumen.
      </p>

      <div style="background:linear-gradient(135deg,{color} 0%,#3f3f46 100%);border-radius:16px;padding:28px;margin-bottom:28px;">
        <p style="color:#d4d4d8;font-size:11px;text-transform:uppercase;letter-spacing:2px;font-weight:700;margin:0 0 20px;">
          Detalle del pago
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Paquete</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{venta.nombre_paquete}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Fecha</span>
              <span style="color:#ffffff;font-size:16px;font-weight:600;">{fecha_fmt}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Valor total</span>
              <span style="color:#ffffff;font-size:18px;font-weight:700;">{cop(venta.valor_total)}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Abono recibido</span>
              <span style="color:#4ade80;font-size:18px;font-weight:700;">{cop(venta.abono)}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.15);">
              <span style="color:#d4d4d8;font-size:11px;display:block;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">{saldo_label}</span>
              <span style="color:{saldo_color};font-size:18px;font-weight:700;">{cop(venta.saldo)}</span>
            </td>
          </tr>
          {sesiones_row}
          {vencimiento_row}
        </table>
      </div>

      {vencimiento_block}

      <div style="text-align:center;margin-bottom:28px;">
        {estado_badge}
      </div>

      {"" if venta.saldo == 0 else f'''<div style="background:#fff7ed;border-radius:12px;padding:16px 20px;margin-bottom:28px;border:1px solid #fed7aa;"><p style="color:#92400e;font-size:13px;margin:0;line-height:1.7;">⚠️ <strong>Recuerda:</strong> Tienes un saldo pendiente de <strong>{cop(venta.saldo)}</strong>. Por favor comunícate con {tenant.nombre_comercial} para completar tu pago.</p></div>'''}

      <div style="text-align:center;">
        <a href="{portal}"
           style="display:inline-block;background-color:{color};border-radius:12px;padding:16px 40px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
          Ver mi portal
        </a>
      </div>"""

    return _base_template(f"Confirmación de pago – {tenant.nombre_comercial}", content, tenant.nombre_comercial)


def send_confirmacion_pago(nombre: str, email: str, venta, tenant: Tenant, vigencia_dias: int) -> None:
    try:
        html = _build_pago_html(nombre, venta, vigencia_dias, tenant)
        _send(email, f"✅ Confirmación de pago – {venta.nombre_paquete}", html)
    except Exception:
        logger.exception("Error enviando confirmación de pago a %s", email)


def send_confirmacion(nombre: str, email: str, cita, tenant: Tenant, plan=None) -> None:
    try:
        html = _build_confirmacion_html(nombre, cita, plan, tenant)
        _send(email, f"✅ Cita confirmada – {cita.tipo} el {_fmt_fecha(cita.fecha)}", html)
    except Exception:
        logger.exception("Error enviando confirmación a %s", email)


def send_recordatorio(nombre: str, email: str, cita, tenant: Tenant, plan=None) -> None:
    try:
        html = _build_recordatorio_html(nombre, cita, plan, tenant)
        _send(email, f"🔔 Recordatorio: mañana tienes {cita.tipo} a las {cita.hora.strftime('%H:%M')}", html)
    except Exception:
        logger.exception("Error enviando recordatorio a %s", email)
