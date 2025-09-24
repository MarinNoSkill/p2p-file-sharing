# Sistema P2P con API REST# Sistema P2P File Sharing con REST API y Autenticación



## DescripciónSistema de archivos distribuido P2P que requiere autenticación obligatoria para todas las operaciones. Cada peer debe hacer login antes de poder realizar cualquier acción.

Implementación del sistema P2P con interfaz REST simplificada. Cada peer ofrece 4 comandos esenciales a través de una API REST.

## 🚀 Características

## Comandos Disponibles

- **Autenticación Obligatoria**: Cada peer requiere login antes de cualquier operación

### 1. HEALTH - Verificar estado del peer- **REST API**: Todas las operaciones via endpoints HTTP

```bash- **Docker Compose**: Despliegue completo con múltiples peers

curl http://localhost:8001/health- **Postman Ready**: Colección incluida para testing

```- **Token-based Auth**: Autenticación mediante tokens de sesión

- **Microservicios**: Arquitectura separada PServer/PClient

### 2. LOGIN - Autenticación obligatoria

```bash## 📋 Prerrequisitos

curl -X POST http://localhost:8001/login \

  -H "Content-Type: application/json" \- Docker y Docker Compose

  -d '{"peer_id": "peer1", "username": "usuario1", "password": "password1"}'- Postman (para testing de APIs)

```- Python 3.9+ (para desarrollo local)



### 3. CREATE - Subir archivos## 🛠️ Instalación y Uso

```bash

curl -X POST http://localhost:8001/create \### 1. Clonar y preparar el proyecto

  -H "Authorization: Bearer <token>" \

  -F "file=@archivo.txt"```bash

```git clone <repo-url>

cd python-p2p

### 4. SEARCH - Buscar en la red P2P```

```bash

curl -X POST http://localhost:8001/search \### 2. Desplegar con Docker Compose

  -H "Content-Type: application/json" \

  -H "Authorization: Bearer <token>" \```bash

  -d '{"query": "documento"}'# Construir y ejecutar todos los servicios

```docker-compose up --build



### 5. DOWNLOAD - Descargar archivos# Ver logs en tiempo real

```bashdocker-compose logs -f

curl -X GET http://localhost:8001/download/archivo.txt \

  -H "Authorization: Bearer <token>" \# Ejecutar en background

  -o archivo_descargado.txtdocker-compose up -d --build

``````



## Configuración de Peers### 3. Verificar que los servicios estén corriendo



- **Peer1 (8001)**: shared_files/```bash

- **Peer2 (8002)**: shared_files_peer2/# Verificar que todos los contenedores estén activos

- **Peer3 (8003)**: shared_files_peer3/docker-compose ps



## Credenciales# Debería mostrar:

# - p2p-directory-server (puerto 50051)

- Peer1: usuario1 / password1# - p2p-peer1 (puerto 8001)

- Peer2: usuario2 / password2  # - p2p-peer2 (puerto 8002)

- Peer3: usuario3 / password3# - p2p-peer3 (puerto 8003)

```

## Uso con Docker

### 4. Testing con Postman

```bash

docker-compose up --build -d1. **Importar la colección**:

```   - Abrir Postman
   - Import → Upload Files
   - Seleccionar `postman_collection.json`

2. **Ejecutar flujo completo**:
   - Usar la carpeta "Peer 1 - Flujo Completo"
   - Ejecutar requests en orden:
     1. Health Check
     2. Login (OBLIGATORIO)
     3. Get Status
     4. Scan Files
     5. Index Files
     6. List Local Files

3. **Probar autenticación**:
   - Usar carpeta "Tests de Autenticación"
   - Verificar que requests sin token fallan (401)

## 🔐 Flujo de Autenticación

### 1. Login Obligatorio
Cada peer DEBE hacer login antes de cualquier operación:

```bash
POST http://localhost:8001/login
Content-Type: application/json

{
    "peer_id": "peer1",
    "username": "usuario1",
    "password": "password1"
}
```

**Respuesta exitosa**:
```json
{
    "success": true,
    "message": "Login exitoso",
    "token": "uuid-token-here",
    "peer_info": {
        "peer_id": "peer1",
        "username": "usuario1"
    }
}
```

### 2. Usar Token en Todas las Requests
Agregar header de autorización en todas las requests posteriores:

```
Authorization: Bearer <token-recibido>
```

### 3. Logout (Opcional)
```bash
POST http://localhost:8001/logout
Authorization: Bearer <token>
```

## 📚 API Endpoints

### Endpoints Públicos (sin autenticación)
- `GET /health` - Health check del servicio
- `POST /login` - Login del peer

### Endpoints Protegidos (requieren autenticación)
- `GET /status` - Estado detallado del peer
- `POST /scan` - Escanear archivos del directorio compartido
- `POST /index` - Indexar archivos en el servidor de directorio
- `POST /search` - Buscar archivos en la red P2P
- `GET /files` - Listar archivos locales
- `GET /download/{filename}` - Descargar archivo específico
- `POST /upload` - Subir archivo al directorio compartido
- `POST /logout` - Cerrar sesión

## 🎯 Flujo Típico de Uso

### 1. Preparar Peer 1
```bash
# 1. Login
POST http://localhost:8001/login
{
    "peer_id": "peer1",
    "username": "usuario1", 
    "password": "password1"
}

