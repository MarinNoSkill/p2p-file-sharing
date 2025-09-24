@echo off
REM Script para iniciar el sistema P2P en Windows

echo === Iniciando Sistema P2P en Python ===

REM Función para verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python no está instalado o no está en el PATH
    pause
    exit /b 1
)

REM Función para instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error instalando dependencias
    pause
    exit /b 1
)

REM Función para generar archivos protobuf
echo Generando archivos protobuf...

REM Servidor
cd Server\src\protobuf
python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. service.proto
cd ..\..\..

REM Peer
cd Peer\src\protobuf
python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. service.proto
cd ..\..\..

echo Archivos protobuf generados

REM Crear archivos de ejemplo
echo Creando archivos de ejemplo...
if not exist shared_files mkdir shared_files
if not exist shared_files_peer2 mkdir shared_files_peer2

echo Este es un archivo de ejemplo para el sistema P2P > shared_files\ejemplo1.txt
echo Documento de prueba para compartir entre peers > shared_files\documento.txt
echo Archivo de información del sistema distribuido > shared_files\info.txt

echo Archivo exclusivo del peer 2 > shared_files_peer2\exclusivo_peer2.txt
echo Documento compartido desde el segundo peer > shared_files_peer2\documento_peer2.txt

echo Archivos de ejemplo creados

REM Procesar argumentos
if "%1"=="docker" goto docker
if "%1"=="setup" goto setup_only
if "%1"=="clean" goto clean
if "%1"=="help" goto show_help
if "%1"=="peer" goto start_peer
if "%1"=="test" goto run_tests
if "%1"=="demo" goto run_demo

REM Modo desarrollo por defecto
:dev
echo Iniciando en modo desarrollo...
echo Iniciando servidor de directorio...
cd Server\src
start "P2P Server" python server.py
cd ..\..

echo Servidor iniciado
echo Servidor gRPC: localhost:50051
echo API REST: http://localhost:8080
echo.
echo Para iniciar peers, usa:
echo   start.bat peer      # Iniciar peer principal
echo   start.bat peer 2    # Iniciar peer secundario
echo.
echo Para probar el sistema:
echo   start.bat demo      # Demo manual paso a paso
echo   start.bat test      # Ejecutar pruebas automatizadas
echo.
echo Presiona cualquier tecla para continuar o Ctrl+C para salir...
pause
goto end

:start_peer
if "%2"=="2" goto start_peer2
echo Iniciando Peer Principal...
cd Peer\src
start "P2P Peer 1" python peer.py config.json
cd ..\..
echo Peer 1 iniciado en http://localhost:8081
goto end

:start_peer2
echo Iniciando Peer Secundario...
cd Peer\src
start "P2P Peer 2" python peer.py config_peer2.json
cd ..\..
echo Peer 2 iniciado en http://localhost:8082
goto end

:run_demo
echo Iniciando demo manual del sistema P2P...
python demo_manual.py
goto end

:run_tests
echo Ejecutando pruebas del sistema...
python test_complete_system.py
goto end

:docker
echo Iniciando con Docker...
docker-compose up --build
goto end

:setup_only
echo Setup completado. Ejecuta 'start.bat' para iniciar el servidor
goto end

:clean
echo Limpiando archivos generados...
for /r %%i in (*_pb2.py) do del "%%i"
for /r %%i in (*_pb2_grpc.py) do del "%%i"
for /r %%i in (*.pyc) do del "%%i"
for /d /r %%i in (__pycache__) do rmdir /s /q "%%i" 2>nul
del *.log 2>nul
echo Limpieza completada
goto end

:show_help
echo Uso: start.bat [OPCIÓN] [NÚMERO]
echo.
echo Opciones:
echo   (ninguna) Iniciar servidor de directorio
echo   peer      Iniciar peer principal
echo   peer 2    Iniciar peer secundario
echo   demo      Demo manual interactivo
echo   test      Ejecutar pruebas del sistema
echo   docker    Iniciar con Docker Compose
echo   setup     Solo instalar dependencias y generar protobuf
echo   clean     Limpiar archivos generados
echo   help      Mostrar esta ayuda
echo.
echo Ejemplos de uso completo:
echo   1. start.bat         # Iniciar servidor
echo   2. start.bat demo    # Demo guiado paso a paso
echo   O bien:
echo   1. start.bat         # Iniciar servidor (terminal 1)
echo   2. start.bat peer    # Iniciar peer 1 (terminal 2)
echo   3. start.bat peer 2  # Iniciar peer 2 (terminal 3)
echo   4. start.bat test    # Probar sistema completo
echo.
echo URLs de acceso:
echo   Servidor: http://localhost:8080
echo   Peer 1:   http://localhost:8081
echo   Peer 2:   http://localhost:8082
goto end

:end