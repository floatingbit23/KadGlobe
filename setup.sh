#!/bin/bash
# ========================================================
#       KadGlobe Provisioning / Configurador Inicial
# ========================================================
# Este script automatiza la instalación de dependencias,
# prepara la estructura de carpetas y gestiona la BBDD.

echo "========================================="
echo "      KadGlobe: Sistema de Configuración"
echo "========================================="

# 1. Comprobar e instalar dependencias del sistema (Solo Linux/Debian)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "[*] 1. Comprobando paquetes del sistema (amule-utils, unzip, pip)..."
    
    # Lista de paquetes necesarios
    PACKAGES=("amule-utils" "unzip" "python3-pip" "curl")
    MISSING_PACKAGES=()

    for pkg in "${PACKAGES[@]}"; do
        if ! dpkg -l | grep -q "^ii  $pkg " &> /dev/null; then
            MISSING_PACKAGES+=("$pkg")
        fi
    done

    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo "[!] Faltan paquetes: ${MISSING_PACKAGES[*]}"
        echo "[i] Se requiere sudo para instalarlos:"
        sudo apt update && sudo apt install -y "${MISSING_PACKAGES[@]}"
    else
        echo "[+] Dependencias del sistema ya instaladas."
    fi
fi

# 2. Instalar dependencias de Python
echo "[*] 2. Instalando librerías de Python con pip (puede tardar un minuto)..."
pip install -r requirements.txt --quiet --user

# 3. Crear carpetas de datos si no existen
echo "[*] 3. Generando estructura de directorios (data/ y jsons/)..."
mkdir -p data jsons

# 4. Gestionar la base de datos IP2Location
DB_FILE="data/IP2LOCATION-LITE-DB5.BIN"

if [ ! -f "$DB_FILE" ]; then
    echo ""
    echo "[!] ATENCIÓN: No se ha detectado la base de datos de geolocalización."
    echo "[i] Para que KadGlobe funcione, necesitas el archivo IP2LOCATION-LITE-DB5.BIN en la carpeta data/."
    echo ""
    echo "--- Pasos para conseguirla (Gratis) ---"
    echo " 1. Regístrate en: https://lite.ip2location.com/"
    echo " 2. Descarga 'DB5-LITE-BIN' (City/Lat/Lng version)."
    echo " 3. Extrae el .ZIP y mueve el archivo .BIN a la carpeta 'data/' de este proyecto."
    echo ""
    
    # Intento de automatización si el usuario tiene Token
    read -p "¿Quieres que intente descargarla ahora por ti automáticamente? (Requiere tu TOKEN de descarga) [s/N]: " download_choice
    
    if [[ "$download_choice" =~ ^[Ss]$ ]]; then
        read -p "Introduce tu Token de descarga: " USER_TOKEN
        
        if [ -z "$USER_TOKEN" ]; then
            echo "[!] No has introducido ningún token. Operación cancelada."
        else
            echo "[*] Descargando y procesando base de datos..."
            
            # Descargamos el ZIP directamente usando el endpoint oficial con el token del usuario
            if command -v curl &> /dev/null; then
                curl -o data/db.zip -L "https://www.ip2location.com/download/?token=${USER_TOKEN}&file=DB5LITEBIN"
            else
                wget -O data/db.zip -L "https://www.ip2location.com/download/?token=${USER_TOKEN}&file=DB5LITEBIN"
            fi
            
            # Extracción del binario (requiere 'unzip' instalado)
            if command -v unzip &> /dev/null; then
                unzip -j data/db.zip "IP2LOCATION-LITE-DB5.BIN" -d data/
                rm data/db.zip
                echo "[+] ¡Base de datos instalada con éxito!"
            else
                echo "[!] 'unzip' no está instalado. El archivo se ha guardado como 'data/db.zip'. Extráelo manualmente."
            fi
        fi
    fi
else
    echo "[+] 4. Base de datos detectada correctamente en $DB_FILE."
fi

# 5. Dar permisos al launcher de Linux
echo "[*] 5. Concediendo permisos de ejecución a launcher.sh..."
chmod +x launcher.sh

echo ""
echo "========================================="
echo "   ¡Configuración completada con éxito!"
echo "   Ya puedes lanzar el proyecto con:"
echo "   ./launcher.sh"
echo "========================================="
echo ""
