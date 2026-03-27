@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
:: ========================================================
::       KadGlobe Provisioning / Configurador Inicial
:: ========================================================

echo =========================================
echo       KadGlobe: Sistema de Configuración
echo =========================================

:: 1. Instalar dependencias de Python
echo [*] 1. Instalando librerias necesarias con pip (puede tardar un minuto)...
python -m pip install -r requirements.txt --quiet --user

:: 2. Crear carpetas de datos si no existen
echo [*] 2. Generando estructura de directorios (data/ y jsons/)...
if not exist data mkdir data
if not exist jsons mkdir jsons

:: 3. Gestionar la base de datos IP2Location
set "DB_FILE=data/IP2LOCATION-LITE-DB5.BIN"

if not exist "!DB_FILE!" (
    echo.
    echo [!] ATENCION: No se ha detectado la base de datos de geolocalización.
    echo [i] Necesitas el archivo IP2LOCATION-LITE-DB5.BIN en la carpeta data/.
    echo.
    echo --- Pasos para conseguirla ^(Gratis^) ---
    echo  1. Registrate en: https://lite.ip2location.com/
    echo  2. Descarga 'DB5-LITE-BIN' ^(City/Lat/Lng version^).
    echo  3. Extrae el .ZIP y mueve el archivo .BIN a 'data/'.
    echo.
    set /p "ans=¿Quieres intentar descargarla ahora automaticamente? (Token requerido) [s/N]: "
    if /i "!ans!"=="s" (
        set /p "token=Introduce tu Token de descarga: "
        if "!token!"=="" (
            echo [!] Token vacio. Operación cancelada.
        ) else (
            echo [*] Descargando y procesando base de datos...
            powershell -Command "Invoke-WebRequest -Uri 'https://www.ip2location.com/download/?token=!token!&file=DB5LITEBIN' -OutFile 'data/db.zip'"
            powershell -Command "Expand-Archive -Path 'data/db.zip' -DestinationPath 'data/' -Force"
            del data\db.zip
            del data\LICENSE_LITE.TXT 2>nul
            del data\README_LITE.TXT 2>nul
            echo [+] ¡Base de datos instalada con exito!
        )
    )
) else (
    echo [+] 3. Base de datos detectada correctamente en !DB_FILE!.
)

echo.
echo =========================================
echo    ¡Configuración completada con éxito!
echo    Ya puedes lanzar el proyecto con:
echo    Script.bat
echo =========================================
echo.
pause
