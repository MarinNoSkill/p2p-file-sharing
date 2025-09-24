#!/usr/bin/env python3
"""
Servidor de directorio y localización para sistema P2P
Implementa un servidor gRPC que mantiene el registro de peers y archivos disponibles.
"""

import asyncio
import grpc
import logging
import threading
import time
import uuid
import hashlib
from concurrent import futures
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

# Importar los módulos generados por protobuf
import sys
import os

# Agregar el directorio protobuf al path
protobuf_path = os.path.join(os.path.dirname(__file__), 'protobuf')
sys.path.append(protobuf_path)

try:
    import service_pb2
    import service_pb2_grpc
except ImportError as e:
    print(f"Error: No se encontraron los archivos protobuf generados: {e}")
    print("Ejecuta: python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. protobuf/service.proto")
    sys.exit(1)

from config import ConfigManager, setup_logging


@dataclass
class PeerData:
    """Información de un peer conectado"""
    peer_id: str
    username: str
    url: str
    port: int
    token: str
    is_online: bool = True
    last_seen: datetime = field(default_factory=datetime.now)
    files: Dict[str, Dict] = field(default_factory=dict)  # filename -> file_metadata
    login_attempts: int = 0
    created_at: datetime = field(default_factory=datetime.now)


class P2PDirectoryServer(service_pb2_grpc.PeerServiceServicer):
    """
    Servidor de directorio principal del sistema P2P.
    Maneja el registro de peers, autenticación y búsqueda de archivos.
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.server_config = config_manager.get_server_config()
        self.db_config = config_manager.get_database_config()
        self.security_config = config_manager.get_security_config()
        
        # Base de datos en memoria
        self.peers: Dict[str, PeerData] = {}  # token -> PeerData
        self.peer_index: Dict[str, str] = {}  # peer_id -> token
        self.username_index: Dict[str, str] = {}  # username -> token
        
        # Lock para operaciones thread-safe
        self.db_lock = threading.RLock()
        
        # Contador para generar tokens únicos
        self.token_counter = 0
        
        # Iniciar tareas de limpieza
        self._start_cleanup_task()
        
        logging.info("Servidor de directorio P2P inicializado")
    
    def _generate_token(self) -> str:
        """Genera un token único para el peer"""
        with self.db_lock:
            self.token_counter += 1
            timestamp = int(time.time())
            unique_id = f"{timestamp}-{self.token_counter}-{uuid.uuid4().hex[:8]}"
            return hashlib.md5(unique_id.encode()).hexdigest()
    
    def _start_cleanup_task(self):
        """Inicia la tarea de limpieza periódica de peers inactivos"""
        def cleanup_loop():
            while True:
                try:
                    self._cleanup_inactive_peers()
                    time.sleep(self.db_config.cleanup_interval)
                except Exception as e:
                    logging.error(f"Error en limpieza periódica: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        logging.info("Tarea de limpieza periódica iniciada")
    
    def _cleanup_inactive_peers(self):
        """Limpia peers que han estado inactivos por mucho tiempo"""
        cutoff_time = datetime.now() - timedelta(seconds=self.db_config.peer_timeout)
        
        with self.db_lock:
            inactive_tokens = []
            for token, peer in self.peers.items():
                if peer.last_seen < cutoff_time:
                    inactive_tokens.append(token)
            
            for token in inactive_tokens:
                peer = self.peers[token]
                logging.info(f"Eliminando peer inactivo: {peer.peer_id}")
                
                # Limpiar índices
                if peer.peer_id in self.peer_index:
                    del self.peer_index[peer.peer_id]
                if peer.username in self.username_index:
                    del self.username_index[peer.username]
                
                # Eliminar peer
                del self.peers[token]
    
    def _validate_token(self, token: str) -> Optional[PeerData]:
        """Valida un token y retorna la información del peer"""
        with self.db_lock:
            peer = self.peers.get(token)
            if peer and peer.is_online:
                # Actualizar última actividad
                peer.last_seen = datetime.now()
                return peer
            return None
    
    async def Login(self, request, context):
        """Maneja el login de un peer en el sistema"""
        logging.info(f"Solicitud de login de: {request.username} - {request.peer_id}")
        
        try:
            with self.db_lock:
                # Verificar si el peer ya existe
                existing_token = self.username_index.get(request.username)
                
                if existing_token and existing_token in self.peers:
                    peer = self.peers[existing_token]
                    
                    # Verificar credenciales
                    if peer.username == request.username and peer.url == request.peer_url:
                        # Peer existente reconectándose
                        peer.is_online = True
                        peer.last_seen = datetime.now()
                        peer.port = request.port
                        
                        # Obtener lista de peers conectados
                        connected_peers = []
                        for p in self.peers.values():
                            if p.is_online and p.token != existing_token:
                                peer_info = service_pb2.PeerInfo(
                                    peer_id=p.peer_id,
                                    username=p.username,
                                    url=p.url,
                                    port=p.port,
                                    is_online=p.is_online,
                                    last_seen=int(p.last_seen.timestamp()),
                                    file_count=len(p.files)
                                )
                                connected_peers.append(peer_info)
                        
                        logging.info(f"Peer existente reconectado: {request.username}")
                        return service_pb2.LoginResponse(
                            success=True,
                            token=existing_token,
                            message="Reconexión exitosa",
                            connected_peers=connected_peers
                        )
                
                # Nuevo peer o credenciales incorrectas
                if self.security_config.enable_auth:
                    # Aquí podrías implementar validación de credenciales más robusta
                    # Por ahora, aceptamos cualquier combinación username/password
                    pass
                
                # Verificar límites de intentos de login
                if existing_token:
                    peer = self.peers[existing_token]
                    peer.login_attempts += 1
                    
                    if peer.login_attempts > self.security_config.max_login_attempts:
                        return service_pb2.LoginResponse(
                            success=False,
                            token="",
                            message="Demasiados intentos de login fallidos"
                        )
                
                # Crear nuevo peer
                token = self._generate_token()
                peer_data = PeerData(
                    peer_id=request.peer_id,
                    username=request.username,
                    url=request.peer_url,
                    port=request.port,
                    token=token,
                    is_online=True,
                    last_seen=datetime.now()
                )
                
                # Registrar en la base de datos
                self.peers[token] = peer_data
                self.peer_index[request.peer_id] = token
                self.username_index[request.username] = token
                
                # Obtener lista de peers conectados
                connected_peers = []
                for p in self.peers.values():
                    if p.is_online and p.token != token:
                        peer_info = service_pb2.PeerInfo(
                            peer_id=p.peer_id,
                            username=p.username,
                            url=p.url,
                            port=p.port,
                            is_online=p.is_online,
                            last_seen=int(p.last_seen.timestamp()),
                            file_count=len(p.files)
                        )
                        connected_peers.append(peer_info)
                
                logging.info(f"Nuevo peer registrado: {request.username} con token: {token}")
                return service_pb2.LoginResponse(
                    success=True,
                    token=token,
                    message="Login exitoso",
                    connected_peers=connected_peers
                )
                
        except Exception as e:
            logging.error(f"Error en login: {e}")
            return service_pb2.LoginResponse(
                success=False,
                token="",
                message=f"Error interno del servidor: {str(e)}"
            )
    
    async def Logout(self, request, context):
        """Maneja el logout de un peer"""
        logging.info(f"Solicitud de logout: {request.peer_id}")
        
        try:
            peer = self._validate_token(request.token)
            if not peer:
                return service_pb2.LogoutResponse(
                    success=False,
                    message="Token inválido o peer no encontrado"
                )
            
            with self.db_lock:
                peer.is_online = False
                
            logging.info(f"Peer desconectado: {peer.username}")
            return service_pb2.LogoutResponse(
                success=True,
                message="Logout exitoso"
            )
            
        except Exception as e:
            logging.error(f"Error en logout: {e}")
            return service_pb2.LogoutResponse(
                success=False,
                message=f"Error interno del servidor: {str(e)}"
            )
    
    async def Index(self, request, context):
        """Actualiza el índice de archivos de un peer"""
        logging.info(f"Solicitud de indexado de {len(request.files)} archivos del peer: {request.peer_id}")
        
        try:
            peer = self._validate_token(request.token)
            if not peer:
                return service_pb2.IndexResponse(
                    success=False,
                    message="Token inválido o peer no encontrado",
                    files_indexed=0
                )
            
            with self.db_lock:
                # Actualizar índice de archivos del peer
                peer.files.clear()
                files_indexed = 0
                
                for file_metadata in request.files:
                    peer.files[file_metadata.filename] = {
                        'filename': file_metadata.filename,
                        'file_path': file_metadata.file_path,
                        'file_size': file_metadata.file_size,
                        'file_hash': file_metadata.file_hash,
                        'last_modified': file_metadata.last_modified,
                        'mime_type': file_metadata.mime_type,
                        'tags': list(file_metadata.tags)
                    }
                    files_indexed += 1
            
            logging.info(f"Indexados {files_indexed} archivos para peer: {peer.username}")
            return service_pb2.IndexResponse(
                success=True,
                message="Archivos indexados correctamente",
                files_indexed=files_indexed
            )
            
        except Exception as e:
            logging.error(f"Error en indexado: {e}")
            return service_pb2.IndexResponse(
                success=False,
                message=f"Error interno del servidor: {str(e)}",
                files_indexed=0
            )
    
    async def Search(self, request, context):
        """Busca archivos en la red P2P"""
        logging.info(f"Búsqueda de archivo: '{request.filename}' por peer: {request.peer_id}")
        
        try:
            peer = self._validate_token(request.token)
            if not peer:
                return service_pb2.SearchResponse(
                    success=False,
                    message="Token inválido o peer no encontrado",
                    results=[]
                )
            
            results = []
            search_term = request.filename.lower()
            search_pattern = request.file_pattern.lower() if request.file_pattern else ""
            
            with self.db_lock:
                for token, p in self.peers.items():
                    if not p.is_online or token == request.token:
                        continue
                    
                    # Buscar en los archivos del peer
                    for filename, file_data in p.files.items():
                        match = False
                        
                        # Búsqueda exacta por nombre
                        if search_term and search_term in filename.lower():
                            match = True
                        
                        # Búsqueda por patrón (wildcards básicos)
                        if search_pattern and search_pattern in filename.lower():
                            match = True
                        
                        if match:
                            # Crear metadatos del archivo
                            file_metadata = service_pb2.FileMetadata(
                                filename=file_data['filename'],
                                file_path=file_data['file_path'],
                                file_size=file_data['file_size'],
                                file_hash=file_data['file_hash'],
                                last_modified=file_data['last_modified'],
                                mime_type=file_data['mime_type'],
                                tags=file_data['tags']
                            )
                            
                            # Crear información del peer
                            peer_info = service_pb2.PeerInfo(
                                peer_id=p.peer_id,
                                username=p.username,
                                url=p.url,
                                port=p.port,
                                is_online=p.is_online,
                                last_seen=int(p.last_seen.timestamp()),
                                file_count=len(p.files)
                            )
                            
                            # Crear resultado de búsqueda
                            file_location = service_pb2.FileLocation(
                                file_info=file_metadata,
                                peer_info=peer_info,
                                download_url=f"http://{p.url}:{p.port}/download/{filename}",
                                is_available=True
                            )
                            
                            results.append(file_location)
            
            logging.info(f"Búsqueda completada: {len(results)} resultados encontrados")
            return service_pb2.SearchResponse(
                success=True,
                message=f"Se encontraron {len(results)} resultados",
                results=results
            )
            
        except Exception as e:
            logging.error(f"Error en búsqueda: {e}")
            return service_pb2.SearchResponse(
                success=False,
                message=f"Error interno del servidor: {str(e)}",
                results=[]
            )
    
    async def GetPeerInfo(self, request, context):
        """Obtiene información de peers conectados"""
        try:
            peer = self._validate_token(request.token)
            if not peer:
                return service_pb2.PeerInfoResponse(
                    success=False,
                    peers=[]
                )
            
            peers_info = []
            with self.db_lock:
                for p in self.peers.values():
                    if p.is_online:
                        peer_info = service_pb2.PeerInfo(
                            peer_id=p.peer_id,
                            username=p.username,
                            url=p.url,
                            port=p.port,
                            is_online=p.is_online,
                            last_seen=int(p.last_seen.timestamp()),
                            file_count=len(p.files)
                        )
                        peers_info.append(peer_info)
            
            return service_pb2.PeerInfoResponse(
                success=True,
                peers=peers_info
            )
            
        except Exception as e:
            logging.error(f"Error obteniendo info de peers: {e}")
            return service_pb2.PeerInfoResponse(
                success=False,
                peers=[]
            )
    
    async def Heartbeat(self, request, context):
        """Maneja el heartbeat de los peers para mantener la conexión activa"""
        try:
            peer = self._validate_token(request.token)
            if not peer:
                return service_pb2.HeartbeatResponse(
                    success=False,
                    server_timestamp=int(time.time()),
                    active_peers=0
                )
            
            with self.db_lock:
                active_peers = sum(1 for p in self.peers.values() if p.is_online)
            
            return service_pb2.HeartbeatResponse(
                success=True,
                server_timestamp=int(time.time()),
                active_peers=active_peers
            )
            
        except Exception as e:
            logging.error(f"Error en heartbeat: {e}")
            return service_pb2.HeartbeatResponse(
                success=False,
                server_timestamp=int(time.time()),
                active_peers=0
            )
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del servidor"""
        with self.db_lock:
            total_peers = len(self.peers)
            active_peers = sum(1 for p in self.peers.values() if p.is_online)
            total_files = sum(len(p.files) for p in self.peers.values())
            
            return {
                'total_peers': total_peers,
                'active_peers': active_peers,
                'total_files': total_files,
                'uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0
            }


