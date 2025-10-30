# Usa una imagen base ligera de Python
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar y usar librerías como matplotlib y graphviz
RUN apt-get update && apt-get install -y \
    graphviz \
    libgraphviz-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Establecer variable de entorno para Cloud Run
ENV PORT=8080

# Exponer el puerto
EXPOSE 8080

# Comando para correr Flask en modo producción
CMD ["gunicorn", "-b", ":8080", "app:app"]
