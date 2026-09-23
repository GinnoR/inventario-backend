FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema para opencv y lxml
RUN apt-get update --fix-missing && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar los binarios del navegador para Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar código fuente
COPY . .

# Puerto dinámico de Railway
ENV PORT=8000
EXPOSE $PORT

# Comando de inicio
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
