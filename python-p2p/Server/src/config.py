import json
import yaml
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Configuración del servidor de directorio"""
    host: str
    grpc_port: int
    rest_port: int
    max_workers: int
    

@dataclass
class DatabaseConfig:
    """Configuración de la base de datos"""
    type: str
    cleanup_interval: int
    peer_timeout: int


@dataclass
class LoggingConfig:
    """Configuración del sistema de logging"""
    level: str
    format: str
    file: str


@dataclass
class SecurityConfig:
    """Configuración de seguridad"""
    enable_auth: bool
    token_expiry: int
    max_login_attempts: int


@dataclass
class PeerNetworkConfig:
    """Configuración de red del peer"""
    host: str
    grpc_port: int
    rest_port: int
    server_url: str


@dataclass
class PeerConfig:
    """Configuración básica del peer"""
    peer_id: str
    username: str
    password: str


@dataclass
class FilesConfig:
    """Configuración de archivos compartidos"""
    shared_directory: str
    max_file_size: int
    allowed_extensions: list
    scan_interval: int


@dataclass
class PeersConfig:
    """Configuración de peers amigos"""
    primary_friend: str
    backup_friend: str
    heartbeat_interval: int
    connection_timeout: int


class ConfigManager:
    """Manager para manejar la configuración del sistema"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config_data = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Carga la configuración desde archivo JSON o YAML"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as file:
            if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                return yaml.safe_load(file)
            else:
                return json.load(file)
    
    def reload_config(self) -> None:
        """Recarga la configuración desde el archivo"""
        self.config_data = self._load_config()
        logging.info(f"Configuración recargada desde {self.config_path}")
    
    def get_server_config(self) -> ServerConfig:
        """Obtiene la configuración del servidor"""
        server_data = self.config_data.get('server', {})
        return ServerConfig(
            host=server_data.get('host', '0.0.0.0'),
            grpc_port=server_data.get('grpc_port', 50051),
            rest_port=server_data.get('rest_port', 8080),
            max_workers=server_data.get('max_workers', 10)
        )
    
    def get_database_config(self) -> DatabaseConfig:
        """Obtiene la configuración de la base de datos"""
        db_data = self.config_data.get('database', {})
        return DatabaseConfig(
            type=db_data.get('type', 'memory'),
            cleanup_interval=db_data.get('cleanup_interval', 300),
            peer_timeout=db_data.get('peer_timeout', 120)
        )
    
    def get_logging_config(self) -> LoggingConfig:
        """Obtiene la configuración de logging"""
        log_data = self.config_data.get('logging', {})
        return LoggingConfig(
            level=log_data.get('level', 'INFO'),
            format=log_data.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            file=log_data.get('file', 'app.log')
        )
    
    def get_security_config(self) -> SecurityConfig:
        """Obtiene la configuración de seguridad"""
        sec_data = self.config_data.get('security', {})
        return SecurityConfig(
            enable_auth=sec_data.get('enable_auth', True),
            token_expiry=sec_data.get('token_expiry', 3600),
            max_login_attempts=sec_data.get('max_login_attempts', 3)
        )
    
    def get_peer_config(self) -> PeerConfig:
        """Obtiene la configuración básica del peer"""
        peer_data = self.config_data.get('peer', {})
        return PeerConfig(
            peer_id=peer_data.get('peer_id', 'peer-001'),
            username=peer_data.get('username', 'peer_user'),
            password=peer_data.get('password', 'peer_pass')
        )
    
    def get_peer_network_config(self) -> PeerNetworkConfig:
        """Obtiene la configuración de red del peer"""
        network_data = self.config_data.get('network', {})
        return PeerNetworkConfig(
            host=network_data.get('host', '0.0.0.0'),
            grpc_port=network_data.get('grpc_port', 50052),
            rest_port=network_data.get('rest_port', 8081),
            server_url=network_data.get('server_url', 'localhost:50051')
        )
    
    def get_files_config(self) -> FilesConfig:
        """Obtiene la configuración de archivos"""
        files_data = self.config_data.get('files', {})
        return FilesConfig(
            shared_directory=files_data.get('shared_directory', '../shared_files'),
            max_file_size=files_data.get('max_file_size', 104857600),  # 100MB
            allowed_extensions=files_data.get('allowed_extensions', ['.txt', '.pdf', '.jpg']),
            scan_interval=files_data.get('scan_interval', 60)
        )
    
    def get_peers_config(self) -> PeersConfig:
        """Obtiene la configuración de peers amigos"""
        peers_data = self.config_data.get('peers', {})
        return PeersConfig(
            primary_friend=peers_data.get('primary_friend', ''),
            backup_friend=peers_data.get('backup_friend', ''),
            heartbeat_interval=peers_data.get('heartbeat_interval', 30),
            connection_timeout=peers_data.get('connection_timeout', 10)
        )
    
    def update_config(self, section: str, key: str, value: Any) -> None:
        """Actualiza un valor de configuración"""
        if section not in self.config_data:
            self.config_data[section] = {}
        
        self.config_data[section][key] = value
        
        # Guardar cambios al archivo
        with open(self.config_path, 'w', encoding='utf-8') as file:
            if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                yaml.safe_dump(self.config_data, file, default_flow_style=False)
            else:
                json.dump(self.config_data, file, indent=4)
        
        logging.info(f"Configuración actualizada: {section}.{key} = {value}")


def setup_logging(config: LoggingConfig) -> None:
    """Configura el sistema de logging"""
    logging.basicConfig(
        level=getattr(logging, config.level.upper()),
        format=config.format,
        handlers=[
            logging.FileHandler(config.file),
            logging.StreamHandler()
        ]
    )


# Función para crear configuración por defecto si no existe
def create_default_config(config_path: str, config_type: str = 'server') -> None:
    """Crea un archivo de configuración por defecto"""
    if config_type == 'server':
        default_config = {
            "server": {
                "host": "0.0.0.0",
                "grpc_port": 50051,
                "rest_port": 8080,
                "max_workers": 10
            },
            "database": {
                "type": "memory",
                "cleanup_interval": 300,
                "peer_timeout": 120
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "server.log"
            },
            "security": {
                "enable_auth": True,
                "token_expiry": 3600,
                "max_login_attempts": 3
            }
        }
    else:  # peer config
        default_config = {
            "peer": {
                "peer_id": "peer-001",
                "username": "peer_user",
                "password": "peer_pass"
            },
            "network": {
                "host": "0.0.0.0",
                "grpc_port": 50052,
                "rest_port": 8081,
                "server_url": "localhost:50051"
            },
            "files": {
                "shared_directory": "../shared_files",
                "max_file_size": 104857600,
                "allowed_extensions": [".txt", ".pdf", ".jpg", ".png", ".mp3", ".mp4", ".zip"],
                "scan_interval": 60
            },
            "peers": {
                "primary_friend": "",
                "backup_friend": "",
                "heartbeat_interval": 30,
                "connection_timeout": 10
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "peer.log"
            }
        }
    
    with open(config_path, 'w', encoding='utf-8') as file:
        json.dump(default_config, file, indent=4)
    
    print(f"Archivo de configuración por defecto creado: {config_path}")