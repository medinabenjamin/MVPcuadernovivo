# 📒 Cuaderno Vivo

**Cuaderno Vivo** es un MVP universitario construido para NewenDomo, una pyme chilena de confecciones. La dueña atiende a sus clientes por WhatsApp y registra sus ventas en cuadernos físicos; este sistema le permite seguir trabajando exactamente igual, pero ahora basta con que envíe un mensaje corto (texto o nota de voz) a un número de WhatsApp dedicado — por ejemplo, *"vendí un vestido S a 15 lucas a la Pamela"* — y la venta queda registrada automáticamente.

Detrás de escena, un backend en Python recibe el mensaje vía la WhatsApp Cloud API, lo transcribe si es audio (faster-whisper), lo interpreta con Claude (Anthropic) usando *tool use* para extraer producto, talla, cantidad, precio y cliente, y guarda la venta en una hoja de Google Sheets que funciona como el "cuaderno digital". Además, la dueña puede hacer preguntas como *"¿cuánto vendí hoy?"* y cada noche a las 20:00 recibe automáticamente un resumen del día.

El proyecto está pensado para personas con baja alfabetización digital: cero apps nuevas, cero formularios, solo WhatsApp como siempre.

---

## Estructura

```
cuaderno-vivo/
├── app/
│   ├── main.py            # FastAPI + webhook + flujo completo
│   ├── whatsapp.py        # envío/recepción y descarga de audios (Cloud API)
│   ├── ai_extractor.py    # Claude con tool use: extrae ventas y consultas
│   ├── transcription.py   # faster-whisper (notas de voz -> texto)
│   ├── sheets.py          # Google Sheets: guardar ventas y resúmenes
│   ├── scheduler.py       # resumen diario 20:00 (America/Santiago)
│   └── config.py          # variables de entorno
├── tests/test_ai_extractor.py
├── .env.example
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 1. Obtener credenciales

### a) Anthropic (Claude API)
1. Crea una cuenta en https://console.anthropic.com
2. Ve a **API Keys → Create Key** y copia la clave (`sk-ant-...`).
3. Pégala en `.env` como `ANTHROPIC_API_KEY`.

### b) Meta — WhatsApp Cloud API (número de prueba)
1. Entra a https://developers.facebook.com y crea una app de tipo **Business**.
2. En el panel de la app, agrega el producto **WhatsApp**. Meta te asigna un **número de prueba** gratuito.
3. En **WhatsApp → API Setup**:
   - Copia el **Temporary access token** → `WHATSAPP_TOKEN` (dura ~24h; para algo más permanente, crea un *System User token* en Business Settings).
   - Copia el **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`.
   - En "To", agrega el número de la dueña como destinatario de prueba (Meta exige registrarlo y confirmar un código).
4. Inventa un string secreto cualquiera → `WHATSAPP_VERIFY_TOKEN` (lo usarás al configurar el webhook).

### c) Google Sheets API (cuenta de servicio)
1. Entra a https://console.cloud.google.com y crea un proyecto.
2. Habilita las APIs **Google Sheets API** y **Google Drive API**.
3. Ve a **IAM y administración → Cuentas de servicio → Crear cuenta de servicio**.
4. Dentro de la cuenta de servicio: **Claves → Agregar clave → JSON**. Se descarga un archivo; guárdalo como `credentials.json` en la raíz del proyecto.
5. Crea una hoja de cálculo en Google Sheets y crea (o deja que el sistema cree) una pestaña llamada **Ventas**.
6. **Comparte la hoja** (botón Compartir) con el email de la cuenta de servicio (algo como `xxx@proyecto.iam.gserviceaccount.com`) con permiso de **Editor**. Sin este paso, el bot no podrá escribir.
7. Copia el ID de la hoja desde la URL (`/spreadsheets/d/ESTE_ID/edit`) → `GOOGLE_SHEET_ID`.

---

## 2. Correr localmente

```bash
# 1. Crear y activar entorno virtual
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables
cp .env.example .env
# -> edita .env con tus credenciales reales

# 4. Levantar el servidor
uvicorn app.main:app --reload --port 8000
```

Verifica en http://localhost:8000 que responde `{"status": "ok"}`.

