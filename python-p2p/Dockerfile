# Dockerfile para el servidor de directorio P2P
FROM python:3.9-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY Server/src/ ./Server/src/
COPY Peer/src/ ./Peer/src/
COPY shared_files/ ./shared_files/

# Crear directorio para logs
RUN mkdir -p /app/logs

# Generar archivos protobuf
WORKDIR /app/Server/src/protobuf
RUN python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. service.proto

WORKDIR /app/Peer/src/protobuf
RUN python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. service.proto

# Volver al directorio principal
WORKDIR /app

# Exponer puertos
EXPOSE 50051 8080

# Variables de entorno
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Comando por defecto (servidor)
CMD ["python", "Server/src/server.py"]