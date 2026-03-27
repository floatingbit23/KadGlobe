#!/bin/bash
# ========================================================
#          LINUX LAUNCHER: aMule/eMule + KadGlobe
# ========================================================
echo "[*] Iniciando KadGlobe en Linux..."

# Función de limpieza al apagar
cleanup() {
    echo ""
    echo "[*] Recibida señal de apagado. Cerrando procesos de forma limpia..."
    # Matamos amuleweb y el servidor Python
    pkill -f server_aMule.py 2>/dev/null
    pkill -f amuleweb 2>/dev/null
    
    # Intentamos cerrar aMule de forma suave primero
    pkill -15 amule 2>/dev/null
    
    echo "[*] Esperando a que aMule guarde archivos temporales..."
    sleep 3
    
    # Si sigue vivo, forzamos cierre
    pkill -9 amule 2>/dev/null
    pkill -f emule 2>/dev/null
    
    # Limpieza de bloqueos
    rm -f ~/.aMule/muleLock
    echo "[+] Todo cerrado. ¡Hasta pronto!"
    exit 0
}

# Capturar Ctrl+C (SIGINT) y llamar a cleanup
trap cleanup SIGINT SIGTERM

# 1. Limpieza inicial (Fiel al sistema server.pid)
if [ -f "server.pid" ]; then
    OLD_PID=$(cat server.pid)
    echo "[*] Limpiando servidor anterior (PID: $OLD_PID)..."
    kill -9 $OLD_PID 2>/dev/null
    rm server.pid
fi

# Fallback en caso de que el PID no exista
pkill -f server_aMule.py 2>/dev/null
pkill -f amuleweb 2>/dev/null
pkill -f amule 2>/dev/null
pkill -f emule 2>/dev/null
rm -f ~/.aMule/muleLock # a veces se queda bloqueado

echo "[*] Entorno limpiado e iniciando nuevos sistemas..."

# 2. Preparar entorno del servidor
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 3. Leer la contraseña del archivo .env
ADMIN_PASS=$(grep -oP "ADMIN_PASS='?\K[^']*" .env 2>/dev/null)

# 4. Lanzar el cliente
if command -v amule &> /dev/null; then
    echo "[*] Iniciando aMule nativo..."
    amule &
elif command -v wine &> /dev/null && [ -f "$HOME/.wine/drive_c/Program Files (x86)/eMule/emule.exe" ]; then
    echo "[*] Iniciando eMule via Wine..."
    wine "$HOME/.wine/drive_c/Program Files (x86)/eMule/emule.exe" &
else
    echo "[!] No se detecto aMule ni eMule/Wine."
fi

# 5. Lanzar amuleweb independiente
echo "[*] Esperando 15s a que aMule arranque su motor EC..."
sleep 15

if command -v amuleweb &> /dev/null; then
    echo "[*] Lanzando amuleweb en puerto 4712..."
    amuleweb -p 4711 -s 4712 -P "$ADMIN_PASS" -A "$ADMIN_PASS" -q &
    sleep 2
    echo "[+] amuleweb iniciado correctamente."
else
    echo "[!] amuleweb no encontrado."
fi

echo ""
echo "[*] Abriendo la interfaz web de KadGlobe..."
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000/frontend/
fi

# 6. Iniciar el servidor central (usamos 'wait' para que el trap funcione correctamente)
echo "[*] Iniciando Servidor KadGlobe..."
python3 server_aMule.py &
SERVER_PID=$!

# Esperamos al proceso del servidor. Si se pulsa Ctrl+C, el trap se encargará de todo.
wait $SERVER_PID
