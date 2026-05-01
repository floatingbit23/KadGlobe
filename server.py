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
import platform # Detecting Linux Version
import datetime # Para registrar timestamps de los logs
import builtins
 
# 1. Verificación de Versión de Python (Mínimo 3.7 para diccionarios ordenados y f-strings)
if sys.version_info < (3, 7):
    print("\n\033[91m[!] Error Crítico: KadGlobe requiere Python 3.7 o superior.\033[0m")
    print(f"Tu versión actual: {platform.python_version()}\n")
    sys.exit(1)

# Importamos el scraper para usar sesiones persistentes (evita miles de logins en eMule)
from backend.kadglobe_scraper import EMuleWebScraper 
from dotenv import load_dotenv
 
load_dotenv() # Carga las variables de entorno del archivo .env

# Inicializamos el soporte de colores para la terminal de Windows
if os.name == 'nt':
    os.system('')


# COLORES EN TERMINAL
# Evitamos doble sobreescritura si el módulo se importa en otro que ya lo hizo
if not getattr(builtins.print, "_kadglobe_logging", False):
    _orig_print = builtins.print 

    def _color_print(*args, **kwargs):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        text = " ".join(map(str, args))
        stripped_text = text.lstrip()
        
        if stripped_text.startswith("[!]"):
            # Rojo para avisos y errores
            _orig_print(f"{timestamp}\033[91m{text}\033[0m", **kwargs)
        elif stripped_text.startswith("[+]"):
            # Verde para éxitos y resultados positivos
            _orig_print(f"{timestamp}\033[92m{text}\033[0m", **kwargs)
        elif stripped_text.startswith("[*]") or stripped_text.startswith("[i]"):
            # Blanco brillante para información
            _orig_print(f"{timestamp}\033[97m{text}\033[0m", **kwargs)
        else:
            # Por defecto, blanco estándar con timestamp
            _orig_print(f"{timestamp}{text}", **kwargs)

    _color_print._kadglobe_logging = True
    builtins.print = _color_print

def atomic_write_json(path, data):
    """Escribe un JSON de forma segura usando un archivo temporal."""
    temp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, path)
        return True
    except Exception as e:
        print(f"[!] Error en escritura atómica: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

# Constantes de configuración
PORT = int(os.getenv("KADGLOBE_HTTP_PORT", 8000))
POLL_INTERVAL = 30  # Los 30 segundos originales para eMule Windows


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    # Directorios permitidos (protección contra ataque de Directory Traversal)
    ALLOWED_DIRS = ('frontend', 'jsons', 'images')

    def do_GET(self):
        """Sobreescribimos do_GET para añadir validación de ruta."""

        # Proteccion estricta contra Directory Traversal (Local File Inclusion Attack)
        if '..' in self.path:
            self.send_response(400)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'400 Bad Request: Directory Traversal Detected')
            return

        # Resolvemos la ruta solicitada de forma segura
        requested = self.path.split('?')[0].lstrip('/')
        # Permitimos la raíz / (redirige a frontend)
        if not requested or requested == 'frontend' or any(requested.startswith(d + '/') or requested == d for d in self.ALLOWED_DIRS):
            super().do_GET()
        else:
            self.send_response(403)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'403 Forbidden')

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Expires', '0')
        self.send_header('Pragma', 'no-cache')

        # --- SECURITY HEADERS ---
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')

        # CSP: permite solo recursos locales y CDNs conocidos (unpkg, jsdelivr)
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https://unpkg.com https://cdn.jsdelivr.net https://flagcdn.com; "
            "connect-src 'self' https://unpkg.com; "
            "worker-src 'self' blob:; "
            "frame-ancestors 'none'"
        )
        super().end_headers()

    def log_message(self, format, *args):
        # Silenciamos los logs de peticiones HTTP para que la terminal esté más limpia
        return


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
    webui_port = int(os.getenv("WEBUI_PORT", 4711))
    scraper = EMuleWebScraper(host=ip_address, port=webui_port, password=admin_pass)
    
    # Intento de login inicial
    scraper_ready = scraper.login()
    client_version = "eMule"

    # Se informa de la versión del cliente eMule.
    if scraper_ready:
        client_version = scraper.fetch_emule_version()
        print(f"[+] Versión del cliente: {client_version}")

    round_num = 1 # Contador de rondas
    
    while True: 
        # Comprobamos si eMule sigue abierto antes de procesar
        if not is_emule_running():
            print("\n[!] Se ha detectado que eMule se ha cerrado. Apagando KadGlobe por seguridad...")
            time.sleep(5) # Damos tiempo al usuario para leer el mensaje antes de cerrar la terminal
            os._exit(0)

        try:
            success = True
            print("\n[i] Escaneando estadísticas en vivo del WebUI...")
            
            # Si la sesión se perdió o falló el login, reintentamos el login
            if not scraper_ready:
                scraper_ready = scraper.login()

            # Si la sesión es válida, obtenemos las estadísticas
            if scraper_ready:
                stats = scraper.fetch_kad_stats()

                # Si obtenemos estadísticas, las guardamos en el JSON
                if stats:
                    # Guardamos los resultados de forma atómica
                    output_path = os.path.join(os.path.dirname(__file__), "jsons", "kad_stats.json")
                    if not atomic_write_json(output_path, stats):
                        success = False
                else:
                    scraper_ready = False # Marcamos para re-login en la próxima ronda
                    success = False
            else:
                success = False
            

            print("\n[i] Ejecutando Kad UDP Probe sobre nodos Kademlia...")
            pinger_proc = subprocess.run([python_exe, "kad_udp_pinger.py"], cwd=backend_dir, check=False)
            if pinger_proc.returncode != 0:
                success = False
            
            if success:
                print(f"\n[+] Telemetrías actualizadas exitosamente en ronda nº{round_num} ({client_version}). Próxima medición en {POLL_INTERVAL} segundos...")
            else:
                print(f"\n[!] La ronda nº{round_num} finalizó con errores parciales. Se reintentará en {POLL_INTERVAL} segundos...")
            
            round_num += 1
            
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
            print("\n[*] Recibida orden de apagado. Cerrando el servidor...")
