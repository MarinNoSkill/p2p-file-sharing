#!/usr/bin/env python3
"""
Peer - Aplicación principal del peer que integra PServer y PClient
Implementa un nodo completo del sistema P2P con todos los microservicios
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional

# Importar componentes del peer
from PServer.pserver import PServer
from PClient.pclient import PClient
from config import ConfigManager, setup_logging


class P2PPeer:
    """
    Nodo peer completo del sistema P2P.
    Integra PServer (microservicio servidor) y PClient (cliente).
    """
    
    def __init__(self, config_path: str):
        # Cargar configuración
        self.config_manager = ConfigManager(config_path)
        self.peer_config = self.config_manager.get_peer_config()
        self.network_config = self.config_manager.get_peer_network_config()
        self.files_config = self.config_manager.get_files_config()
        self.logging_config = self.config_manager.get_logging_config()
        
        # Configurar logging
        setup_logging(self.logging_config)
        
        # Inicializar componentes
        self.pserver = PServer(self.config_manager)
        self.pclient = PClient(self.config_manager)
        
        # Estado del peer
        self.is_running = False
        self.tasks: List[asyncio.Task] = []
        self.heartbeat_task = None
        
        logging.info(f"Peer {self.peer_config.peer_id} inicializado")
        logging.info(f"PServer en puerto: {self.network_config.rest_port}")
        logging.info(f"Conectará a servidor: {self.network_config.server_url}")
    
    async def start(self):
        """Inicia los servicios básicos del peer (sin login automático)"""
        try:
            logging.info("=== Iniciando Peer P2P ===")
            
            # 1. Crear directorio compartido si no existe
            shared_dir = Path(self.files_config.shared_directory)
            shared_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Directorio compartido: {shared_dir.absolute()}")
            
            # 2. Iniciar PServer en background
            pserver_task = asyncio.create_task(self.pserver.start_server())
            self.tasks.append(pserver_task)
            
            # 3. Marcar como en ejecución
            self.is_running = True
            
            logging.info("🎉 Peer iniciado!")
            logging.info(f"🌐 PServer API: http://{self.network_config.host}:{self.network_config.rest_port}")
            logging.info(f"� Para usar el peer, debe hacer LOGIN primero")
            logging.info(f"💡 Use el comando 'login' en la interfaz CLI")
            
            return True
            
        except Exception as e:
            logging.error(f"Error iniciando peer: {e}")
            return False
    
    async def manual_login(self) -> bool:
        """Realiza login manual al servidor de directorio"""
        if self.pclient.is_connected:
            logging.warning("⚠️ Ya está conectado al servidor")
            return True
        
        logging.info("🔐 Iniciando proceso de login...")
        
        # Conectar al servidor
        if await self.pclient.connect_to_server():
            logging.info("✅ Login exitoso!")
            logging.info(f"👤 Usuario: {self.peer_config.username}")
            logging.info(f"🆔 Peer ID: {self.peer_config.peer_id}")
            
            # Iniciar heartbeat después del login
            if not hasattr(self, 'heartbeat_task') or self.heartbeat_task.done():
                self.heartbeat_task = asyncio.create_task(self.pclient.start_heartbeat_task())
                self.tasks.append(self.heartbeat_task)
            
            return True
        else:
            logging.error("❌ Error en login. Verifique que el servidor esté corriendo")
            return False
    
    async def manual_logout(self):
        """Realiza logout manual del servidor"""
        if not self.pclient.is_connected:
            logging.warning("⚠️ No está conectado al servidor")
            return
        
        logging.info("👋 Realizando logout...")
        await self.pclient.disconnect()
        logging.info("✅ Logout completado")
    
    async def manual_scan_files(self) -> List[Dict]:
        """Escanea archivos manualmente"""
        logging.info("📂 Escaneando archivos compartidos...")
        files = await self.pserver.file_manager.scan_files()
        logging.info(f"✅ Encontrados {len(files)} archivos para compartir")
        
        for file_info in files:
            size_mb = file_info['file_size'] / (1024 * 1024)
            logging.info(f"  📄 {file_info['filename']} ({size_mb:.2f} MB)")
        
        return files
    
    async def manual_index_files(self) -> bool:
        """Indexa archivos manualmente en el servidor"""
        if not self.pclient.is_connected:
            logging.error("❌ Debe hacer login primero")
            return False
        
        logging.info("📊 Indexando archivos en el servidor...")
        files = self.pserver.file_manager.get_files_list()
        
        if not files:
            logging.warning("⚠️ No hay archivos para indexar. Use 'scan' primero")
            return False
        
        success = await self.pclient.index_files(files)
        if success:
            logging.info(f"✅ {len(files)} archivos indexados en el servidor")
            return True
        else:
            logging.error("❌ Error indexando archivos en el servidor")
            return False
    
    async def search_and_download(self, filename: str, save_dir: str = None) -> bool:
        """Busca y descarga un archivo de la red P2P"""
        try:
            logging.info(f"🔍 Buscando archivo: {filename}")
            
            # Buscar archivo en la red
            results = await self.pclient.search_files(filename)
            
            if not results:
                logging.warning(f"❌ Archivo '{filename}' no encontrado en la red")
                return False
            
            logging.info(f"✅ Encontradas {len(results)} ubicaciones para '{filename}'")
            
            # Intentar descargar del primer peer disponible
            for result in results:
                try:
                    # Determinar directorio de descarga
                    if save_dir is None:
                        save_dir = self.files_config.shared_directory
                    
                    save_path = os.path.join(save_dir, filename)
                    
                    # Descargar archivo
                    success = await self.pclient.download_file_from_peer(result, save_path)
                    
                    if success:
                        logging.info(f"✅ Archivo descargado: {save_path}")
                        logging.info(f"📡 Desde peer: {result.peer_info.peer_id} ({result.peer_info.username})")
                        
                        # Nota: No reescaneamos automáticamente, el usuario debe usar 'scan' manualmente
                        return True
                    
                except Exception as e:
                    logging.warning(f"⚠️ Error descargando desde {result.peer_info.peer_id}: {e}")
                    continue
            
            logging.error(f"❌ No se pudo descargar '{filename}' desde ningún peer")
            return False
            
        except Exception as e:
            logging.error(f"Error en búsqueda y descarga: {e}")
            return False
    
    async def list_network_files(self) -> List[Dict]:
        """Lista todos los archivos disponibles en la red"""
        try:
            # Obtener información de peers
            peers = await self.pclient.get_peer_info()
            
            # Para este ejemplo, solo mostramos los peers
            # En una implementación completa, podrías hacer consultas a cada peer
            network_info = []
            
            for peer in peers:
                if peer.peer_id != self.peer_config.peer_id:  # Excluir este peer
                    network_info.append({
                        'peer_id': peer.peer_id,
                        'username': peer.username,
                        'url': peer.url,
                        'port': peer.port,
                        'file_count': peer.file_count,
                        'is_online': peer.is_online
                    })
            
            return network_info
            
        except Exception as e:
            logging.error(f"Error listando archivos de red: {e}")
            return []
    
    async def get_status(self) -> Dict:
        """Obtiene el estado actual del peer"""
        local_files = self.pserver.file_manager.get_files_list()
        known_peers = self.pclient.get_known_peers()
        
        return {
            'peer_id': self.peer_config.peer_id,
            'username': self.peer_config.username,
            'is_running': self.is_running,
            'is_logged_in': self.pclient.is_connected,
            'local_files_count': len(local_files),
            'known_peers_count': len(known_peers),
            'shared_directory': self.files_config.shared_directory,
            'server_url': self.network_config.server_url,
            'pserver_port': self.network_config.rest_port
        }
    
    async def stop(self):
        """Detiene todos los servicios del peer"""
        logging.info("🛑 Deteniendo peer...")
        
        self.is_running = False
        
        # Desconectar del servidor si está conectado
        if self.pclient.is_connected:
            await self.pclient.disconnect()
        
        # Cancelar tareas
        for task in self.tasks:
            task.cancel()
        
        # Esperar a que las tareas terminen
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logging.info("✅ Peer detenido correctamente")


# Interfaz de línea de comandos
class PeerCLI:
    """Interfaz de línea de comandos para el peer"""
    
    def __init__(self, peer: P2PPeer):
        self.peer = peer
    
    async def run_interactive(self):
        """Ejecuta modo interactivo"""
        print("\n=== Sistema P2P - Interfaz de Peer ===")
        print("NOTA: Debe hacer LOGIN antes de usar funciones de red")
        print("\nComandos disponibles:")
        print("  status    - Ver estado del peer")
        print("  login     - Conectar al servidor (REQUERIDO)")
        print("  logout    - Desconectar del servidor")
        print("  scan      - Escanear archivos locales")
        print("  index     - Indexar archivos en el servidor")
        print("  files     - Listar archivos locales")
        print("  network   - Ver peers en la red")
        print("  search <filename> - Buscar archivo en la red")
        print("  download <filename> - Buscar y descargar archivo")
        print("  help      - Mostrar ayuda")
        print("  quit      - Salir")
        print("\nFLUJO RECOMENDADO:")
        print("  1. login     (conectar al servidor)")
        print("  2. scan      (escanear archivos locales)")
        print("  3. index     (indexar en servidor)")
        print("  4. search    (buscar archivos de otros peers)")
        print()
        
        while self.peer.is_running:
            try:
                cmd = input("peer> ").strip().split()
                if not cmd:
                    continue
                
                command = cmd[0].lower()
                
                if command == "quit" or command == "exit":
                    break
                elif command == "status":
                    await self._show_status()
                elif command == "login":
                    await self._do_login()
                elif command == "logout":
                    await self._do_logout()
                elif command == "scan":
                    await self._scan_files()
                elif command == "index":
                    await self._index_files()
                elif command == "files":
                    await self._show_local_files()
                elif command == "network":
                    await self._show_network()
                elif command == "search":
                    if len(cmd) > 1:
                        await self._search_file(cmd[1])
                    else:
                        print("Uso: search <filename>")
                elif command == "download":
                    if len(cmd) > 1:
                        await self._download_file(cmd[1])
                    else:
                        print("Uso: download <filename>")
                elif command == "help":
                    print("\nComandos disponibles:")
                    print("  login, logout, scan, index, status, files, network")
                    print("  search <file>, download <file>, quit")
                    print("\nFlujo típico: login -> scan -> index -> search")
                else:
                    print(f"Comando desconocido: {command}. Use 'help' para ver comandos disponibles")
                    
            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                print(f"Error: {e}")
    
    async def _do_login(self):
        """Realiza login"""
        if self.peer.pclient.is_connected:
            print("✅ Ya está conectado al servidor")
            return
        
        print("🔐 Conectando al servidor...")
        success = await self.peer.manual_login()
        if success:
            print("✅ Login exitoso!")
        else:
            print("❌ Error en login. Verifique que el servidor esté corriendo")
    
    async def _do_logout(self):
        """Realiza logout"""
        await self.peer.manual_logout()
        print("👋 Desconectado del servidor")
    
    async def _scan_files(self):
        """Escanea archivos"""
        print("📂 Escaneando archivos...")
        files = await self.peer.manual_scan_files()
        print(f"✅ Encontrados {len(files)} archivos")
    
    async def _index_files(self):
        """Indexa archivos"""
        if not self.peer.pclient.is_connected:
            print("❌ Debe hacer LOGIN primero")
            return
        
        print("📊 Indexando archivos en el servidor...")
        success = await self.peer.manual_index_files()
        if success:
            print("✅ Archivos indexados correctamente")
        else:
            print("❌ Error indexando archivos")
    
    async def _show_status(self):
        """Muestra el estado del peer"""
        status = await self.peer.get_status()
        print("\n=== Estado del Peer ===")
        for key, value in status.items():
            if key == 'is_logged_in':
                status_icon = "🟢 Conectado" if value else "🔴 Desconectado"
                print(f"  Estado de conexión: {status_icon}")
            else:
                print(f"  {key}: {value}")
        print()
    
    async def _show_local_files(self):
        """Muestra archivos locales"""
        files = self.peer.pserver.file_manager.get_files_list()
        print(f"\n=== Archivos Locales ({len(files)}) ===")
        if not files:
            print("  📭 No hay archivos. Use 'scan' para escanear el directorio compartido")
        else:
            for file_info in files:
                size_mb = file_info['file_size'] / (1024 * 1024)
                print(f"  📄 {file_info['filename']} ({size_mb:.2f} MB)")
        print()
    
    async def _show_network(self):
        """Muestra peers en la red"""
        if not self.peer.pclient.is_connected:
            print("❌ Debe hacer LOGIN primero para ver la red")
            return
        
        network_info = await self.peer.list_network_files()
        print(f"\n=== Peers en la Red ({len(network_info)}) ===")
        if not network_info:
            print("  📭 No hay otros peers conectados")
        else:
            for peer_info in network_info:
                status = "🟢" if peer_info['is_online'] else "🔴"
                print(f"  {status} {peer_info['peer_id']} ({peer_info['username']}) - {peer_info['file_count']} archivos")
        print()
    
    async def _search_file(self, filename):
        """Busca un archivo en la red"""
        if not self.peer.pclient.is_connected:
            print("❌ Debe hacer LOGIN primero para buscar archivos")
            return
        
        results = await self.peer.pclient.search_files(filename)
        print(f"\n=== Búsqueda: '{filename}' ===")
        if results:
            for i, result in enumerate(results, 1):
                size_mb = result.file_size / (1024 * 1024)
                print(f"  {i}. 📄 {result.filename} ({size_mb:.2f} MB)")
                print(f"     🤖 Peer: {result.peer_info.peer_id} ({result.peer_info.username})")
                print(f"     🔗 URL: {result.download_url}")
        else:
            print("  ❌ No se encontraron resultados")
        print()
    
    async def _download_file(self, filename):
        """Descarga un archivo"""
        if not self.peer.pclient.is_connected:
            print("❌ Debe hacer LOGIN primero para descargar archivos")
            return
        
        print(f"\n🔽 Descargando '{filename}'...")
        success = await self.peer.search_and_download(filename)
        if success:
            print(f"✅ Descarga completada: {filename}")
        else:
            print(f"❌ No se pudo descargar: {filename}")
        print()


async def main():
    """Función principal"""
    print("=== Sistema P2P - Peer ===")
    
    # Configurar logging básico
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Determinar archivo de configuración
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    if not os.path.exists(config_path):
        print(f"❌ Archivo de configuración no encontrado: {config_path}")
        print("Uso: python peer.py [config.json]")
        return
    
    # Crear y iniciar peer
    peer = P2PPeer(config_path)
    
    # Manejar señales de interrupción
    def signal_handler(signum, frame):
        print("\n🛑 Interrupción recibida, cerrando peer...")
        asyncio.create_task(peer.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Iniciar peer
        if await peer.start():
            # Crear CLI
            cli = PeerCLI(peer)
            
            # Ejecutar modo interactivo
            await cli.run_interactive()
        else:
            print("❌ No se pudo iniciar el peer")
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupción por teclado")
    
    finally:
        await peer.stop()


if __name__ == "__main__":
    asyncio.run(main())