# 2. Escanear archivos locales
POST http://localhost:8001/scan
Authorization: Bearer <token>

# 3. Indexar en servidor
POST http://localhost:8001/index
Authorization: Bearer <token>
{
    "force_rescan": true
}
```

### 2. Preparar Peer 2
```bash
# 1. Login
POST http://localhost:8002/login
{
    "peer_id": "peer2",
    "username": "usuario2",
    "password": "password2"
}

# 2. Escanear e indexar archivos
POST http://localhost:8002/scan
POST http://localhost:8002/index
```

### 3. Buscar Archivos P2P
```bash
# Desde cualquier peer logueado
POST http://localhost:8001/search
Authorization: Bearer <token>
{
    "query": "documento"
}
```

### 4. Descargar Archivos
```bash
# Descargar archivo específico
GET http://localhost:8001/download/documento.txt
Authorization: Bearer <token>
```

## 🔧 Configuración

### Variables de Entorno (Docker)
```bash
# Peer Configuration
PEER_ID=peer1
PEER_USERNAME=usuario1
PEER_PASSWORD=password1
PEER_HOST=0.0.0.0
PEER_REST_PORT=8001

# Network Configuration  
SERVER_URL=directory-server:50051

# Files Configuration
SHARED_DIRECTORY=/app/shared_files
```

### Configuración JSON Local
```json
{
  "peer": {
    "peer_id": "peer1",
    "username": "usuario1",
    "password": "password1"
  },
  "network": {
    "host": "localhost",
    "rest_port": 8001,
    "server_url": "localhost:50051"
  },
  "files": {
    "shared_directory": "./shared_files",
    "allowed_extensions": [".txt", ".json", ".py", ".md"],
    "max_file_size_mb": 100
  }
}
```

## 🐛 Troubleshooting

### 1. Peer no responde
```bash
# Verificar que el contenedor esté corriendo
docker-compose ps

# Ver logs del peer
docker-compose logs peer1

# Reiniciar servicio específico
docker-compose restart peer1
```

### 2. Error de autenticación
- Verificar que el login se haya realizado correctamente
- Confirmar que el token esté incluido en los headers
- Verificar que el token no haya expirado

### 3. Error de conexión al servidor
```bash
# Verificar que el servidor de directorio esté corriendo
docker-compose logs directory-server

# Reiniciar todo el stack
docker-compose down
docker-compose up --build
```

### 4. Archivos no encontrados
- Verificar que los archivos estén en `./shared_files`
- Ejecutar `POST /scan` para reescanear
- Verificar permisos de lectura en los directorios

## 📊 Monitoreo

### Health Checks
```bash
# Verificar estado de cada peer
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

### Status Detallado (requiere auth)
```bash
# Login primero, luego:
curl -H "Authorization: Bearer <token>" http://localhost:8001/status
```

## 🎮 Testing Automatizado

### Ejecutar Collection Completa en Postman
1. Importar `postman_collection.json`
2. Usar "Collection Runner"
3. Seleccionar toda la colección
4. Ejecutar en orden secuencial

### Tests Incluidos
- ✅ Health checks de todos los peers
- ✅ Login/logout functionality
- ✅ Autenticación obligatoria (401 sin token)
- ✅ Escaneo e indexado de archivos
- ✅ Búsquedas P2P cross-peer
- ✅ Descarga de archivos

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Postman       │    │  Docker Compose  │    │   Peer Network  │
│   Testing       │───▶│  Orchestration   │───▶│   P2P Protocol  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Directory Server │
                       │    (gRPC :50051) │
                       └──────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │   Peer 1    │ │   Peer 2    │ │   Peer 3    │
        │ REST :8001  │ │ REST :8002  │ │ REST :8003  │
        │ (Auth Req)  │ │ (Auth Req)  │ │ (Auth Req)  │
        └─────────────┘ └─────────────┘ └─────────────┘
```

## 🔗 Links Útiles

- **Peer 1 API**: http://localhost:8001
- **Peer 2 API**: http://localhost:8002  
- **Peer 3 API**: http://localhost:8003
- **Directory Server**: localhost:50051 (gRPC)

---

¡El sistema está listo para testing con Postman! 🚀