import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

logger = logging.getLogger(__name__)

SMTP_USER     = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

PORTAL_URL      = os.getenv("PORTAL_URL", "http://localhost:3000/portal")
CLINIC_MAPS_URL = os.getenv("CLINIC_MAPS_URL", "https://maps.google.com")

_DAYS_ES   = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_DURACION  = {"Pilates": 60, "Fisioterapia": 60, "Sesión de cortesía": 45}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_fecha(d) -> str:
    return f"{_DAYS_ES[d.weekday()]} {d.day} de {_MONTHS_ES[d.month - 1]} de {d.year}"


def _google_cal_url(cita) -> str:
    dt_start = datetime.combine(cita.fecha, cita.hora)
    dt_end   = dt_start + timedelta(minutes=_DURACION.get(cita.tipo, 60))
    fmt      = "%Y%m%dT%H%M%S"
    dates    = f"{dt_start.strftime(fmt)}/{dt_end.strftime(fmt)}"
    text     = quote(f"Cita {cita.tipo} – Elysium Fisio-Pilates")
    details  = quote(f"Cita de {cita.tipo} en Elysium Fisio-Pilates.")
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={text}&dates={dates}&details={details}"
        f"&location={quote('Elysium Fisio-Pilates')}"
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

def _base_template(title: str, content: str) -> str:
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
              <p style="margin:0;font-size:22px;font-weight:300;color:#ffffff;letter-spacing:6px;text-transform:uppercase;">Elysium</p>
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
              <p style="margin:0 0 4px;font-size:12px;color:#94a3b8;font-weight:600;">Elysium Fisio-Pilates</p>
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

def _build_confirmacion_html(nombre: str, cita, plan) -> str:
    hora_fmt  = cita.hora.strftime("%H:%M")
    fecha_fmt = _fmt_fecha(cita.fecha)
    cal_url   = _google_cal_url(cita)

    content = f"""
      <p style="color:#64748b;font-size:15px;margin:0 0 6px;">
        Hola, <strong style="color:#0f172a;">{nombre}</strong> 👋
      </p>
      <h2 style="color:#0f172a;font-size:22px;font-weight:800;margin:0 0 8px;line-height:1.3;">
        ¡Tu cita está confirmada!
      </h2>
      <p style="color:#64748b;font-size:15px;margin:0 0 32px;">
        Aquí tienes el resumen de tu reserva en Elysium.
      </p>

      <!-- Cita card -->
      <div style="background:linear-gradient(135deg,#27272a 0%,#3f3f46 100%);border-radius:16px;padding:28px;margin-bottom:28px;">
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
              <span style="color:#ffffff;font-size:18px;font-weight:700;">Equipo Elysium</span>
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
        <a href="{PORTAL_URL}"
           style="display:inline-block;background-color:#27272a;border-radius:12px;padding:16px 40px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
          Ver mi portal
        </a>
      </div>"""

    return _base_template("Confirmación de cita – Elysium", content)


# ── Reminder template ─────────────────────────────────────────────────────────

def _build_recordatorio_html(nombre: str, cita, plan) -> str:
    hora_fmt  = cita.hora.strftime("%H:%M")
    fecha_fmt = _fmt_fecha(cita.fecha)
    cal_url   = _google_cal_url(cita)

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
      <div style="background:linear-gradient(135deg,#27272a 0%,#3f3f46 100%);border-radius:16px;padding:28px;margin-bottom:28px;">
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
              <span style="color:#ffffff;font-size:18px;font-weight:700;">Equipo Elysium</span>
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
        <a href="{PORTAL_URL}"
           style="display:inline-block;background-color:#27272a;border-radius:12px;padding:16px 40px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
          Gestionar mi cita
        </a>
      </div>"""

    return _base_template("Recordatorio de cita – Elysium", content)


# ── Public API ────────────────────────────────────────────────────────────────

def _send(to_email: str, subject: str, html: str) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.info(
            "📧 [EMAIL - modo log]\n  Para: %s\n  Asunto: %s\n\n%s\n",
            to_email, subject, html,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Elysium Fisio-Pilates <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())


def send_confirmacion(nombre: str, email: str, cita, plan=None) -> None:
    try:
        html = _build_confirmacion_html(nombre, cita, plan)
        _send(email, f"✅ Cita confirmada – {cita.tipo} el {_fmt_fecha(cita.fecha)}", html)
    except Exception:
        logger.exception("Error enviando confirmación a %s", email)


def send_recordatorio(nombre: str, email: str, cita, plan=None) -> None:
    try:
        html = _build_recordatorio_html(nombre, cita, plan)
        _send(email, f"🔔 Recordatorio: mañana tienes {cita.tipo} a las {cita.hora.strftime('%H:%M')}", html)
    except Exception:
        logger.exception("Error enviando recordatorio a %s", email)
