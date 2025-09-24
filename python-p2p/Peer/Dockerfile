# Dockerfile para Peer con sistema REST API
FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY src/requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ .

# Crear directorios necesarios
RUN mkdir -p shared_files downloads logs

# Configurar variables de entorno por defecto
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PEER_ID=peer1
ENV PEER_USERNAME=usuario1
ENV PEER_PASSWORD=password1
ENV PEER_HOST=0.0.0.0
ENV PEER_REST_PORT=8001
ENV SERVER_URL=directory-server:50051
ENV SHARED_DIRECTORY=/app/shared_files

# Crear archivo de configuración dinámico
RUN echo '#!/bin/bash\n\
cat > config.json << EOF\n\
{\n\
  "peer": {\n\
    "peer_id": "${PEER_ID}",\n\
    "username": "${PEER_USERNAME}",\n\
    "password": "${PEER_PASSWORD}"\n\
  },\n\
  "network": {\n\
    "host": "${PEER_HOST}",\n\
    "rest_port": ${PEER_REST_PORT},\n\
    "server_url": "${SERVER_URL}"\n\
  },\n\
  "files": {\n\
    "shared_directory": "${SHARED_DIRECTORY}",\n\
    "allowed_extensions": [".txt", ".json", ".py", ".md", ".log"],\n\
    "max_file_size_mb": 100\n\
  },\n\
  "logging": {\n\
    "level": "INFO",\n\
    "file": "peer.log",\n\
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"\n\
  }\n\
}\n\
EOF\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

# Exponer puerto
EXPOSE 8001

# Punto de entrada
ENTRYPOINT ["/entrypoint.sh"]

# Comando por defecto - ejecutar PServer
CMD ["python", "PServer/pserver.py"]