"""
Este módulo es mi 'recolector de datos' o scraper.
Su misión es entrar en la interfaz web de eMule, navegar por sus páginas 
y extraer toda la información que eMule no guarda en archivos fáciles de leer.
"""

import requests
import re
import urllib.parse
import os
import json
import binascii
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Configuro mi sistema de impresión con colores para que los logs sean legibles.
import builtins
_orig_print = builtins.print
def _color_print(*args, **kwargs):
    text = " ".join(map(str, args))
    if text.lstrip().startswith("[!]"):
        _orig_print(f"\033[91m{text}\033[0m", **kwargs)
    else:
        _orig_print(f"\033[92m{text}\033[0m", **kwargs)
builtins.print = _color_print


# Cargo mi archivo .env para leer la contraseña de la WebUI y las rutas de los archivos.
load_dotenv()
 

class EMuleWebScraper:

    def __init__(self, host="127.0.0.1", port=4711, password=""):
        # Inicializo mi scraper con la dirección donde eMule está escuchando.
        self.host = host
        self.port = port
        self.password = password
        self.base_url = f"http://{host}:{port}"
        self.session_id = None 
        # Sesión persistente para evitar re-logins constantes
        self.session = requests.Session()
        self.headers = {
            'Connection': 'close'
        }


    def login(self):

        """
        Este es mi primer paso obligatorio. Envío mi contraseña a eMule 
        y trato de cazar el 'ses_id' de la URL de respuesta.
        """

        print(f"\n[*] Estoy intentando entrar en tu eMule WebUI en {self.base_url}...")

        try:
            # Parámetros universales: p (eMule), pass (amuleweb)
            payload = {
                "w": "password",
                "p": self.password,
                "pass": self.password,
                "submit": "Submit"
            }

            # Lanzo la petición POST para autenticarme usando la sesión
            response = self.session.post(self.base_url + "/", data=payload, headers=self.headers, timeout=5)
            
            # eMule redirige usando un meta-refresh con el ID de sesión. Lo extraigo con esta regex.
            match = re.search(r'\?ses=([A-Za-z0-9_]+)', response.text)
            
            if match: 
                self.session_id = match.group(1) 
                print(f"[+] ¡Logueado perfectamente! ID: {self.session_id}") 
                time.sleep(2) # Pausa tras login para dejar que aMule respire
                return True
            else:
                print("[!] No he podido entrar. Revisa si tu contraseña en el .env es correcta.")
                return False
                
        except requests.exceptions.RequestException as e: # Si hay un error de conexión...
            print(f"[!] No he podido ni conectar con eMule: {e}")
            return False

    def fetch_kad_stats(self):

        """
        Esta función entra en la sección Kad de eMule y  extrae cuántos contactos tengo y si estoy conectado.
        """

        if not self.session_id: # Si no tengo una sesión activa...
            print("[!] No puedo trabajar sin una sesión activa.")
            return None
            
        target_url = f"{self.base_url}/?ses={self.session_id}&w=kad" # Construyo la URL para entrar en la sección Kad.
        
        try:

            response = self.session.get(target_url, headers=self.headers, timeout=5) # Lanzo la petición GET para entrar en la sección Kad.
            soup = BeautifulSoup(response.text, 'html.parser') # Creo un objeto BeautifulSoup para analizar el HTML.
            full_text = soup.get_text(separator=' ', strip=True) # Extraigo todo el texto de la página.
            
            # Busco el estado de Kad (Connected, Firewalled, etc.)
            match_status = re.search(r'Kad\s+Status\s+([A-Za-z]+)', full_text, re.IGNORECASE)
            status = match_status.group(1).strip() if match_status else "Desconectado"
            
            # Extraigo el número de contactos y búsquedas activas.
            match_cs = re.search(r'Contacts\s+Current\s+Searches\s+(\d+)\s+(\d+)', full_text, re.IGNORECASE)
            nodes_count = match_cs.group(1) if match_cs else "0"
            active_searches = match_cs.group(2) if match_cs else "0"

            # Determino si el estado UDP es abierto o tras cortafuegos (exacto para Kad).
            kad_status = "Tras corta Fuegos (Firewalled)" if "firewalled" in status.lower() else "Abierto (Open)"

            # Llamo a mi otra función para sacar métricas de tráfico y Firewalled.
            extra = self.fetch_stats_kad_data()

            # Mi paso maestro: obtener el ID real de 128 bits para el gráfico de K-Buckets.
            local_id = self.fetch_local_kad_id()

            # Empaqueto todo en un diccionario limpio.
            result = {
                "status": status,
                "kad_status": kad_status,
                "contacts": nodes_count,
                "active_searches": active_searches,
                "local_id": local_id
            }

            result.update(extra) # Fusiono los datos extra (tráfico y firewalled) con el resultado principal.
            return result

        except requests.exceptions.RequestException as e:
            print(f"[!] Error extrayendo datos de Kad: {e}")
            return None


    def fetch_local_kad_id(self):

        """
        Esta función lee el archivo 'key_index.dat' (en eMule/config/) para obtener la Kad ID de mi nodo de 128 bits. 
        Sin ese ID, no sabría calcular las distancias XOR en mi frontend.
        """

        # Busco la ruta en el .env. Es donde eMule guarda su identidad de red.
        pref_path = os.getenv("EMULE_KEY_INDEX_PATH", "C:\\Program Files (x86)\\eMule\\config\\key_index.dat")
        
        # Lógica de detección automática para Linux (aMule) si la ruta por defecto no existe.
        if (not os.path.exists(pref_path)) and os.name != "nt":
            amule_pref = os.path.expanduser("~/.aMule/key_index.dat")
            if os.path.exists(amule_pref):
                pref_path = amule_pref

        try:
            if os.path.exists(pref_path):

                with open(pref_path, "rb") as f:

                    # Leo los primeros 16 bytes. Es un hash binario aleatorio único.
                    user_hash = f.read(16)

                    if len(user_hash) == 16:
                        kad_id_hex = binascii.hexlify(user_hash).decode('ascii') # Lo convierto a hexadecimal para que sea legible.
                        print(f"[+] He sacado tu Kad ID real: {kad_id_hex}") # Lo imprimo para verificar que se ha obtenido correctamente.
                        return kad_id_hex
            else:
                print(f"[!] No encuentro el archivo key_index.dat en {pref_path}. Asegúrate de que la ruta en el .env es correcta.")

        except Exception as e:
            print(f"[!] Error crítico leyendo tu identidad: {e}")

        return "0" * 32

    def fetch_stats_kad_data(self):
        """
        Navego a la página de Estadísticas (Statistics) para sacar datos de tráfico UDP 
        y porcentajes de Firewalled que no están en la pestaña principal de Kad.
        """
        defaults = {
            "kad_overhead_session_pkts": "0",
            "kad_overhead_total_pkts": "0",
            "kad_clients_pct": "0",
            "kad_firewalled_udp_pct": "0",
            "kad_firewalled_tcp_pct": "0",
            "kad_sources_found": "0",
        }

        if not self.session_id:
            return defaults

        target_url = f"{self.base_url}/?ses={self.session_id}&w=stats"
        try:
            response = self.session.get(target_url, headers=self.headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            lines = soup.get_text(separator='\n', strip=True)

            # Uso regex para capturar el tráfico 'Overhead' de la sesión de Kad.
            def find(pattern, text=lines):
                m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                return m.group(1).strip() if m else "0"

            kad_session = find(r'Kad Overhead \(Packets\):\s*[\d.,]+\s*\w+\s*\(([\d.,]+\s*\w*)\)', lines)
            
            all_matches = re.findall(r'Kad Overhead \(Packets\):\s*[\d.,]+\s*\w+\s*\(([\d.,]+\s*\w*)\)', lines, re.IGNORECASE)
            kad_total = all_matches[1].strip() if len(all_matches) >= 2 else kad_session

            # Calculo cuántos de tus clientes son estrictamente Kad.
            kad_clients_pct = find(r'^Kad:\s*\d+\s*\(([\d.]+)%\)')

            # Saco los porcentajes de bloqueos de puerto.
            fw_block = re.search(r'Firewalled \(Kad\)(.*?)Low ID', lines, re.IGNORECASE | re.DOTALL)
            fw_text = fw_block.group(1) if fw_block else ""
            fw_udp = find(r'UDP:\s*([\d.]+)%', fw_text) if fw_text else "0"
            fw_tcp = find(r'TCP:\s*([\d.]+)%', fw_text) if fw_text else "0"

            kad_sources = find(r'via Kad:\s*(\d+)')

            return {
                "kad_overhead_session_pkts": kad_session,
                "kad_overhead_total_pkts": kad_total,
                "kad_clients_pct": kad_clients_pct,
                "kad_firewalled_udp_pct": fw_udp,
                "kad_firewalled_tcp_pct": fw_tcp,
                "kad_sources_found": kad_sources,
            }

        except Exception as e:
            print(f"[!] Error en la página de estadísticas: {e}")
            return defaults


# Bloque de ejecución manual (solo si lanzas este archivo solo)

if __name__ == "__main__":
    print("\n--- Estoy iniciando una captura manual de datos ---")
    
    admin_pass = os.getenv("ADMIN_PASS", "")
    ip_address = os.getenv("IP_ADDRESS", "127.0.0.1")

    scraper = EMuleWebScraper(host=ip_address, port=4711, password=admin_pass)

    if scraper.login():
        stats = scraper.fetch_kad_stats()

        if stats:
            try:
                # Calculo la ruta absoluta de la carpeta jsons/ en la raíz del proyecto
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                output_path = os.path.join(project_root, "jsons", "kad_stats.json")
                
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=4, ensure_ascii=False)
                print(f"[+] Todo guardado en '{output_path}'.")
            except Exception as e:
                print(f"[!] No he podido escribir el JSON: {e}")
    else:
        print("[!] No he podido conectar con eMule. Actualizando estado a 'Disconnected'...")
        disconnected_data = {
            "status": "Disconnected",
            "kad_status": "Disconnected",
            "contacts": "0",
            "active_searches": "0",
            "local_id": "Unknown"
        }
        try:
            # Calculo la ruta absoluta de la carpeta jsons/ en la raíz del proyecto
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_path = os.path.join(project_root, "jsons", "kad_stats.json")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(disconnected_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[!] No he podido de actualizar el estado offline: {e}")
