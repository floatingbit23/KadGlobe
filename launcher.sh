#!/bin/bash
# ========================================================
#          LINUX LAUNCHER: aMule/eMule + KadGlobe
# ========================================================

echo "[*] Iniciando KadGlobe en Linux..."

# Intentar detectar aMule (nativo)
if command -v amule &> /dev/null
then
    echo "[*] Iniciando aMule..."
    amule &
else
    # Si no hay aMule, quizá el usuario tenga eMule instalado vía Wine
    if command -v wine &> /dev/null && [ -f "$HOME/.wine/drive_c/Program Files (x86)/eMule/emule.exe" ]; then
        echo "[*] Iniciando eMule vía Wine..."
        wine "$HOME/.wine/drive_c/Program Files (x86)/eMule/emule.exe" &
    else
        echo "[!] No se detectó aMule ni eMule/Wine. Por favor, arranca tu cliente Kad manualmente."
    fi
fi

echo "[*] Iniciando Servidor KadGlobe..."
# Obtener el directorio del script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Lanzar el servidor en segundo plano
python3 server.py &

echo ""
echo "[*] Abriendo la interfaz web de KadGlobe..."
# Intentar abrir el navegador (compatible con la mayoría de distros)
if command -v xdg-open &> /dev/null
then
    xdg-open http://localhost:8000/frontend/
else
    echo "[i] Por favor, abre tu navegador en: http://localhost:8000/frontend/"
fi

echo "[+] ¡Sistemas lanzados!"
echo ""