async def serve():
    """Función principal para iniciar el servidor"""
    try:
        # Cargar configuración
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        config_manager = ConfigManager(config_path)
        
        # Configurar logging
        logging_config = config_manager.get_logging_config()
        setup_logging(logging_config)
        
        logging.info("Iniciando servidor de directorio P2P...")
        
        # Crear servidor gRPC
        server_config = config_manager.get_server_config()
        grpc_server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=server_config.max_workers))
        
        # Agregar servicio
        directory_server = P2PDirectoryServer(config_manager)
        directory_server.start_time = time.time()
        service_pb2_grpc.add_PeerServiceServicer_to_server(directory_server, grpc_server)
        
        # Configurar dirección de escucha
        listen_addr = f"{server_config.host}:{server_config.grpc_port}"
        grpc_server.add_insecure_port(listen_addr)
        
        # Iniciar servidor gRPC
        await grpc_server.start()
        logging.info(f"Servidor gRPC iniciado en {listen_addr}")
        
        # Iniciar API REST en paralelo
        from rest_api import run_rest_api
        rest_task = asyncio.create_task(run_rest_api(directory_server, config_manager))
        
        # Mostrar estadísticas periódicamente
        async def show_stats():
            while True:
                await asyncio.sleep(60)  # Cada minuto
                stats = directory_server.get_stats()
                logging.info(f"Estadísticas: {stats}")
        
        # Iniciar tarea de estadísticas
        stats_task = asyncio.create_task(show_stats())
        
        try:
            # Esperar a que termine cualquiera de los servicios
            await asyncio.gather(
                grpc_server.wait_for_termination(),
                rest_task,
                stats_task
            )
        except KeyboardInterrupt:
            logging.info("Recibida señal de interrupción. Cerrando servidor...")
            await grpc_server.stop(grace=5)
            rest_task.cancel()
            stats_task.cancel()
            
    except Exception as e:
        logging.error(f"Error crítico en el servidor: {e}")
        raise


def main():
    """Punto de entrada principal"""
    print("=== Sistema P2P - Servidor de Directorio ===")
    print("Iniciando servidor...")
    
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()