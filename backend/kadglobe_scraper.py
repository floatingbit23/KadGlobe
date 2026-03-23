"""
Este módulo actúa como un web scraper para la interfaz web por defecto de eMule.
Su objetivo principal es acceder al estado general de la red Kad.
"""

import requests
import re
import urllib.parse
import os
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import builtins
_orig_print = builtins.print
def _color_print(*args, **kwargs):
    text = " ".join(map(str, args))
    if text.lstrip().startswith("[!]"):
        _orig_print(f"\033[91m{text}\033[0m", **kwargs)
    else:
        _orig_print(f"\033[92m{text}\033[0m", **kwargs)
builtins.print = _color_print

# Cargo las variables de nuestro archivo .env al os.environ para poder utilizarlas
load_dotenv()
 
class EMuleWebScraper:

    # Constructor de la clase
    def __init__(self, host="127.0.0.1", port=4711, password=""): # Inicializo el scraper con los valores por defecto
        self.host = host # Dirección IP de la máquina con eMule
        self.port = port # Puerto de la interfaz web de eMule
        self.password = password # Contraseña de la interfaz web de eMule
        self.base_url = f"http://{host}:{port}" # URL base de la interfaz web de eMule
        self.session_id = None # ID de sesión
        self.session = requests.Session() # Sesión de requests

    # Método para iniciar sesión en la interfaz web de eMule
    def login(self):
        """
        Me autentico en la interfaz web de eMule para obtener el Session ID.
        """

        print(f"\n[*] Iniciando sesión en la WebUI de eMule en {self.base_url}...")

        try:
            # En eMule.tmpl, el formulario de inicio de sesión envía 'p' (password) y 'w=password' 
            payload = {
                "w": "password",
                "p": self.password
            }

            # Envío la solicitud POST a la URL base de la interfaz web de eMule
            response = self.session.post(self.base_url + "/", data=payload, timeout=5)
            
            # eMule habitualmente responde con una etiqueta meta refresh que contiene el identificador de sesión:
            # <meta http-equiv="refresh" content="0;URL=/?ses=12345678">
            match = re.search(r'\?ses=([A-Za-z0-9_]+)', response.text)

            # Si he encontrado el Session ID, lo guardo y muestro un mensaje de éxito
            if match:
                self.session_id = match.group(1)
                print(f"[+] He iniciado sesión correctamente. El Session ID es: {self.session_id}")
                return True
            else:
                print("[!] He fallado al intentar iniciar sesión. No he encontrado el Session ID en la respuesta. Por favor, comprueba que la contraseña sea correcta o el estado de la WebUI.")
                return False
                
        except requests.exceptions.RequestException as e: # Si ha ocurrido un error de conexión durante el login
            print(f"[!] Ha ocurrido un error de conexión durante el login: {e}")
            return False

    # Método para extraer las estadísticas de Kad (página /kad)
    def fetch_kad_stats(self):
        """
        Navego hacia la página de Kad y extraigo el estado actual de la conexión Kad
        y sus estadísticas detalladas de forma robusta.
        """
        if not self.session_id:
            print("[!] No puedo proceder a extraer las estadísticas sin tener una sesión válida.")
            return None
            
        target_url = f"{self.base_url}/?ses={self.session_id}&w=kad"
        
        try:
            response = self.session.get(target_url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            full_text = soup.get_text(separator=' ', strip=True)
            
            # 1. Estado de Conexión (específico de Kad)
            match_status = re.search(r'Kad\s+Status\s+([A-Za-z]+)', full_text, re.IGNORECASE)
            status = match_status.group(1).strip() if match_status else "Desconectado"
            
            # 2. Contacts / Current Searches (formato "Etiqueta Etiqueta Valor Valor")
            match_cs = re.search(r'Contacts\s+Current\s+Searches\s+(\d+)\s+(\d+)', full_text, re.IGNORECASE)
            nodes_count = match_cs.group(1) if match_cs else "0"
            active_searches = match_cs.group(2) if match_cs else "0"

            id_type = "ID Baja (Firewalled)" if "firewall" in status.lower() or "cortafuego" in status.lower() else "ID Alta (Abierto)"

            # 3. Métricas adicionales enriquecidas desde /stats
            extra = self.fetch_stats_kad_data()

            result = {
                "status": status,
                "id_type": id_type,
                "contacts": nodes_count,
                "active_searches": active_searches,
            }
            result.update(extra)
            return result

        except requests.exceptions.RequestException as e:
            print(f"[!] Problema de conexión al extraer información de Kad: {e}")
            return None

    # Método para extraer métricas Kad reales desde la página de Statistics
    def fetch_stats_kad_data(self):
        """
        Scrapeo la página /stats para extraer métricas de red Kad que no aparecen en /kad:
        - Tráfico UDP Kad (paquetes session y acumulado)
        - Porcentaje de nodos Firewalled (UDP / TCP)
        - Clientes descubiertos vía Kad
        - Fuentes encontradas vía Kad en descarga activa
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
            response = self.session.get(target_url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Separador newline para que los patrones multilinea sean más precisos
            lines = soup.get_text(separator='\n', strip=True)

            def find(pattern, text=lines):
                m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                return m.group(1).strip() if m else "0"

            # Tráfico Kad (Session): "Kad Overhead (Packets): 796.52 KB (11.44 k)"
            # Cogemos el número de paquetes (dentro del paréntesis al final)
            kad_session = find(r'Kad Overhead \(Packets\):\s*[\d.,]+\s*\w+\s*\(([\d.,]+\s*\w*)\)', lines)
            
            # Tráfico Kad Acumulado (aparece por segunda vez en el bloque Cumulative)
            all_matches = re.findall(r'Kad Overhead \(Packets\):\s*[\d.,]+\s*\w+\s*\(([\d.,]+\s*\w*)\)', lines, re.IGNORECASE)
            kad_total = all_matches[1].strip() if len(all_matches) >= 2 else kad_session

            # Clientes conectados vía Kad: "Kad: 19 (86.4%)"
            kad_clients_pct = find(r'^Kad:\s*\d+\s*\(([\d.]+)%\)')

            # Firewalled: "UDP: 26.4%"  y "TCP: 28.2%" dentro del bloque "Firewalled (Kad)"
            fw_block = re.search(r'Firewalled \(Kad\)(.*?)Low ID', lines, re.IGNORECASE | re.DOTALL)
            fw_text = fw_block.group(1) if fw_block else ""
            fw_udp = find(r'UDP:\s*([\d.]+)%', fw_text) if fw_text else "0"
            fw_tcp = find(r'TCP:\s*([\d.]+)%', fw_text) if fw_text else "0"

            # Fuentes encontradas vía Kad en descarga activa: "via Kad: 13"
            kad_sources = find(r'via Kad:\s*(\d+)')

            return {
                "kad_overhead_session_pkts": kad_session,
                "kad_overhead_total_pkts": kad_total,
                "kad_clients_pct": kad_clients_pct,
                "kad_firewalled_udp_pct": fw_udp,
                "kad_firewalled_tcp_pct": fw_tcp,
                "kad_sources_found": kad_sources,
            }

        except requests.exceptions.RequestException as e:
            print(f"[!] Problema al scrapear /stats: {e}")
            return defaults


if __name__ == "__main__":
    print("\n--- Scraper Avanzado KadGlobe para eMule ---")
    
    admin_pass = os.getenv("ADMIN_PASS", "")
    ip_address = os.getenv("IP_ADDRESS", "127.0.0.1")

    scraper = EMuleWebScraper(host=ip_address, port=4711, password=admin_pass)

    if scraper.login():
        stats = scraper.fetch_kad_stats()

        if stats:
            print("\n[+] Estadísticas Avanzadas extraídas:")
            for k, v in stats.items():
                print(f"    - {k.replace('_', ' ').title()}: {v}")

            # Guardo la información enriquecida en kad_stats.json
            try:
                output_path = "../jsons/kad_stats.json"
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=4, ensure_ascii=False)

                print(f"\n[+] Datos guardados en '{output_path}'.")
            except Exception as e:
                print(f"[!] Error al guardar JSON: {e}")
