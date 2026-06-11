# Imagen base liviana con Python 3.11
FROM python:3.11-slim

# ffmpeg es necesario para que faster-whisper decodifique audio .ogg
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias primero (aprovecha la caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código
COPY . .

# Railway/Render inyectan la variable PORT; usamos 8000 por defecto
ENV PORT=8000
EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