> Nota: la primera nota de voz tardará más porque se descarga el modelo de Whisper. Necesitas `ffmpeg` instalado (`sudo apt install ffmpeg` o `brew install ffmpeg`).

---

## 3. Pruebas locales con ngrok

Meta necesita una URL pública HTTPS para el webhook. En desarrollo se usa ngrok:

```bash
# En una terminal: el servidor
uvicorn app.main:app --port 8000

# En otra terminal: el túnel
ngrok http 8000
```

ngrok te dará una URL tipo `https://abc123.ngrok-free.app`. Luego, en Meta for Developers:

1. **WhatsApp → Configuration → Webhook → Edit**.
2. **Callback URL**: `https://abc123.ngrok-free.app/webhook`
3. **Verify token**: el mismo valor de `WHATSAPP_VERIFY_TOKEN` de tu `.env`.
4. Clic en **Verify and save** (tu servidor debe estar corriendo).
5. En **Webhook fields**, suscríbete al campo **messages**.

⚠️ Cada vez que reinicies ngrok, la URL cambia y debes actualizarla en Meta.

## 4. Despliegue en Railway

1. Sube el proyecto a un repositorio de GitHub (sin `.env` ni `credentials.json`).
2. En https://railway.app: **New Project → Deploy from GitHub repo** y selecciona el repo. Railway detecta el `Dockerfile` automáticamente.
3. En la pestaña **Variables**, agrega todas las del `.env.example`. Para `GOOGLE_SHEETS_CREDENTIALS_JSON`, pega el **contenido completo** del archivo JSON (el código lo detecta y lo parsea).
4. En **Settings → Networking → Generate Domain**, genera el dominio público (ej. `cuaderno-vivo.up.railway.app`).
5. En Meta for Developers, actualiza el webhook: **Callback URL** = `https://cuaderno-vivo.up.railway.app/webhook`, con el mismo verify token, y suscripción al campo **messages**.

(En Render es análogo: New → Web Service → conectar repo → Environment = Docker → agregar variables → usar la URL `.onrender.com` como callback.)

---

## 5. Demo rápida

Envía estos mensajes al número de prueba del bot:

1. `vendí un vestido S a 15 lucas a la Pamela` → debería responder ✅ con la venta anotada y el total del día.
2. 🎤 Nota de voz: *"se vendieron dos poleras talla M a cinco lucas cada una"* → transcribe y anota.
3. `¿cuánto vendí hoy?` → responde con el total, número de ventas y top de productos.

---

## 6. Pruebas automatizadas

```bash
pytest tests/ -v
```

> Las pruebas llaman a la API real de Claude (requieren `ANTHROPIC_API_KEY` válida y consumen algunos tokens).
---

## ✅ Checklist manual (para dejar todo funcionando)

- [ ] Crear cuenta en Anthropic y obtener `ANTHROPIC_API_KEY`.
- [ ] Crear app Business en Meta for Developers y agregar el producto WhatsApp.
- [ ] Copiar `WHATSAPP_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID` desde API Setup.
- [ ] Registrar el número de la dueña como destinatario de prueba en Meta.
- [ ] Inventar y anotar el `WHATSAPP_VERIFY_TOKEN`.
- [ ] Crear proyecto en Google Cloud, habilitar Sheets API y Drive API.
- [ ] Crear cuenta de servicio y descargar `credentials.json`.
- [ ] Crear la hoja de Google Sheets y **compartirla como Editor** con el email de la cuenta de servicio.
- [ ] Copiar el `GOOGLE_SHEET_ID` desde la URL.
- [ ] Copiar `.env.example` a `.env` y completar todos los valores (incluido `OWNER_PHONE_NUMBER`).
- [ ] Probar localmente con uvicorn + ngrok y verificar el webhook en Meta.
- [ ] Subir el repo a GitHub (verificando que `.env` y `credentials.json` NO se suban).
- [ ] Desplegar en Railway/Render, configurar variables y dominio.
- [ ] Actualizar la Callback URL del webhook en Meta con el dominio de producción.
- [ ] Enviar los mensajes de la "Demo rápida" para validar de punta a punta.
- [ ] Esperar (o adelantar el reloj del cron para probar) el resumen de las 20:00.
