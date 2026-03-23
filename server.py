"""
Este servidor local en Python cumple un doble propósito vital:
1. Sirve la estructura estática en el puerto 8000 (resolviendo los bloqueos de CORS del navegador al pedir los JSON locales).
2. Ejecuta un Hilo (Thread) en segundo plano que dispara "kadglobe_scraper", "kad_pinger" y "geolocator" cada 30 segundos usando mi entorno original python.
"""

import http.server
import socketserver
import threading
import time
import subprocess
import os
import sys
import builtins

# COLORES EN TERMINAL
_orig_print = builtins.print # 'builtins.print' es la función de impresión incorporada en Python

def _color_print(*args, **kwargs): # 'def _color_print(*args, **kwargs)' define una función llamada _color_print que acepta cualquier número de argumentos posicionales (*args) y argumentos de palabra clave (**kwargs)
    text = " ".join(map(str, args)) # 'text = " ".join(map(str, args))' convierte todos los argumentos posicionales en cadenas de texto y los une con un espacio en blanco
    if text.lstrip().startswith("[!]"): # 'si la cadena de texto comienza con "[!]".
        _orig_print(f"\033[91m{text}\033[0m", **kwargs) # colorea el texto de rojo
    else: # si no comienza con "[!]".
        _orig_print(f"\033[96m{text}\033[0m", **kwargs) # colorea el texto de azul

builtins.print = _color_print # reemplaza la función de impresión incorporada en Python por la función personalizada _color_print


# Constantes de configuración
PORT = 8000
POLL_INTERVAL = 30  # La cadencia solicitada de 30 segundos

# Clase para desactivar la caché de los JSON
class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    # Sobrescribimos y desactivamos la caché para que los JSON devuelvan el contenido en tiempo real
    def end_headers(self): 
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0') # 'Cache-Control' 'no-store' 'no-cache' 'must-revalidate' 'max-age=0' evita que la caché se almacene
        self.send_header('Expires', '0') # 'Expires' '0' significa que la caché expira inmediatamente
        self.send_header('Pragma', 'no-cache') # 'Pragma' 'no-cache' evita que la caché se almacene
        super().end_headers() # 'super().end_headers()' es una llamada al método end_headers() de la clase padre (SimpleHTTPRequestHandler)

# Función de ejecución en bucle inquebrantable. Dispara el parseador y el geolocalizador secuencialmente.
def run_backend_cronjob():

    backend_dir = os.path.join(os.path.dirname(__file__), 'backend') # 'backend_dir' es la ruta al directorio 'backend'

    # 'sys.executable' me garantiza usar el ejecutable exacto e intérprete actual (previniendo problemas de librerías faltantes como python-dotenv o IP2Location)
    python_exe = sys.executable

    # 1º. Ejecutar el Geolocalizador UNA ÚNICA VEZ al arrancar el servidor
    # (Ya que nodes.dat no sufre cambios dinámicos mientras eMule está encendido)

    print("\n[Server Startup] Leyendo el archivo de eMule nodes.dat...\n")

    try:
        subprocess.run([python_exe, "geolocator.py"], cwd=backend_dir, check=True) # 'subprocess.run()' ejecuta el comando especificado en la lista [python_exe, "geolocator.py"] en el directorio especificado por 'cwd' (backend_dir)
        print("[Server Startup] Nodos base mapeados exitosamente.") 

    except subprocess.CalledProcessError as e: # 'subprocess.CalledProcessError' es una excepción que se lanza cuando el comando especificado en 'subprocess.run()' devuelve un código de error distinto de cero
        print(f"[!] Error ejecutando geolocator en inicio: {e}")

    # 2º. Bucle infinito EXCLUSIVO para descargar estadísticas web en vivo

    round = 1 # Inicializo el contador de rondas 
    
    while True: # hasta que se cierre el servidor
        
        try:
            print(f"\n[i] Escaneando estadísticas en vivo del WebUI...")
            subprocess.run([python_exe, "kadglobe_scraper.py"], cwd=backend_dir, check=False)
            
            print(f"\n[i] Ejecutando ICMP Ping Sweep sobre nodos Kademlia...")
            subprocess.run([python_exe, "kad_pinger.py"], cwd=backend_dir, check=False)
            
            print(f"\n[i] Telemetrías actualizadas exitosamente en ronda nº{round}. \n[i] Próxima ronda en {POLL_INTERVAL} segundos.\n")
            
            round += 1 # Incremento el contador de rondas
            
        except subprocess.CalledProcessError as e: # Si ha ocurrido un error de conexión durante la ejecución de los scripts
            print(f"[!] Error de ejecucion en el daemon thread: {e}")
            
        time.sleep(POLL_INTERVAL) # Espero el tiempo especificado en la constante POLL_INTERVAL antes de ejecutar la siguiente ronda


# Inicio del servidor

if __name__ == "__main__":

    print("=========================================")
    print("      KADGLOBE REAL-TIME SERVER          ")
    print("=========================================")
    
    # 1º Arranco el subproceso 'Cronjob' como daemon (proceso en segundo plano que morirá automáticamente cuando cierre el servidor)

    worker_thread = threading.Thread(target=run_backend_cronjob, daemon=True) # 'threading.Thread()' crea un nuevo hilo de ejecución
    worker_thread.start() # Inicio el hilo

    # 2. Arranco el Servidor HTTP clásico en el hilo principal
    with socketserver.TCPServer(("", PORT), NoCacheHTTPRequestHandler) as httpd: # 'socketserver.TCPServer()' crea un servidor TCP que escucha en el puerto especificado por la constante PORT
        print(f"[*] Escuchando activamente en el puerto HTTP //localhost:{PORT}") 
        print(f"[*] Visualiza el frontend navegando a: http://localhost:{PORT}/frontend/")
        print("[*] (Presiona Ctrl+C para finalizar completamente)\n")
        
        try:
            httpd.serve_forever() # El servidor se mantendrá interceptando y proveyendo archivos infinitamente

        except KeyboardInterrupt: # si el usuario presiona Ctrl+C
            print(f"\n[*] Recibida orden de apagado. Cerrando el servidor...")
