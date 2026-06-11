"""
scheduler.py — Resumen diario automático a las 20:00 (hora de Chile).

Usa APScheduler en segundo plano dentro del mismo proceso de FastAPI.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import config, sheets, whatsapp

logger = logging.getLogger(__name__)


def enviar_resumen_diario():
    """Calcula el resumen del día y lo envía por WhatsApp a la dueña."""
    if not config.OWNER_PHONE_NUMBER:
        logger.warning("OWNER_PHONE_NUMBER no configurado: no se envía resumen diario.")
        return

    try:
        resumen = sheets.resumen_del_dia()
    except Exception as e:
        logger.error("Error leyendo Sheets para el resumen diario: %s", e)
        return

    if resumen["num_ventas"] == 0:
        mensaje = "📒 Resumen de hoy: no se registraron ventas. ¡Mañana será mejor! 💪"
    else:
        top = "\n".join(
            f"  {i+1}. {nombre} ({int(cant)} unid.)"
            for i, (nombre, cant) in enumerate(resumen["productos_top"])
        )
        mensaje = (
            "📒 *Resumen del día*\n"
            f"💰 Total vendido: ${resumen['total']:,.0f}\n"
            f"🧾 Ventas: {resumen['num_ventas']}\n"
            f"⭐ Top productos:\n{top}"
        )

    whatsapp.enviar_mensaje_texto(config.OWNER_PHONE_NUMBER, mensaje)
    logger.info("Resumen diario enviado.")


def iniciar_scheduler() -> BackgroundScheduler:
    """Crea y arranca el scheduler con la tarea de las 20:00 (America/Santiago)."""
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        enviar_resumen_diario,
        CronTrigger(hour=20, minute=0, timezone=config.TIMEZONE),
        id="resumen_diario",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado: resumen diario a las 20:00 (%s).", config.TIMEZONE)
    return scheduler
