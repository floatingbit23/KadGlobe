"""
Este servidor local en Python sirve la estructura estática en el puerto 8000
y dispara las tareas de recolección en segundo plano (ideal para Windows/eMule). 
"""

import http.server
import socketserver
import threading
import time
import subprocess
import os
import sys
import json

# Inicializamos el soporte de colores para la terminal de Windows
if os.name == 'nt':
    os.system('')


# COLORES EN TERMINAL
import builtins
_orig_print = builtins.print 

def _color_print(*args, **kwargs):
    text = " ".join(map(str, args))
    stripped_text = text.lstrip()
    
    if stripped_text.startswith("[!]"):
        # Rojo para avisos y errores
        _orig_print(f"\033[91m{text}\033[0m", **kwargs)
    elif stripped_text.startswith("[+]"):
        # Verde para éxitos y resultados positivos
        _orig_print(f"\033[92m{text}\033[0m", **kwargs)
    elif stripped_text.startswith("[*]") or stripped_text.startswith("[i]"):
        # Blanco brillante para información
        _orig_print(f"\033[97m{text}\033[0m", **kwargs)
    else:
        # Por defecto, blanco estándar
        _orig_print(text, **kwargs)

builtins.print = _color_print

# Constantes de configuración
PORT = 8000
POLL_INTERVAL = 30  # Los 30 segundos originales para eMule Windows

class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    def end_headers(self): 
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Expires', '0')
        self.send_header('Pragma', 'no-cache')
        super().end_headers()
    
    def log_message(self, format, *args):
        # Silenciamos los logs de peticiones HTTP para que la terminal esté más limpia
        return

# Importamos el scraper para usar sesiones persistentes (evita miles de logins en eMule)
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from kadglobe_scraper import EMuleWebScraper
from dotenv import load_dotenv

load_dotenv()

def is_emule_running():
    # Detectamos si eMule (Windows) o aMule (Linux) está corriendo para sincronizar el apagado
    try:
        if os.name == 'nt':
            # Comprobamos emule.exe en Windows
            result = subprocess.run(['tasklist', '/FI', 'ImageName eq emule.exe', '/nh'], capture_output=True, text=True, check=False)
            return 'emule.exe' in result.stdout.lower()
        else:
            # Comprobamos amule en Linux
            result = subprocess.run(['pgrep', '-x', 'amule'], capture_output=True, check=False)
            return result.returncode == 0
    except Exception:
        return True # En caso de error en el comando, asumimos que sigue activo

def run_backend_cronjob():
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    python_exe = sys.executable

    print("\n[Server Startup] Leyendo el archivo de eMule nodes.dat...\n")

    try:
        subprocess.run([python_exe, "geolocator.py"], cwd=backend_dir, check=True)
        print("[Server Startup] Nodos base mapeados exitosamente.") 
    except subprocess.CalledProcessError as e:
        print(f"[!] Error ejecutando geolocator en inicio: {e}")

    # Inicializamos el scraper una sola vez (Sesión Persistente)
    admin_pass = os.getenv("ADMIN_PASS", "")
    ip_address = os.getenv("IP_ADDRESS", "127.0.0.1")
    scraper = EMuleWebScraper(host=ip_address, port=4711, password=admin_pass)
    
    # Intento de login inicial
    scraper_ready = scraper.login()

    round = 1 # Contador de rondas
    
    while True: 
        # Comprobamos si eMule sigue abierto antes de procesar
        if not is_emule_running():
            print("\n[!] Se ha detectado que eMule se ha cerrado. Apagando KadGlobe por seguridad...")
            time.sleep(5) # Damos tiempo al usuario para leer el mensaje antes de cerrar la terminal
            os._exit(0)

        try:
            print(f"\n[i] Escaneando estadísticas en vivo del WebUI...")
            
            # Si la sesión se perdió o falló el login, reintentamos el login
            if not scraper_ready:
                scraper_ready = scraper.login()

            # Si la sesión es válida, obtenemos las estadísticas
            if scraper_ready:

                stats = scraper.fetch_kad_stats()

                # Si obtenemos estadísticas, las guardamos en el JSON
                if stats:

                    # Guardamos los resultados
                    output_path = os.path.join(os.path.dirname(__file__), "jsons", "kad_stats.json") # Ruta del archivo JSON
                    os.makedirs(os.path.dirname(output_path), exist_ok=True) # Crea la carpeta si no existe

                    # Escribimos los resultados en el archivo JSON
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(stats, f, indent=4, ensure_ascii=False) # Guardamos los resultados

                else:
                    scraper_ready = False # Marcamos para re-login en la próxima ronda (en 30 segundos)
            

            print(f"\n[i] Ejecutando ICMP Ping Sweep sobre nodos Kademlia...")
            subprocess.run([python_exe, "kad_pinger.py"], cwd=backend_dir, check=False)
            
            print(f"\n[i] Telemetrías actualizadas exitosamente en ronda nº{round}.")
            round += 1
            
        except Exception as e:
            print(f"[!] Error de ejecución en el daemon thread: {e}")
            
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    print("=========================================")
    print("      KADGLOBE REAL-TIME SERVER          ")
    print("=========================================")
    
    # Guardamos el PID en un archivo para que Script.bat pueda matarlo fielmente
    with open("server.pid", "w") as f:
        f.write(str(os.getpid()))

    worker_thread = threading.Thread(target=run_backend_cronjob, daemon=True)
    worker_thread.start()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NoCacheHTTPRequestHandler) as httpd: 
        print(f"[*] Escuchando activamente en el puerto HTTP //localhost:{PORT}") 
        print(f"[*] Visualiza el globo terráqueo navegando a: http://localhost:{PORT}/frontend/")
        print("[*] (Presiona Ctrl+C para finalizar completamente)\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n[*] Recibida orden de apagado. Cerrando el servidor...")
