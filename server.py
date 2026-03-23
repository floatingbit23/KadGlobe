"""
server.py
----------------
Este servidor local en Python cumple un doble propósito vital:
1. Sirve la estructura estática en el puerto 8000 (resolviendo los bloqueos de CORS del navegador al pedir los JSON locales).
2. Ejecuta un Hilo (Thread) en segundo plano que dispara "kadglobe_scraper" y "geolocator" cada 30 segundos usando tu entorno original python.
"""

import http.server
import socketserver
import threading
import time
import subprocess
import os
import sys

# Constantes de configuración
PORT = 8000
POLL_INTERVAL = 5  # La cadencia solicitada de 30 segundos

class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    # Sobrescribimos y desactivamos la caché para que los JSON devuelvan el contenido en tiempo real
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Expires', '0')
        self.send_header('Pragma', 'no-cache')
        super().end_headers()

def run_backend_cronjob():
    """
    Función de ejecución en bucle inquebrantable. Dispara el parseador y el geolocalizador secuencialmente.
    """
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')

    # sys.executable nos garantiza usar el ejecutable exacto e intérprete actual (previniendo problemas de librerías faltantes como python-dotenv o IP2Location)
    python_exe = sys.executable

    # 1. Ejecutar el Geolocalizador UNA ÚNICA VEZ al arrancar el servidor
    # Ya que nodes.dat no sufre cambios dinámicos mientras eMule está encendido.
    print("\n[Server Startup] Leyendo el archivo originario nodes.dat (1 sola vez)...")

    try:
        subprocess.run([python_exe, "geolocator.py"], cwd=backend_dir, check=True)
        print("[Server Startup] Nodos base mapeados exitosamente.")
    except subprocess.CalledProcessError as e:
        print(f"[!] Error ejecutando geolocator en inicio: {e}")

    # 2. Bucle infinito EXCLUSIVO para descargar estadísticas web en vivo
    while True:
        
        print("\n[Server Cronjob] Escaneando estadísticas en vivo del WebUI...")
        
        try:
            # Solo ejecuto el Scraper (Actualiza status, contacts y searches)
            subprocess.run([python_exe, "kadglobe_scraper.py"], cwd=backend_dir, check=True)
            
            print(f"[Server Cronjob] JSON estadístico actualizado. Próxima ronda en {POLL_INTERVAL} segundos.")
        
        except subprocess.CalledProcessError as e:
            print(f"[!] Error de Scraper en el daemon thread: {e}")
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    print("=========================================")
    print("      KADGLOBE REAL-TIME SERVER          ")
    print("=========================================")
    
    # 1. Arranco el subproceso 'Cronjob' como daemon (significa que morirá automáticamente cuando cierre el servidor principal)
    worker_thread = threading.Thread(target=run_backend_cronjob, daemon=True)
    worker_thread.start()

    # 2. Arranco el Servidor HTTP clásico en el hilo principal
    with socketserver.TCPServer(("", PORT), NoCacheHTTPRequestHandler) as httpd:
        print(f"[*] Escuchando activamente en el puerto HTTP //localhost:{PORT}")
        print(f"[*] Visualiza el frontend navegando a: http://localhost:{PORT}/frontend/")
        print("[*] (Presiona Ctrl+C para finalizar completamente)\n")
        try:
            httpd.serve_forever() # El servidor se mantendrá interceptando y proveyendo archivos infinitamente
        except KeyboardInterrupt:
            print("\n[*] Recibida orden de apagado. Cerrando servidor de inmediato...")
