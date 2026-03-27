@echo off
setlocal
chcp 65001 > nul

:: ========================================================
::          LANZADOR ÚNICO: eMule + KadGlobe
:: ========================================================

setlocal enabledelayedexpansion
echo [*] Limpiando servidor KadGlobe anterior...

:: Método 1: Por PID guardado (más preciso)
if exist "server.pid" (
    set /p OLD_PID=<"server.pid"
    taskkill /F /PID !OLD_PID! >nul 2>&1
    del "server.pid"
)

:: Método 2: Por nombre y ruta (fallback de seguridad)
wmic process where "name like 'python%%' and commandline like '%%%%KadGlobe%%%%server.py%%%%'" call terminate > nul 2>&1

echo [*] Comprobando si eMule está abierto...
tasklist /fi "ImageName eq emule.exe" /nh | find /i "emule.exe" > nul

if errorlevel 1 (
    
    echo [*] eMule no está en ejecución. Iniciando eMule...

    :: Cambia esta ruta si tienes el ejecutable de eMule en otro directorio
    start "" "C:\Program Files (x86)\eMule\emule.exe"

    echo [*] Esperando 7 segundos a que eMule levante su servidor WebUI...
    timeout /t 7 /nobreak > nul

) else (
    echo [+] eMule ya está abierto. No es necesario relanzarlo.
)

echo [*] Iniciando Servidor KadGlobe (en ventana minimizada)...
:: Usamos %~dp0 para que el script sea portátil (funcione en cualquier carpeta)
cd /d "%~dp0"
start /min python server.py

echo.
echo [*] Abriendo la interfaz web de KadGlobe en primer plano...
start http://localhost:8000/frontend/

echo [+] ¡Todos los sistemas lanzados con éxito!
echo [i] Puedes visualizar el mapa en: http://localhost:8000/frontend/
echo.

:: La ventana se cerrará sola tras 3 segundos o al pulsar una tecla
timeout /t 3
exit
