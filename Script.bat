@echo off
:: ========================================================
::          LANZADOR ÚNICO: eMule + KadGlobe
:: ========================================================

echo [*] Iniciando eMule v0.70b...

:: Cambia esta ruta si tienes el ejecutable de eMule en otro directorio
start "" "C:\Program Files (x86)\eMule\emule.exe"

echo [*] Iniciando Servidor KadGlobe (en ventana minimizada)...
:: Me aseguro de estar en el directorio del proyecto
cd /d "c:\Users\Javi\Coding\KadGlobe"
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
