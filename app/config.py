"""
config.py — Carga de variables de entorno.

Todas las claves y credenciales se leen desde un archivo .env
(que NUNCA debe subirse a git). Ver .env.example para saber
qué valores se necesitan y dónde obtenerlos.
"""

import os
from dotenv import load_dotenv

# Carga el archivo .env de la raíz del proyecto
load_dotenv()


def _requerida(nombre: str) -> str:
    """Obtiene una variable de entorno obligatoria o lanza un error claro."""
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno '{nombre}'. "
            f"Copia .env.example a .env y completa los valores."
        )
    return valor


# --- Claude (Anthropic) ---
ANTHROPIC_API_KEY = _requerida("ANTHROPIC_API_KEY")

# --- WhatsApp Cloud API (Meta) ---
WHATSAPP_TOKEN = _requerida("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = _requerida("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = _requerida("WHATSAPP_VERIFY_TOKEN")

# --- Google Sheets ---
# Puede ser la RUTA a un archivo JSON de credenciales, o el JSON completo como texto.
GOOGLE_SHEETS_CREDENTIALS_JSON = _requerida("GOOGLE_SHEETS_CREDENTIALS_JSON")
GOOGLE_SHEET_ID = _requerida("GOOGLE_SHEET_ID")

# --- Opcionales con valores por defecto ---
# Número de WhatsApp de la dueña (con código de país, sin +), para el resumen diario.
OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "")

# Zona horaria para el resumen diario
TIMEZONE = os.getenv("TIMEZONE", "America/Santiago")

# Modelo de Claude a usar
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# Tamaño del modelo de Whisper ("base" o "small" recomendados para CPU)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
