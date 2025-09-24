#!/usr/bin/env python3
"""
API REST para el servidor de directorio P2P
Proporciona endpoints HTTP para interacción con el sistema P2P
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Modelos de datos para la API REST
class LoginRequest(BaseModel):
    username: str
    password: str
    peer_id: str
    peer_url: str
    port: int

class LoginResponse(BaseModel):
    success: bool
    token: str
    message: str
    connected_peers: List[Dict] = []

class SearchRequest(BaseModel):
    filename: str
    file_pattern: str = ""

class SearchResponse(BaseModel):
    success: bool
    message: str
    results: List[Dict] = []

class FileMetadata(BaseModel):
    filename: str
    file_path: str
    file_size: int
    file_hash: str
    last_modified: int
    mime_type: str
    tags: List[str] = []

class IndexRequest(BaseModel):
    files: List[FileMetadata]

class IndexResponse(BaseModel):
    success: bool
    message: str
    files_indexed: int

class PeerInfoResponse(BaseModel):
    success: bool
    peers: List[Dict] = []

class HeartbeatResponse(BaseModel):
    success: bool
    server_timestamp: int
    active_peers: int

class StatsResponse(BaseModel):
    total_peers: int
    active_peers: int
    total_files: int
    uptime: float


# Seguridad JWT simple
security = HTTPBearer()

class RESTAPIServer:
    """Servidor REST para el sistema P2P"""
    
    def __init__(self, directory_server, config_manager):
        self.directory_server = directory_server
        self.config_manager = config_manager
        self.server_config = config_manager.get_server_config()
        
        # Crear aplicación FastAPI
        self.app = FastAPI(
            title="P2P Directory Server API",
            description="API REST para el sistema P2P de intercambio de archivos",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Configurar CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Configurar rutas
        self._setup_routes()
        
        logging.info("API REST inicializada")
    
    def _setup_routes(self):
        """Configura las rutas de la API"""
        
        @self.app.get("/")
        async def root():
            """Endpoint raíz con información del servidor"""
            return {
                "message": "P2P Directory Server API",
                "version": "1.0.0",
                "status": "running",
                "timestamp": int(time.time())
            }
        
        @self.app.get("/health")
        async def health_check():
            """Endpoint de verificación de salud"""
            stats = self.directory_server.get_stats()
            return {
                "status": "healthy",
                "stats": stats,
                "timestamp": int(time.time())
            }
        
        @self.app.post("/login", response_model=LoginResponse)
        async def login(request: LoginRequest):
            """Endpoint de login"""
            try:
                # Crear request gRPC
                import service_pb2
                grpc_request = service_pb2.LoginRequest(
                    username=request.username,
                    password=request.password,
                    peer_id=request.peer_id,
                    peer_url=request.peer_url,
                    port=request.port
                )
                
                # Llamar al servicio gRPC
                response = await self.directory_server.Login(grpc_request, None)
                
                # Convertir peers a formato REST
                connected_peers = []
                for peer in response.connected_peers:
                    connected_peers.append({
                        "peer_id": peer.peer_id,
                        "username": peer.username,
                        "url": peer.url,
                        "port": peer.port,
                        "is_online": peer.is_online,
                        "last_seen": peer.last_seen,
                        "file_count": peer.file_count
                    })
                
                return LoginResponse(
                    success=response.success,
                    token=response.token,
                    message=response.message,
                    connected_peers=connected_peers
                )
                
            except Exception as e:
                logging.error(f"Error en login REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error en login: {str(e)}"
                )
        
        @self.app.post("/logout")
        async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
            """Endpoint de logout"""
            try:
                import service_pb2
                grpc_request = service_pb2.LogoutRequest(
                    peer_id="",  # Se puede obtener del token
                    token=credentials.credentials
                )
                
                response = await self.directory_server.Logout(grpc_request, None)
                
                return {
                    "success": response.success,
                    "message": response.message
                }
                
            except Exception as e:
                logging.error(f"Error en logout REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error en logout: {str(e)}"
                )
        
        @self.app.post("/index", response_model=IndexResponse)
        async def index_files(
            request: IndexRequest,
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Endpoint para indexar archivos"""
            try:
                import service_pb2
                
                # Convertir archivos a formato gRPC
                files_grpc = []
                for file_data in request.files:
                    file_metadata = service_pb2.FileMetadata(
                        filename=file_data.filename,
                        file_path=file_data.file_path,
                        file_size=file_data.file_size,
                        file_hash=file_data.file_hash,
                        last_modified=file_data.last_modified,
                        mime_type=file_data.mime_type,
                        tags=file_data.tags
                    )
                    files_grpc.append(file_metadata)
                
                grpc_request = service_pb2.IndexRequest(
                    peer_id="",  # Se puede obtener del token
                    token=credentials.credentials,
                    files=files_grpc
                )
                
                response = await self.directory_server.Index(grpc_request, None)
                
                return IndexResponse(
                    success=response.success,
                    message=response.message,
                    files_indexed=response.files_indexed
                )
                
            except Exception as e:
                logging.error(f"Error en indexado REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error en indexado: {str(e)}"
                )
        
        @self.app.post("/search", response_model=SearchResponse)
        async def search_files(
            request: SearchRequest,
            credentials: HTTPAuthorizationCredentials = Depends(security)
        ):
            """Endpoint para buscar archivos"""
            try:
                import service_pb2
                grpc_request = service_pb2.SearchRequest(
                    peer_id="",  # Se puede obtener del token
                    token=credentials.credentials,
                    filename=request.filename,
                    file_pattern=request.file_pattern
                )
                
                response = await self.directory_server.Search(grpc_request, None)
                
                # Convertir resultados a formato REST
                results = []
                for file_location in response.results:
                    result = {
                        "file_info": {
                            "filename": file_location.file_info.filename,
                            "file_path": file_location.file_info.file_path,
                            "file_size": file_location.file_info.file_size,
                            "file_hash": file_location.file_info.file_hash,
                            "last_modified": file_location.file_info.last_modified,
                            "mime_type": file_location.file_info.mime_type,
                            "tags": list(file_location.file_info.tags)
                        },
                        "peer_info": {
                            "peer_id": file_location.peer_info.peer_id,
                            "username": file_location.peer_info.username,
                            "url": file_location.peer_info.url,
                            "port": file_location.peer_info.port,
                            "is_online": file_location.peer_info.is_online,
                            "last_seen": file_location.peer_info.last_seen,
                            "file_count": file_location.peer_info.file_count
                        },
                        "download_url": file_location.download_url,
                        "is_available": file_location.is_available
                    }
                    results.append(result)
                
                return SearchResponse(
                    success=response.success,
                    message=response.message,
                    results=results
                )
                
            except Exception as e:
                logging.error(f"Error en búsqueda REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error en búsqueda: {str(e)}"
                )
        
        @self.app.get("/peers", response_model=PeerInfoResponse)
        async def get_peers(credentials: HTTPAuthorizationCredentials = Depends(security)):
            """Endpoint para obtener información de peers"""
            try:
                import service_pb2
                grpc_request = service_pb2.PeerInfoRequest(
                    token=credentials.credentials
                )
                
                response = await self.directory_server.GetPeerInfo(grpc_request, None)
                
                # Convertir peers a formato REST
                peers = []
                for peer in response.peers:
                    peers.append({
                        "peer_id": peer.peer_id,
                        "username": peer.username,
                        "url": peer.url,
                        "port": peer.port,
                        "is_online": peer.is_online,
                        "last_seen": peer.last_seen,
                        "file_count": peer.file_count
                    })
                
                return PeerInfoResponse(
                    success=response.success,
                    peers=peers
                )
                
            except Exception as e:
                logging.error(f"Error obteniendo peers REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error obteniendo peers: {str(e)}"
                )
        
        @self.app.post("/heartbeat", response_model=HeartbeatResponse)
        async def heartbeat(credentials: HTTPAuthorizationCredentials = Depends(security)):
            """Endpoint de heartbeat"""
            try:
                import service_pb2
                grpc_request = service_pb2.HeartbeatRequest(
                    token=credentials.credentials
                )
                
                response = await self.directory_server.Heartbeat(grpc_request, None)
                
                return HeartbeatResponse(
                    success=response.success,
                    server_timestamp=response.server_timestamp,
                    active_peers=response.active_peers
                )
                
            except Exception as e:
                logging.error(f"Error en heartbeat REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error en heartbeat: {str(e)}"
                )
        
        @self.app.get("/stats", response_model=StatsResponse)
        async def get_stats():
            """Endpoint de estadísticas del servidor"""
            try:
                stats = self.directory_server.get_stats()
                return StatsResponse(**stats)
            except Exception as e:
                logging.error(f"Error obteniendo estadísticas REST: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error obteniendo estadísticas: {str(e)}"
                )


async def run_rest_api(directory_server, config_manager):
    """Función para ejecutar el servidor REST"""
    try:
        logging.info("Iniciando API REST...")
        
        # Crear servidor REST
        rest_server = RESTAPIServer(directory_server, config_manager)
        server_config = config_manager.get_server_config()
        
        # Configuración de Uvicorn
        config = uvicorn.Config(
            app=rest_server.app,
            host=server_config.host,
            port=server_config.rest_port,
            log_level="info",
            access_log=True,
            reload=False
        )
        
        # Iniciar servidor
        server = uvicorn.Server(config)
        logging.info(f"API REST iniciada en http://{server_config.host}:{server_config.rest_port}")
        
        await server.serve()
        
    except Exception as e:
        logging.error(f"Error en API REST: {e}")
        raise


if __name__ == "__main__":
    # Este archivo no debe ejecutarse directamente
    print("Este módulo debe ser importado por server.py")