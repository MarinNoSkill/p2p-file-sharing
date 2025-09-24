# Dockerfile para Directory Server
FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements del server
COPY src/requirements.txt* ./
# Si no existe requirements.txt específico, usar el general
RUN echo "grpcio==1.59.3\ngrpcio-tools==1.59.3\nprotobuf==4.25.1\npyyaml==6.0.1\nfastapi==0.104.1\nuvicorn==0.24.0" > requirements.txt

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ .

# Crear directorios necesarios
RUN mkdir -p logs

# Configurar variables de entorno
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=50051
ENV LOG_LEVEL=INFO

# Exponer puerto gRPC
EXPOSE 50051

# Comando por defecto - ejecutar servidor
CMD ["python", "server.py"]