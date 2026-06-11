"""
test_ai_extractor.py — Pruebas del extractor con mensajes reales en chileno.

Estas pruebas hacen llamadas REALES a la API de Claude (requieren
ANTHROPIC_API_KEY en el .env). Para correrlas:

    pytest tests/ -v

Si prefieres no gastar tokens, puedes marcar la suite con -k para
correr solo algunos casos.
"""

import pytest

from app.ai_extractor import interpretar_mensaje


# ------------------------------------------------------------------
# Casos de VENTA
# ------------------------------------------------------------------

def test_venta_simple_con_lucas():
    r = interpretar_mensaje("vendí un vestido S a 15 lucas a la Pamela")
    assert r["tipo"] == "venta"
    d = r["datos"]
    assert "vestido" in d["producto"].lower()
    assert d["precio_unitario"] == 15000
    assert d["variante"].upper().strip() == "S"
    assert "pamela" in d["cliente"].lower()


def test_venta_con_luca_singular():
    r = interpretar_mensaje("se vendió una polera a 8 lucas")
    assert r["tipo"] == "venta"
    assert r["datos"]["precio_unitario"] == 8000
    assert "polera" in r["datos"]["producto"].lower()


def test_venta_varias_unidades():
    r = interpretar_mensaje("vendí 3 poleras talla m a 5 lucas cada una")
    assert r["tipo"] == "venta"
    d = r["datos"]
    assert d["cantidad"] == 3
    assert d["precio_unitario"] == 5000
    assert d["variante"].upper().strip() == "M"


def test_venta_precio_directo_sin_lucas():
    r = interpretar_mensaje("vendí un delantal a 12000")
    assert r["tipo"] == "venta"
    assert r["datos"]["precio_unitario"] == 12000


def test_venta_quince_mil():
    r = interpretar_mensaje("salió una falda L a 15 mil")
    assert r["tipo"] == "venta"
    assert r["datos"]["precio_unitario"] == 15000
    assert r["datos"]["variante"].upper().strip() == "L"


# ------------------------------------------------------------------
# Casos de CONSULTA
# ------------------------------------------------------------------

def test_consulta_ventas_hoy():
    r = interpretar_mensaje("¿cuánto vendí hoy?")
    assert r["tipo"] == "consulta"
    assert r["periodo"] == "hoy"


def test_consulta_ventas_semana():
    r = interpretar_mensaje("qué producto se vendió más esta semana?")
    assert r["tipo"] == "consulta"
    assert r["periodo"] == "semana"


# ------------------------------------------------------------------
# Casos que NO son venta ni consulta
# ------------------------------------------------------------------

def test_saludo_no_es_venta():
    r = interpretar_mensaje("hola, buenos días!")
    assert r["tipo"] == "conversacion"
    assert isinstance(r["respuesta"], str) and len(r["respuesta"]) > 0


def test_mensaje_ambiguo_sin_precio():
    # Sin precio no debería registrarse como venta completa,
    # o al menos no inventar un precio.
    r = interpretar_mensaje("me preguntaron por los vestidos")
    assert r["tipo"] in ("conversacion", "consulta")


def test_agradecimiento():
    r = interpretar_mensaje("gracias!!")
    assert r["tipo"] == "conversacion"
