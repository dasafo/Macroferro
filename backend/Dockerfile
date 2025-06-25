# backend/Dockerfile

# Usar una imagen base oficial de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo en el contenedor
WORKDIR /app

# Copiar el archivo de requerimientos primero para aprovechar el cache de Docker
COPY ./requirements.txt /app/requirements.txt

# Instalar dependencias del sistema para WeasyPrint (PDF generation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Instalar las dependencias de Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación al directorio de trabajo
COPY ./app /app/app

# Exponer el puerto en el que correrá la aplicación (Uvicorn por defecto usa 8000)
EXPOSE 8000

# Comando para correr la aplicación usando Uvicorn
# El comando en docker-compose.yml sobreescribirá este si se especifica allí.
# Este es un buen CMD por defecto si se ejecuta la imagen directamente.
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]