"""
ai_extractor.py — Interpretación de mensajes con Claude (tool use).

Claude recibe el mensaje informal de la dueña y decide:
- Si es una VENTA -> llama a la tool "registrar_venta" con datos estructurados.
- Si es una PREGUNTA sobre ventas -> llama a la tool "consultar_ventas".
- Si no es ninguna de las dos -> responde con texto conversacional.
"""

import logging

from anthropic import Anthropic

from app import config

logger = logging.getLogger(__name__)

cliente_anthropic = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# ------------------------------------------------------------------
# Definición de tools (function calling)
# ------------------------------------------------------------------

TOOL_REGISTRAR_VENTA = {
    "name": "registrar_venta",
    "description": (
        "Registra una venta que la dueña reporta por mensaje. Usar SOLO cuando "
        "el mensaje describe claramente una venta realizada (producto y precio)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "producto": {"type": "string", "description": "Nombre del producto vendido, ej: 'vestido', 'polera'"},
            "variante": {"type": "string", "description": "Talla, color u otra variante. Opcional. Ej: 'S', 'rojo M'"},
            "cantidad": {"type": "number", "description": "Cantidad vendida. Si no se menciona, usar 1.", "default": 1},
            "precio_unitario": {"type": "number", "description": "Precio por unidad en pesos chilenos. 'lucas'/'luca' = miles: 15 lucas = 15000."},
            "cliente": {"type": "string", "description": "Nombre del cliente si se menciona. Opcional."},
        },
        "required": ["producto", "precio_unitario"],
    },
}

TOOL_CONSULTAR_VENTAS = {
    "name": "consultar_ventas",
    "description": (
        "Usar cuando la dueña hace una PREGUNTA sobre sus ventas, "
        "ej: '¿cuánto vendí hoy?', '¿qué se vendió más esta semana?'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "periodo": {
                "type": "string",
                "enum": ["hoy", "semana"],
                "description": "Período por el que pregunta. Si dice 'hoy' o no especifica, usar 'hoy'.",
            },
        },
        "required": ["periodo"],
    },
}

PROMPT_SISTEMA = """Eres el asistente de "Cuaderno Vivo", un sistema que registra las ventas de NewenDomo, \
una pyme chilena de confecciones. La dueña te escribe por WhatsApp en español chileno informal.

Reglas:
- Si el mensaje describe una venta (producto + precio), llama a la tool registrar_venta.
- "lucas" o "luca" significa MILES de pesos chilenos: "15 lucas" = 15000, "una luca" = 1000. \
"15 mil" = 15000. Si dice un número grande directo (ej. 15000), úsalo tal cual.
- Tallas suelen abreviarse: S, M, L, XL, "talla m", etc.
- Si pregunta por sus ventas (cuánto vendió, qué se vendió más), llama a consultar_ventas.
- Si es un saludo, agradecimiento o algo que no es venta ni pregunta de ventas, \
responde brevemente con texto, de forma amable y simple, sin tecnicismos."""


def interpretar_mensaje(texto: str) -> dict:
    """
    Envía el mensaje a Claude y clasifica el resultado.

    Devuelve un dict con una de estas formas:
    - {"tipo": "venta", "datos": {...}, "mensaje_original": texto}
    - {"tipo": "consulta", "periodo": "hoy"|"semana"}
    - {"tipo": "conversacion", "respuesta": "..."}
    - {"tipo": "error", "respuesta": "..."}  (si la API falla)
    """
    try:
        respuesta = cliente_anthropic.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=500,
            system=PROMPT_SISTEMA,
            tools=[TOOL_REGISTRAR_VENTA, TOOL_CONSULTAR_VENTAS],
            messages=[{"role": "user", "content": texto}],
        )
    except Exception as e:  # red, API key inválida, etc.
        logger.error("Error llamando a Claude: %s", e)
        return {
            "tipo": "error",
            "respuesta": "Ups, tuve un problema interno y no pude procesar tu mensaje. Inténtalo de nuevo en un ratito 🙏",
        }

    # Buscar si Claude usó alguna tool
    for bloque in respuesta.content:
        if bloque.type == "tool_use":
            if bloque.name == "registrar_venta":
                datos = dict(bloque.input)
                datos.setdefault("cantidad", 1)
                datos.setdefault("variante", "")
                datos.setdefault("cliente", "")
                return {"tipo": "venta", "datos": datos, "mensaje_original": texto}
            if bloque.name == "consultar_ventas":
                return {"tipo": "consulta", "periodo": bloque.input.get("periodo", "hoy")}

    # Sin tool -> respuesta conversacional
    texto_respuesta = "".join(b.text for b in respuesta.content if b.type == "text").strip()
    if not texto_respuesta:
        texto_respuesta = (
            "Hola 👋 Soy tu Cuaderno Vivo. Mándame tus ventas como mensaje o nota de voz "
            "(ej: 'vendí un vestido S a 15 lucas') y yo las anoto por ti."
        )
    return {"tipo": "conversacion", "respuesta": texto_respuesta}


def redactar_respuesta_consulta(periodo: str, resumen: dict) -> str:
    """
    Le pide a Claude que redacte en lenguaje natural y cercano la respuesta
    a una pregunta sobre ventas, usando los datos ya calculados desde Sheets.

    resumen: {"total": int, "num_ventas": int, "productos_top": [("vestido", 3), ...]}
    """
    contexto = (
        f"Período consultado: {periodo}\n"
        f"Total vendido: ${resumen['total']:,.0f} pesos\n"
        f"Número de ventas: {resumen['num_ventas']}\n"
        f"Productos más vendidos: {resumen['productos_top']}"
    )
    try:
        respuesta = cliente_anthropic.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=300,
            system=(
                "Redacta una respuesta corta y amable para WhatsApp, en español chileno simple, "
                "informando estos datos de ventas a la dueña de una pyme. Usa máximo 1-2 emojis. "
                "No inventes datos que no estén en el contexto."
            ),
            messages=[{"role": "user", "content": contexto}],
        )
        return "".join(b.text for b in respuesta.content if b.type == "text").strip()
    except Exception as e:
        logger.error("Error redactando respuesta de consulta: %s", e)
        # Respuesta de respaldo sin IA, para no dejar a la usuaria sin datos
        return (
            f"Resumen ({periodo}): vendiste ${resumen['total']:,.0f} en "
            f"{resumen['num_ventas']} venta(s) 📒"
        )
