"""
whatsapp.py — Envío y recepción de mensajes con WhatsApp Cloud API (Meta).

Funciones principales:
- enviar_mensaje_texto: responde al usuario por WhatsApp.
- descargar_audio: baja una nota de voz desde los servidores de Meta.
- extraer_mensaje: parsea el payload del webhook y devuelve algo simple.
"""

import logging
import tempfile

import httpx

from app import config

logger = logging.getLogger(__name__)

API_BASE = "https://graph.facebook.com/v21.0"
HEADERS_AUTH = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}


def enviar_mensaje_texto(numero_destino: str, texto: str) -> bool:
    """
    Envía un mensaje de texto simple a un número de WhatsApp.

    numero_destino: número con código de país, sin "+" (ej: "56912345678").
    Devuelve True si Meta aceptó el mensaje.
    """
    url = f"{API_BASE}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto},
    }
    try:
        respuesta = httpx.post(url, json=payload, headers=HEADERS_AUTH, timeout=15)
        respuesta.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.error("Error enviando mensaje de WhatsApp: %s", e)
        return False


def descargar_audio(media_id: str) -> str:
    """
    Descarga un archivo de audio (nota de voz) desde la API de WhatsApp.

    Proceso en 2 pasos (así funciona la Cloud API):
    1. Con el media_id se pide la URL temporal del archivo.
    2. Se descarga el archivo desde esa URL (requiere el mismo token).

    Devuelve la ruta a un archivo temporal .ogg en disco.
    """
    # Paso 1: obtener la URL del archivo
    info = httpx.get(f"{API_BASE}/{media_id}", headers=HEADERS_AUTH, timeout=15)
    info.raise_for_status()
    media_url = info.json()["url"]

    # Paso 2: descargar el contenido binario
    audio = httpx.get(media_url, headers=HEADERS_AUTH, timeout=60)
    audio.raise_for_status()

    # Guardar en un archivo temporal .ogg (formato de las notas de voz)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio.content)
        return f.name


def extraer_mensaje(payload: dict) -> dict | None:
    """
    Toma el JSON crudo que envía Meta al webhook y devuelve un dict simple:
        {"de": "56912345678", "tipo": "texto"|"audio", "texto": ..., "media_id": ...}

    Devuelve None si el payload no contiene un mensaje (ej: es una
    notificación de estado "delivered"/"read", que también llegan al webhook).
    """
    try:
        entry = payload["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return None  # notificación de estado, no un mensaje

        mensaje = entry["messages"][0]
        remitente = mensaje["from"]
        tipo = mensaje["type"]

        if tipo == "text":
            return {"de": remitente, "tipo": "texto", "texto": mensaje["text"]["body"]}
        if tipo == "audio":
            return {"de": remitente, "tipo": "audio", "media_id": mensaje["audio"]["id"]}

        # Otros tipos (imagen, sticker, etc.) no se soportan en el MVP
        return {"de": remitente, "tipo": "otro"}
    except (KeyError, IndexError):
        logger.warning("Payload de webhook con formato inesperado")
        return None
