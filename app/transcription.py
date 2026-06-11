"""
transcription.py — Transcripción de notas de voz con faster-whisper.

Las notas de voz de WhatsApp llegan en formato .ogg (códec opus).
faster-whisper las puede leer directamente, corriendo en CPU.

El modelo se carga UNA sola vez (es lento de cargar) y se reutiliza.
"""

import logging
import os

from faster_whisper import WhisperModel

from app import config

logger = logging.getLogger(__name__)

_modelo: WhisperModel | None = None


def _obtener_modelo() -> WhisperModel:
    """Carga perezosa del modelo (solo la primera vez que se necesita)."""
    global _modelo
    if _modelo is None:
        logger.info("Cargando modelo Whisper '%s' (puede tardar)...", config.WHISPER_MODEL_SIZE)
        _modelo = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",  # más rápido y liviano en CPU
        )
    return _modelo


def transcribir_audio(ruta_archivo: str) -> str:
    """
    Transcribe un archivo de audio a texto en español.
    Devuelve el texto, o lanza una excepción si falla.
    Borra el archivo temporal al terminar.
    """
    try:
        modelo = _obtener_modelo()
        segmentos, _info = modelo.transcribe(ruta_archivo, language="es")
        texto = " ".join(s.text.strip() for s in segmentos).strip()
        logger.info("Transcripción: %s", texto)
        return texto
    finally:
        # Limpieza del archivo temporal descargado
        try:
            os.remove(ruta_archivo)
        except OSError:
            pass
