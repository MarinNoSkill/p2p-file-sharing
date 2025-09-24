#!/usr/bin/env python3
"""
PServer - Microservicio servidor del peer con autenticación obligatoria
Requiere login antes de permitir cualquier operación
"""

import os
import asyncio
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, BinaryIO
import logging
import uuid

from fastapi import FastAPI, HTTPException, File, UploadFile, Response, Depends, Header
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles
import uvicorn

# Importar configuración
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import ConfigManager


# Modelos de datos para las APIs
class LoginRequest(BaseModel):
    peer_id: str
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: str = None
    peer_info: dict = None

class IndexRequest(BaseModel):
    force_rescan: bool = True

class IndexResponse(BaseModel):
    success: bool
    message: str
    files_count: int
    files: List[dict] = []

class SearchRequest(BaseModel):
    query: str
    peer_id: str = None

class AuthManager:
    """Gestor de autenticación del peer"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.peer_config = config_manager.get_peer_config()
        self.logged_in = False
        self.session_token = None
        self.login_time = None
    
    def authenticate(self, peer_id: str, username: str, password: str) -> tuple[bool, str, str]:
        """Autentica al peer con las credenciales"""
        if (peer_id == self.peer_config.peer_id and 
            username == self.peer_config.username and 
            password == self.peer_config.password):
            
            # Generar token de sesión
            self.session_token = str(uuid.uuid4())
            self.logged_in = True
            self.login_time = datetime.now()
            
            return True, "Login exitoso", self.session_token
        
        return False, "Credenciales inválidas", None
    
    def verify_token(self, token: str) -> bool:
        """Verifica si el token es válido"""
        return self.logged_in and self.session_token == token
    
    def logout(self):
        """Cierra la sesión"""
        self.logged_in = False
        self.session_token = None
        self.login_time = None


class FileManager:
    """Gestor de archivos compartidos del peer"""
    
    def __init__(self, shared_directory: str):
        self.shared_directory = Path(shared_directory)
        self.shared_directory.mkdir(exist_ok=True)
        self.files_index: Dict[str, Dict] = {}
        
    async def scan_files(self) -> List[Dict]:
        """Escanea el directorio compartido y actualiza el índice"""
        self.files_index.clear()
        files_list = []
        
        try:
            for file_path in self.shared_directory.iterdir():
                if file_path.is_file():
                    file_info = await self._get_file_metadata(file_path)
                    self.files_index[file_info['filename']] = file_info
                    files_list.append(file_info)
        except Exception as e:
            logging.error(f"Error escaneando archivos: {e}")
        
        return files_list
    
    async def _get_file_metadata(self, file_path: Path) -> Dict:
        """Obtiene metadatos de un archivo"""
        stat = file_path.stat()
        
        # Calcular hash MD5
        hash_md5 = hashlib.md5()
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                async for chunk in f:
                    hash_md5.update(chunk)
        except Exception:
            hash_md5.update(b'')
        
        # Obtener tipo MIME
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        return {
            'filename': file_path.name,
            'file_path': str(file_path.relative_to(self.shared_directory)),
            'file_size': stat.st_size,
            'file_hash': hash_md5.hexdigest(),
            'last_modified': int(stat.st_mtime),
            'mime_type': mime_type,
            'tags': []  # Puede expandirse para incluir tags personalizados
        }
    
    def get_file_path(self, filename: str) -> Optional[Path]:
        """Obtiene la ruta completa de un archivo"""
        file_path = self.shared_directory / filename
        if file_path.exists() and file_path.is_file():
            return file_path
        return None
    
    def get_files_list(self) -> List[Dict]:
        """Retorna la lista de archivos disponibles"""
        return list(self.files_index.values())


class PServer:
    """Microservicio servidor del peer con autenticación obligatoria"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.peer_config = config_manager.get_peer_config()
        self.network_config = config_manager.get_peer_network_config()
        self.files_config = config_manager.get_files_config()
        
        # Inicializar gestores
        self.file_manager = FileManager(self.files_config.shared_directory)
        self.auth_manager = AuthManager(config_manager)
        
        # Cliente P2P persistente para mantener conexión
        self.pclient = None
        
        # Crear aplicación FastAPI
        self.app = FastAPI(
            title=f"PServer - {self.peer_config.peer_id}",
            description="Microservicio servidor del peer con autenticación obligatoria",
            version="2.0.0"
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
        
        logging.info(f"PServer inicializado para peer: {self.peer_config.peer_id}")
    
    def _verify_auth(self, authorization: str = Header(None)) -> bool:
        """Verifica la autenticación del usuario"""
        if not authorization:
            raise HTTPException(status_code=401, detail="Token de autorización requerido")
        
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Formato de token inválido. Use 'Bearer <token>'")
        
        token = authorization.replace("Bearer ", "")
        
        if not self.auth_manager.verify_token(token):
            raise HTTPException(status_code=401, detail="Token inválido o sesión expirada")
        
        return True
    
    def _setup_routes(self):
        """Configura las rutas del microservicio - Solo 4 comandos principales"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check - Verificar que el peer está funcionando"""
            files_count = len(self.file_manager.files_index)
            return {
                "status": "healthy",
                "peer_id": self.peer_config.peer_id,
                "username": self.peer_config.username,
                "files_available": files_count,
                "shared_directory": self.files_config.shared_directory,
                "logged_in": self.auth_manager.logged_in,
                "timestamp": datetime.now().isoformat(),
                "commands": [
                    "POST /login - Autenticarse (OBLIGATORIO)",
                    "POST /create - Crear/Subir archivos",
                    "POST /search - Buscar archivos en la red",
                    "GET /download/{filename} - Descargar archivos"
                ]
            }
        
        @self.app.post("/login", response_model=LoginResponse)
        async def login(request: LoginRequest):
            """COMANDO 1: LOGIN - Autenticación obligatoria"""
            success, message, token = self.auth_manager.authenticate(
                request.peer_id, 
                request.username, 
                request.password
            )
            
            if success:
                # Escanear archivos automáticamente al hacer login
                await self.file_manager.scan_files()
                
                # Establecer conexión persistente con el servidor de directorio
                try:
                    from PClient.pclient import PClient
                    self.pclient = PClient(self.config_manager)
                    
                    if await self.pclient.connect_to_server():
                        files = self.file_manager.get_files_list()
                        if files:
                            await self.pclient.index_files(files)
                            index_message = f" ({len(files)} archivos indexados)"
                        else:
                            index_message = " (sin archivos para indexar)"
                        # NO desconectar - mantener conexión persistente
                    else:
                        index_message = " (sin conexión a servidor)"
                        self.pclient = None
                        
                except Exception as e:
                    logging.warning(f"Error indexando en login: {e}")
                    index_message = " (error en indexado automático)"
                    self.pclient = None
                
                peer_info = {
                    "peer_id": self.peer_config.peer_id,
                    "username": self.peer_config.username,
                    "login_time": self.auth_manager.login_time.isoformat(),
                    "shared_directory": self.files_config.shared_directory,
                    "files_available": len(self.file_manager.files_index)
                }
                
                logging.info(f"✅ Login exitoso para peer: {request.peer_id}{index_message}")
                
                return LoginResponse(
                    success=True,
                    message=f"Login exitoso{index_message}",
                    token=token,
                    peer_info=peer_info
                )
            else:
                logging.warning(f"❌ Login fallido para peer: {request.peer_id}")
                raise HTTPException(status_code=401, detail=message)
        
        @self.app.post("/create")
        async def create_files(file: UploadFile = File(...), authenticated: bool = Depends(self._verify_auth)):
            """COMANDO 2: CREAR ARCHIVOS - Subir archivos al peer"""
            try:
                # Verificar que el archivo no esté vacío
                if file.size == 0:
                    raise HTTPException(status_code=400, detail="El archivo está vacío")
                
                # Verificar límite de tamaño (50MB por defecto)
                max_size = 50 * 1024 * 1024  # 50MB
                if file.size > max_size:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"Archivo demasiado grande. Máximo: 50MB"
                    )
                
                # Determinar ruta de destino
                file_path = self.file_manager.shared_directory / file.filename
                
                # Si el archivo existe, sobrescribirlo
                if file_path.exists():
                    logging.info(f"⚠️ Sobrescribiendo archivo existente: {file.filename}")
                
                # Guardar archivo
                async with aiofiles.open(file_path, 'wb') as f:
                    content = await file.read()
                    await f.write(content)
                
                # Actualizar índice automáticamente
                await self.file_manager.scan_files()
                
                # Indexar automáticamente usando conexión persistente
                try:
                    if self.pclient:
                        files = self.file_manager.get_files_list()
                        await self.pclient.index_files(files)
                        index_message = " y indexado en servidor"
                    else:
                        index_message = " (sin conexión a servidor - haz login primero)"
                        
                except Exception as e:
                    logging.warning(f"Error indexando: {e}")
                    index_message = " (error en indexado)"
                
                logging.info(f"⬆️ Archivo creado: {file.filename} por peer autenticado")
                
                return {
                    "success": True,
                    "message": f"Archivo '{file.filename}' creado exitosamente{index_message}",
                    "filename": file.filename,
                    "size": file.size,
                    "peer_id": self.peer_config.peer_id,
                    "total_files": len(self.file_manager.files_index)
                }
                
            except Exception as e:
                logging.error(f"Error creando archivo: {e}")
                raise HTTPException(status_code=500, detail=f"Error creando archivo: {str(e)}")
        
        @self.app.post("/search")
        async def search_files(request: SearchRequest, authenticated: bool = Depends(self._verify_auth)):
            """COMANDO 3: BUSCAR ARCHIVOS - Buscar en la red P2P"""
            try:
                # Verificar que tenemos conexión activa
                if not self.pclient:
                    raise HTTPException(status_code=503, detail="No hay conexión al servidor de directorio. Haz login primero.")
                
                # Realizar búsqueda usando la conexión persistente
                results = await self.pclient.search_files(request.query)
                
                # NO desconectar - mantener conexión persistente
                
                # Formatear resultados para respuesta
                search_results = []
                for result in results:
                    # Construir URL de descarga
                    peer_port = result.peer_info.port
                    download_url = f"http://{result.peer_info.peer_id}:{peer_port}/download/{result.filename}"
                    
                    search_results.append({
                        "filename": result.filename,
                        "file_size": result.file_size,
                        "file_hash": result.file_hash,
                        "peer_info": {
                            "peer_id": result.peer_info.peer_id,
                            "username": result.peer_info.username,
                            "url": result.peer_info.url,
                            "port": result.peer_info.port
                        },
                        "download_url": download_url
                    })
                
                logging.info(f"🔍 Búsqueda '{request.query}' encontró {len(search_results)} resultados")
                
                return {
                    "success": True,
                    "query": request.query,
                    "results_count": len(search_results),
                    "results": search_results,
                    "peer_id": self.peer_config.peer_id
                }
                
            except Exception as e:
                logging.error(f"Error en búsqueda: {e}")
                raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")
        
        @self.app.get("/download/{filename}")
        async def download_file(filename: str, authenticated: bool = Depends(self._verify_auth)):
            """COMANDO 4: DESCARGAR ARCHIVOS - Transferir archivos"""
            file_path = self.file_manager.get_file_path(filename)
            
            if not file_path:
                raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
            # Verificar que el archivo existe
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Archivo no existe en el sistema")
            
            logging.info(f"⬇️ Descargando archivo: {filename} para peer autenticado")
            
            # Determinar tipo MIME
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Retornar archivo
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Peer-ID": self.peer_config.peer_id,
                    "X-Peer-Username": self.peer_config.username,
                    "X-File-Size": str(file_path.stat().st_size)
                }
            )
    
        @self.app.post("/logout")
        async def logout(authenticated: bool = Depends(self._verify_auth)):
            """LOGOUT - Cerrar sesión y desconectar del servidor"""
            try:
                # Desconectar del servidor de directorio si hay conexión activa
                if self.pclient:
                    await self.pclient.disconnect()
                    self.pclient = None
                
                # Cerrar sesión local
                self.auth_manager.logout()
                
                logging.info(f"🔓 Logout exitoso para peer: {self.peer_config.peer_id}")
                
                return {
                    "success": True,
                    "message": "Logout exitoso",
                    "peer_id": self.peer_config.peer_id
                }
                
            except Exception as e:
                logging.error(f"Error en logout: {e}")
                # Limpiar estado de todos modos
                self.pclient = None
                self.auth_manager.logout()
                raise HTTPException(status_code=500, detail=f"Error en logout: {str(e)}")
    
    async def start_server(self):
        """Inicia el servidor PServer"""
        # Escanear archivos al inicio
        await self.file_manager.scan_files()
        
        config = uvicorn.Config(
            self.app,
            host=self.network_config.host,
            port=self.network_config.rest_port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        logging.info(f"Iniciando PServer en {self.network_config.host}:{self.network_config.rest_port}")
        await server.serve()


async def main():
    """Función principal para testing independiente"""
    import sys
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Cargar configuración (con opción de archivo específico)
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    
    config_manager = ConfigManager(config_path)
    
    # Crear y ejecutar PServer
    pserver = PServer(config_manager)
    await pserver.start_server()


if __name__ == "__main__":
    asyncio.run(main())