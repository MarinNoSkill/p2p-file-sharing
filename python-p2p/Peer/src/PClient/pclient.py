#!/usr/bin/env python3
"""
PClient - Cliente del peer para comunicación con servidor de directorio y otros peers
Maneja autenticación, búsqueda de archivos y comunicación peer-to-peer
"""

import asyncio
import grpc
import requests
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Importar módulos protobuf
import os
import sys

# Agregar el directorio protobuf al path
protobuf_path = os.path.join(os.path.dirname(__file__), '..', 'protobuf')
sys.path.append(protobuf_path)

try:
    import service_pb2
    import service_pb2_grpc
except ImportError as e:
    print(f"Error: No se encontraron los archivos protobuf generados: {e}")
    print("Ejecuta: python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. protobuf/service.proto")
    sys.exit(1)

# Importar configuración
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import ConfigManager


@dataclass
class PeerInfo:
    """Información de un peer"""
    peer_id: str
    username: str
    url: str
    port: int
    is_online: bool
    file_count: int


@dataclass
class FileLocation:
    """Información de ubicación de un archivo"""
    filename: str
    file_size: int
    file_hash: str
    peer_info: PeerInfo
    download_url: str


class PClient:
    """Cliente del peer para comunicación con el sistema P2P"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.peer_config = config_manager.get_peer_config()
        self.network_config = config_manager.get_peer_network_config()
        self.files_config = config_manager.get_files_config()
        self.peers_config = config_manager.get_peers_config()
        
        # Estado del cliente
        self.token: Optional[str] = None
        self.is_connected: bool = False
        self.server_channel: Optional[grpc.Channel] = None
        self.server_stub: Optional[service_pb2_grpc.PeerServiceStub] = None
        
        # Cache de peers conocidos
        self.known_peers: Dict[str, PeerInfo] = {}
        
        logging.info(f"PClient inicializado para peer: {self.peer_config.peer_id}")
    
    async def connect_to_server(self) -> bool:
        """Conecta al servidor de directorio principal"""
        try:
            # Crear canal gRPC
            self.server_channel = grpc.aio.insecure_channel(self.network_config.server_url)
            self.server_stub = service_pb2_grpc.PeerServiceStub(self.server_channel)
            
            # Intentar login
            success = await self.login()
            if success:
                self.is_connected = True
                logging.info(f"Conectado exitosamente al servidor: {self.network_config.server_url}")
                return True
            else:
                logging.error("Falló el login al servidor")
                return False
                
        except Exception as e:
            logging.error(f"Error conectando al servidor: {e}")
            return False
    
    async def connect_to_peer_friend(self) -> bool:
        """Conecta a un peer amigo si el servidor principal no está disponible"""
        friends = [self.peers_config.primary_friend, self.peers_config.backup_friend]
        
        for friend_url in friends:
            if not friend_url:
                continue
                
            try:
                logging.info(f"Intentando conectar a peer amigo: {friend_url}")
                
                # Intentar conectar vía gRPC
                channel = grpc.aio.insecure_channel(friend_url)
                stub = service_pb2_grpc.PeerServiceStub(channel)
                
                # Test de conexión
                request = service_pb2.HeartbeatRequest(
                    token="",
                    peer_id=self.peer_config.peer_id,
                    timestamp=int(time.time())
                )
                
                response = await stub.Heartbeat(request)
                if response.success:
                    logging.info(f"Conectado a peer amigo: {friend_url}")
                    # Aquí podrías implementar lógica adicional para usar el peer amigo
                    return True
                    
            except Exception as e:
                logging.warning(f"No se pudo conectar a peer amigo {friend_url}: {e}")
        
        return False
    
    async def login(self) -> bool:
        """Realiza login en el servidor de directorio"""
        try:
            request = service_pb2.LoginRequest(
                username=self.peer_config.username,
                password=self.peer_config.password,
                peer_url=f"{self.network_config.host}",
                port=self.network_config.rest_port,
                peer_id=self.peer_config.peer_id
            )
            
            response = await self.server_stub.Login(request)
            
            if response.success:
                self.token = response.token
                
                # Actualizar cache de peers conocidos
                for peer_proto in response.connected_peers:
                    peer_info = PeerInfo(
                        peer_id=peer_proto.peer_id,
                        username=peer_proto.username,
                        url=peer_proto.url,
                        port=peer_proto.port,
                        is_online=peer_proto.is_online,
                        file_count=peer_proto.file_count
                    )
                    self.known_peers[peer_info.peer_id] = peer_info
                
                logging.info(f"Login exitoso. Token: {self.token}")
                logging.info(f"Peers conocidos: {len(self.known_peers)}")
                return True
            else:
                logging.error(f"Login fallido: {response.message}")
                return False
                
        except Exception as e:
            logging.error(f"Error durante login: {e}")
            return False
    
    async def logout(self) -> bool:
        """Realiza logout del servidor de directorio"""
        if not self.token:
            return True
        
        try:
            request = service_pb2.LogoutRequest(
                token=self.token,
                peer_id=self.peer_config.peer_id
            )
            
            response = await self.server_stub.Logout(request)
            
            if response.success:
                logging.info("Logout exitoso")
                self.token = None
                self.is_connected = False
                return True
            else:
                logging.error(f"Logout fallido: {response.message}")
                return False
                
        except Exception as e:
            logging.error(f"Error durante logout: {e}")
            return False
    
    async def index_files(self, files_metadata: List[Dict]) -> bool:
        """Envía el índice de archivos al servidor"""
        if not self.token:
            logging.error("No hay token válido para indexar archivos")
            return False
        
        try:
            # Convertir metadatos a protobuf
            proto_files = []
            for file_data in files_metadata:
                proto_file = service_pb2.FileMetadata(
                    filename=file_data['filename'],
                    file_path=file_data['file_path'],
                    file_size=file_data['file_size'],
                    file_hash=file_data['file_hash'],
                    last_modified=file_data['last_modified'],
                    mime_type=file_data['mime_type'],
                    tags=file_data.get('tags', [])
                )
                proto_files.append(proto_file)
            
            request = service_pb2.IndexRequest(
                token=self.token,
                peer_id=self.peer_config.peer_id,
                files=proto_files
            )
            
            response = await self.server_stub.Index(request)
            
            if response.success:
                logging.info(f"Archivos indexados exitosamente: {response.files_indexed}")
                return True
            else:
                logging.error(f"Error indexando archivos: {response.message}")
                return False
                
        except Exception as e:
            logging.error(f"Error durante indexado: {e}")
            return False
    
    async def search_files(self, filename: str, pattern: str = "") -> List[FileLocation]:
        """Busca archivos en la red P2P"""
        if not self.token:
            logging.error("No hay token válido para buscar archivos")
            return []
        
        try:
            request = service_pb2.SearchRequest(
                token=self.token,
                peer_id=self.peer_config.peer_id,
                filename=filename,
                file_pattern=pattern
            )
            
            response = await self.server_stub.Search(request)
            
            if response.success:
                results = []
                for result in response.results:
                    peer_info = PeerInfo(
                        peer_id=result.peer_info.peer_id,
                        username=result.peer_info.username,
                        url=result.peer_info.url,
                        port=result.peer_info.port,
                        is_online=result.peer_info.is_online,
                        file_count=result.peer_info.file_count
                    )
                    
                    file_location = FileLocation(
                        filename=result.file_info.filename,
                        file_size=result.file_info.file_size,
                        file_hash=result.file_info.file_hash,
                        peer_info=peer_info,
                        download_url=result.download_url
                    )
                    results.append(file_location)
                
                logging.info(f"Búsqueda completada: {len(results)} resultados")
                return results
            else:
                logging.error(f"Error en búsqueda: {response.message}")
                return []
                
        except Exception as e:
            logging.error(f"Error durante búsqueda: {e}")
            return []
    
    async def get_peer_info(self) -> List[PeerInfo]:
        """Obtiene información de todos los peers conectados"""
        if not self.token:
            logging.error("No hay token válido para obtener info de peers")
            return []
        
        try:
            request = service_pb2.PeerInfoRequest(
                token=self.token,
                peer_id=self.peer_config.peer_id
            )
            
            response = await self.server_stub.GetPeerInfo(request)
            
            if response.success:
                peers = []
                for peer_proto in response.peers:
                    peer_info = PeerInfo(
                        peer_id=peer_proto.peer_id,
                        username=peer_proto.username,
                        url=peer_proto.url,
                        port=peer_proto.port,
                        is_online=peer_proto.is_online,
                        file_count=peer_proto.file_count
                    )
                    peers.append(peer_info)
                    # Actualizar cache
                    self.known_peers[peer_info.peer_id] = peer_info
                
                logging.info(f"Información de peers obtenida: {len(peers)} peers")
                return peers
            else:
                logging.error("Error obteniendo información de peers")
                return []
                
        except Exception as e:
            logging.error(f"Error obteniendo info de peers: {e}")
            return []
    
    async def download_file_from_peer(self, file_location: FileLocation, save_path: str) -> bool:
        """Descarga un archivo directamente de otro peer"""
        try:
            logging.info(f"Descargando {file_location.filename} desde {file_location.peer_info.peer_id}")
            
            # Usar requests para descargar el archivo vía HTTP
            response = requests.get(file_location.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Guardar archivo
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logging.info(f"Archivo descargado exitosamente: {save_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error descargando archivo: {e}")
            return False
    
    async def send_heartbeat(self) -> bool:
        """Envía heartbeat al servidor para mantener la conexión activa"""
        if not self.token:
            return False
        
        try:
            request = service_pb2.HeartbeatRequest(
                token=self.token,
                peer_id=self.peer_config.peer_id,
                timestamp=int(time.time())
            )
            
            response = await self.server_stub.Heartbeat(request)
            
            if response.success:
                logging.debug(f"Heartbeat exitoso. Peers activos: {response.active_peers}")
                return True
            else:
                logging.warning("Heartbeat falló")
                return False
                
        except Exception as e:
            logging.error(f"Error en heartbeat: {e}")
            return False
    
    async def start_heartbeat_task(self):
        """Inicia tarea periódica de heartbeat"""
        while self.is_connected:
            await self.send_heartbeat()
            await asyncio.sleep(self.peers_config.heartbeat_interval)
    
    async def disconnect(self):
        """Desconecta del servidor y limpia recursos"""
        if self.is_connected:
            await self.logout()
        
        if self.server_channel:
            await self.server_channel.close()
        
        self.known_peers.clear()
        logging.info("Desconectado del sistema P2P")
    
    def get_known_peers(self) -> Dict[str, PeerInfo]:
        """Retorna el cache de peers conocidos"""
        return self.known_peers.copy()


# Funciones de utilidad para testing
async def test_pclient():
    """Función de prueba para PClient"""
    logging.basicConfig(level=logging.INFO)
    
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    config_manager = ConfigManager(config_path)
    
    client = PClient(config_manager)
    
    # Conectar al servidor
    if await client.connect_to_server():
        print("✅ Conexión al servidor exitosa")
        
        # Obtener información de peers
        peers = await client.get_peer_info()
        print(f"✅ Peers conectados: {len(peers)}")
        
        # Buscar archivos
        results = await client.search_files("ejemplo")
        print(f"✅ Resultados de búsqueda: {len(results)}")
        
        # Desconectar
        await client.disconnect()
        print("✅ Desconexión exitosa")
    else:
        print("❌ No se pudo conectar al servidor")


if __name__ == "__main__":
    asyncio.run(test_pclient())