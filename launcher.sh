#!/bin/bash
# ========================================================
#          LINUX LAUNCHER: aMule/eMule + KadGlobe
# ========================================================
echo "[*] Iniciando KadGlobe en Linux..."

# 1. Limpieza profunda
pkill -f server_aMule.py 2>/dev/null
pkill -f amuleweb 2>/dev/null
pkill -f amule 2>/dev/null
pkill -f emule 2>/dev/null

# 2. Eliminar archivos de bloqueo
rm -f ~/.aMule/muleLock

echo "[*] Entorno limpiado e iniciando nuevos sistemas..."

# 3. Preparar entorno del servidor
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 4. Leer la contraseña del archivo .env
ADMIN_PASS=$(grep -oP "ADMIN_PASS='?\K[^']*" .env 2>/dev/null)

# 5. Lanzar el cliente
if command -v amule &> /dev/null; then
    echo "[*] Iniciando aMule nativo..."
    amule &
elif command -v wine &> /dev/null && [ -f "$HOME/.wine/drive_c/Program Files (x86)/eMule/emule.exe" ]; then
    echo "[*] Iniciando eMule via Wine..."
    wine "$HOME/.wine/drive_c/Program Files (x86)/eMule/emule.exe" &
else
    echo "[!] No se detecto aMule ni eMule/Wine."
fi

# 6. Lanzar amuleweb independiente
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

# 7. Iniciar el servidor central
echo "[*] Iniciando Servidor KadGlobe..."
python3 server_aMule.py

echo "[+] Sistemas cerrados."
