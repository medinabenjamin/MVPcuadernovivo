"""
main.py — Aplicación FastAPI: webhook de WhatsApp + flujo completo.

Flujo al recibir un mensaje:
  texto  -> extractor de IA
  audio  -> transcripción -> extractor de IA
  venta    -> guardar en Sheets + confirmación con total del día
  consulta -> calcular datos desde Sheets + respuesta redactada por Claude
  otro     -> respuesta breve explicando qué hace el bot
"""

import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request, Response

from app import ai_extractor, config, scheduler, sheets, transcription, whatsapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al arrancar la app, se inicia el scheduler del resumen diario
    sched = scheduler.iniciar_scheduler()
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="Cuaderno Vivo", lifespan=lifespan)


@app.get("/")
def salud():
    """Endpoint simple para verificar que el servidor está vivo."""
    return {"status": "ok", "app": "Cuaderno Vivo"}


@app.get("/webhook")
def verificar_webhook(request: Request):
    """
    Verificación del webhook que hace Meta UNA vez al configurarlo:
    Meta manda hub.mode, hub.verify_token y hub.challenge.
    Si el token coincide, hay que devolver el challenge tal cual.
    """
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == config.WHATSAPP_VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(content="Token de verificación inválido", status_code=403)


@app.post("/webhook")
async def recibir_mensaje(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe los mensajes entrantes. Respondemos 200 de inmediato y procesamos
    en segundo plano, porque Meta reintenta si tardamos mucho en responder.
    """
    payload = await request.json()
    mensaje = whatsapp.extraer_mensaje(payload)
    if mensaje:
        background_tasks.add_task(procesar_mensaje, mensaje)
    return {"status": "received"}


def procesar_mensaje(mensaje: dict):
    """Lógica principal del bot. Nunca debe lanzar excepciones sin capturar."""
    remitente = mensaje["de"]
    try:
        # --- Paso 1: obtener el texto (transcribiendo si es audio) ---
        if mensaje["tipo"] == "texto":
            texto = mensaje["texto"]
        elif mensaje["tipo"] == "audio":
            try:
                ruta = whatsapp.descargar_audio(mensaje["media_id"])
                texto = transcription.transcribir_audio(ruta)
            except Exception as e:
                logger.error("Fallo transcribiendo audio: %s", e)
                whatsapp.enviar_mensaje_texto(
                    remitente,
                    "No pude escuchar bien tu nota de voz 🙉 ¿Me la mandas de nuevo o por texto?",
                )
                return
            if not texto:
                whatsapp.enviar_mensaje_texto(
                    remitente,
                    "Tu nota de voz llegó vacía o muy cortita. ¿Me la repites?",
                )
                return
        else:
            whatsapp.enviar_mensaje_texto(
                remitente,
                "Por ahora solo entiendo mensajes de texto y notas de voz 📒",
            )
            return

        # --- Paso 2: interpretar con Claude ---
        resultado = ai_extractor.interpretar_mensaje(texto)

        # --- Paso 3: actuar según el tipo ---
        if resultado["tipo"] == "venta":
            try:
                total_venta = sheets.agregar_venta(resultado["datos"], texto)
                resumen = sheets.resumen_del_dia()
                d = resultado["datos"]
                detalle = d["producto"]
                if d.get("variante"):
                    detalle += f" {d['variante']}"
                whatsapp.enviar_mensaje_texto(
                    remitente,
                    f"✅ Anotado: {int(d.get('cantidad', 1))} {detalle} por ${total_venta:,.0f}"
                    + (f" (cliente: {d['cliente']})" if d.get("cliente") else "")
                    + f"\n📦 Llevas ${resumen['total']:,.0f} vendidos hoy en {resumen['num_ventas']} venta(s).",
                )
            except Exception as e:
                logger.error("Fallo guardando en Sheets: %s", e)
                whatsapp.enviar_mensaje_texto(
                    remitente,
                    "Entendí tu venta pero no pude anotarla en el cuaderno 😓 "
                    "Inténtalo de nuevo en un rato, por favor.",
                )

        elif resultado["tipo"] == "consulta":
            try:
                periodo = resultado["periodo"]
                resumen = (
                    sheets.resumen_de_la_semana() if periodo == "semana" else sheets.resumen_del_dia()
                )
                respuesta = ai_extractor.redactar_respuesta_consulta(periodo, resumen)
                whatsapp.enviar_mensaje_texto(remitente, respuesta)
            except Exception as e:
                logger.error("Fallo consultando Sheets: %s", e)
                whatsapp.enviar_mensaje_texto(
                    remitente,
                    "No pude revisar el cuaderno ahora mismo 😓 Inténtalo de nuevo en un rato.",
                )

        else:  # "conversacion" o "error"
            whatsapp.enviar_mensaje_texto(remitente, resultado["respuesta"])

    except Exception as e:
        # Red de seguridad final: nada debe botar el servidor
        logger.exception("Error inesperado procesando mensaje: %s", e)
        whatsapp.enviar_mensaje_texto(
            remitente,
            "Algo salió mal de mi lado 🙏 Tu mensaje no se perdió, inténtalo de nuevo.",
        )
