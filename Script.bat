@echo off
setlocal
:: ========================================================
::          LANZADOR ÚNICO: eMule + KadGlobe
:: ========================================================

echo [*] Limpiando procesos antiguos de KadGlobe y eMule...
:: Mata el proceso del servidor de Python de forma silenciosa
powershell -Command "Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*server.py*' } | Stop-Process -Force"
:: Mata eMule si está abierto (evita bloqueos de archivos de configuración)
taskkill /F /IM emule.exe /T 2>nul

echo [*] Entorno limpiado e iniciando nuevos sistemas...
echo [*] Iniciando eMule v0.70b...

:: Cambia esta ruta si tienes el ejecutable de eMule en otro directorio
start "" "C:\Program Files (x86)\eMule\emule.exe"

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
