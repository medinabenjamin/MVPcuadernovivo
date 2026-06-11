"""
sheets.py — Lectura y escritura en Google Sheets (hoja "Ventas").

Columnas de la hoja (fila 1 = encabezados):
fecha | hora | producto | talla/variante | cantidad | precio_unitario | total | cliente | mensaje_original
"""

import json
import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread

from app import config

logger = logging.getLogger(__name__)

ENCABEZADOS = [
    "fecha", "hora", "producto", "talla/variante", "cantidad",
    "precio_unitario", "total", "cliente", "mensaje_original",
]

_hoja = None  # caché de la conexión


def _obtener_hoja():
    """Conecta con Google Sheets usando la cuenta de servicio y devuelve la hoja 'Ventas'."""
    global _hoja
    if _hoja is not None:
        return _hoja

    cred = config.GOOGLE_SHEETS_CREDENTIALS_JSON
    if os.path.isfile(cred):
        # Es una ruta a un archivo (uso local)
        gc = gspread.service_account(filename=cred)
    else:
        # Es el JSON completo pegado en la variable de entorno (uso en Railway/Render)
        gc = gspread.service_account_from_dict(json.loads(cred))

    libro = gc.open_by_key(config.GOOGLE_SHEET_ID)
    try:
        _hoja = libro.worksheet("Ventas")
    except gspread.WorksheetNotFound:
        # Si no existe, la creamos con los encabezados
        _hoja = libro.add_worksheet(title="Ventas", rows=1000, cols=len(ENCABEZADOS))
        _hoja.append_row(ENCABEZADOS)

    # Asegurar encabezados si la hoja está vacía
    if not _hoja.get_all_values():
        _hoja.append_row(ENCABEZADOS)
    return _hoja


def _ahora() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def agregar_venta(datos: dict, mensaje_original: str) -> float:
    """
    Agrega una fila con la venta y devuelve el TOTAL de esa venta.

    datos: {"producto", "variante", "cantidad", "precio_unitario", "cliente"}
    """
    hoja = _obtener_hoja()
    ahora = _ahora()
    cantidad = float(datos.get("cantidad") or 1)
    precio = float(datos["precio_unitario"])
    total = cantidad * precio

    fila = [
        ahora.strftime("%Y-%m-%d"),
        ahora.strftime("%H:%M"),
        datos.get("producto", ""),
        datos.get("variante", ""),
        cantidad,
        precio,
        total,
        datos.get("cliente", ""),
        mensaje_original,
    ]
    hoja.append_row(fila, value_input_option="USER_ENTERED")
    logger.info("Venta registrada: %s", fila)
    return total


def _leer_ventas_desde(fecha_inicio: str) -> list[dict]:
    """Lee todas las filas con fecha >= fecha_inicio (formato YYYY-MM-DD)."""
    hoja = _obtener_hoja()
    filas = hoja.get_all_records()  # usa la fila 1 como claves
    return [f for f in filas if str(f.get("fecha", "")) >= fecha_inicio]


def _resumir(ventas: list[dict]) -> dict:
    """Calcula total, número de ventas y top de productos de una lista de filas."""
    total = 0.0
    contador = Counter()
    for v in ventas:
        try:
            total += float(v.get("total") or 0)
            cantidad = float(v.get("cantidad") or 1)
            producto = str(v.get("producto") or "desconocido").lower()
            contador[producto] += cantidad
        except (TypeError, ValueError):
            continue  # fila con datos corruptos: se ignora sin caerse
    return {
        "total": total,
        "num_ventas": len(ventas),
        "productos_top": contador.most_common(3),
    }


def resumen_del_dia() -> dict:
    """Total vendido, número de ventas y producto más vendido HOY."""
    hoy = _ahora().strftime("%Y-%m-%d")
    return _resumir(_leer_ventas_desde(hoy))


def resumen_de_la_semana() -> dict:
    """Resumen de la semana actual (desde el lunes)."""
    ahora = _ahora()
    lunes = (ahora - timedelta(days=ahora.weekday())).strftime("%Y-%m-%d")
    return _resumir(_leer_ventas_desde(lunes))
