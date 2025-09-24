#!/bin/bash

# Script para iniciar el sistema P2P completo

echo "=== Iniciando Sistema P2P en Python ==="

# Función para verificar si un puerto está disponible
check_port() {
    local port=$1
    if netstat -an | grep ":$port " > /dev/null 2>&1; then
        echo "Puerto $port está en uso"
        return 1
    fi
    return 0
}

# Función para instalar dependencias
install_deps() {
    echo "Instalando dependencias..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Error instalando dependencias"
        exit 1
    fi
}

# Función para generar archivos protobuf
generate_proto() {
    echo "Generando archivos protobuf..."
    
    # Servidor
    cd Server/src/protobuf
    python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. service.proto
    cd ../../..
    
    # Peer
    cd Peer/src/protobuf
    python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. service.proto
    cd ../../..
    
    echo "Archivos protobuf generados"
}

# Función para crear archivos de ejemplo
create_sample_files() {
    echo "Creando archivos de ejemplo..."
    mkdir -p shared_files shared_files_peer2
    
    echo "Este es un archivo de ejemplo para el sistema P2P" > shared_files/ejemplo1.txt
    echo "Documento de prueba para compartir entre peers" > shared_files/documento.txt
    echo "Archivo de información del sistema distribuido" > shared_files/info.txt
    
    echo "Archivo exclusivo del peer 2" > shared_files_peer2/exclusivo_peer2.txt
    echo "Documento compartido desde el segundo peer" > shared_files_peer2/documento_peer2.txt
    
    echo "Archivos de ejemplo creados"
}

# Función para iniciar en modo desarrollo
start_dev() {
    echo "Iniciando en modo desarrollo..."
    
    # Verificar puertos
    echo "Verificando puertos..."
    check_port 50051 || exit 1
    check_port 8080 || exit 1
    
    # Instalar dependencias
    install_deps
    
    # Generar protobuf
    generate_proto
    
    # Crear archivos de ejemplo
    create_sample_files
    
    # Iniciar servidor
    echo "Iniciando servidor de directorio..."
    cd Server/src
    python server.py &
    SERVER_PID=$!
    cd ../..
    
    echo "Servidor iniciado con PID: $SERVER_PID"
    echo "Servidor gRPC: localhost:50051"
    echo "API REST: http://localhost:8080"
    echo ""
    echo "Para iniciar peers, usa:"
    echo "  ./start.sh peer      # Iniciar peer principal"
    echo "  ./start.sh peer 2    # Iniciar peer secundario"
    echo ""
    echo "Para probar el sistema:"
    echo "  ./start.sh demo      # Demo manual paso a paso"
    echo "  ./start.sh test      # Ejecutar pruebas automatizadas"
    echo ""
    echo "Presiona Ctrl+C para detener el servidor"
    
    # Esperar señal de interrupción
    trap "echo 'Deteniendo servidor...'; kill $SERVER_PID; exit" INT
    wait $SERVER_PID
}

# Función para iniciar peers
start_peer() {
    local peer_num=${2:-1}
    
    if [ "$peer_num" = "2" ]; then
        echo "Iniciando Peer Secundario..."
        cd Peer/src
        python peer.py config_peer2.json &
        PEER_PID=$!
        cd ../..
        echo "Peer 2 iniciado con PID: $PEER_PID en http://localhost:8082"
    else
        echo "Iniciando Peer Principal..."
        cd Peer/src
        python peer.py config.json &
        PEER_PID=$!
        cd ../..
        echo "Peer 1 iniciado con PID: $PEER_PID en http://localhost:8081"
    fi
    
    trap "echo 'Deteniendo peer...'; kill $PEER_PID; exit" INT
    wait $PEER_PID
}

# Función para ejecutar demo manual
run_demo() {
    echo "Iniciando demo manual del sistema P2P..."
    python demo_manual.py
}

# Función para ejecutar pruebas
run_tests() {
    echo "Ejecutando pruebas del sistema..."
    python test_complete_system.py
}

# Función para iniciar con Docker
start_docker() {
    echo "Iniciando con Docker..."
    
    # Construir e iniciar con docker-compose
    docker-compose up --build
}

# Función para mostrar ayuda
show_help() {
    echo "Uso: $0 [OPCIÓN] [NÚMERO]"
    echo ""
    echo "Opciones:"
    echo "  dev       Iniciar servidor de directorio"
    echo "  peer      Iniciar peer principal"
    echo "  peer 2    Iniciar peer secundario"
    echo "  demo      Demo manual interactivo"
    echo "  test      Ejecutar pruebas del sistema"
    echo "  docker    Iniciar con Docker Compose"
    echo "  setup     Solo instalar dependencias y generar protobuf"
    echo "  clean     Limpiar archivos generados"
    echo "  help      Mostrar esta ayuda"
    echo ""
    echo "Ejemplos de uso completo:"
    echo "  1. $0 dev        # Iniciar servidor (terminal 1)"
    echo "  2. $0 demo       # Demo guiado paso a paso"
    echo "  O bien:"
    echo "  1. $0 dev        # Iniciar servidor (terminal 1)"
    echo "  2. $0 peer       # Iniciar peer 1 (terminal 2)"
    echo "  3. $0 peer 2     # Iniciar peer 2 (terminal 3)"
    echo "  4. $0 test       # Probar sistema completo"
    echo ""
    echo "URLs de acceso:"
    echo "  Servidor: http://localhost:8080"
    echo "  Peer 1:   http://localhost:8081"
    echo "  Peer 2:   http://localhost:8082"
}

# Función para setup únicamente
setup_only() {
    echo "Configurando entorno..."
    install_deps
    generate_proto
    create_sample_files
    echo "Setup completado. Ejecuta '$0 dev' para iniciar el servidor"
}

# Función para limpiar archivos generados
clean() {
    echo "Limpiando archivos generados..."
    find . -name "*_pb2.py" -delete
    find . -name "*_pb2_grpc.py" -delete
    find . -name "*.pyc" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    rm -f *.log
    echo "Limpieza completada"
}

# Procesar argumentos
case "${1:-dev}" in
    "dev")
        start_dev
        ;;
    "peer")
        start_peer "$@"
        ;;
    "demo")
        run_demo
        ;;
    "test")
        run_tests
        ;;
    "docker")
        start_docker
        ;;
    "setup")
        setup_only
        ;;
    "clean")
        clean
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo "Opción no válida: $1"
        show_help
        exit 1
        ;;
esac