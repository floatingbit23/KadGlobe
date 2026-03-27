"""
Scraper especializado para amuleweb (Linux).
Adaptado a las plantillas PHP de /usr/share/amule/webserver/default/
que generan un HTML completamente distinto al de eMule para Windows.

URLs clave de amuleweb:
  - Login:       POST / con campo 'pass'
  - Kad page:    /amuleweb-main-kad.php
  - Stats page:  /amuleweb-main-stats.php
  - Stats tree:  /stats_tree.php  (iframe con el arbol de estadisticas)
  - Stats bar:   /stats.php       (iframe con estado Kad/Ed2k)
"""

import requests
import re
import os
import json
import time
import binascii
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Colores en terminal
import builtins
_orig_print = builtins.print
def _color_print(*args, **kwargs):
    text = " ".join(map(str, args))
    if text.lstrip().startswith("[!]"):
        _orig_print(f"\033[91m{text}\033[0m", **kwargs)
    else:
        _orig_print(f"\033[92m{text}\033[0m", **kwargs)
builtins.print = _color_print

load_dotenv()


class AMuleWebScraper:
    """
    Scraper adaptado al HTML que genera amuleweb.
    Usa cookies de sesion en vez de ?ses= en la URL.
    """

    def __init__(self, host="127.0.0.1", port=4712, password=""):
        self.host = host
        self.port = port
        self.password = password
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.logged_in = False

    def login(self):
        """
        amuleweb usa un formulario con campo 'pass' (no 'p').
        Tras un login exitoso, redirige a amuleweb-main-dload.php.
        La sesion se mantiene mediante cookies.
        """
        print(f"\n[*] Conectando con amuleweb en {self.base_url}...")

        try:
            payload = {
                "pass": self.password
            }

            response = self.session.post(
                self.base_url + "/",
                data=payload,
                headers={'Connection': 'close'},
                timeout=10,
                allow_redirects=True
            )

            # Si el login es exitoso, amuleweb redirige a la pagina principal
            # y la respuesta contiene el menu de navegacion (no el formulario de login)
            if "amuleweb-main-dload.php" in response.text or "amuleweb-main-kad.php" in response.text:
                self.logged_in = True
                print("[+] Logueado correctamente en amuleweb.")
                time.sleep(1)
                return True

            # Tambien puede haber un redirect via meta-refresh o 302
            if response.url and "login" not in response.url.lower():
                self.logged_in = True
                print(f"[+] Logueado correctamente en amuleweb (redirect a {response.url}).")
                time.sleep(1)
                return True

            # Si seguimos en la pagina de login, la contrasena es incorrecta
            if "Enter password" in response.text or 'name="pass"' in response.text:
                print("[!] Contrasena incorrecta para amuleweb. Revisa ADMIN_PASS en tu .env")
                return False

            # Fallback: si la respuesta no contiene el formulario de login, asumir exito
            if response.status_code == 200 and 'name="pass"' not in response.text:
                self.logged_in = True
                print("[+] Logueado correctamente en amuleweb.")
                time.sleep(1)
                return True

            print("[!] No he podido entrar en amuleweb. Respuesta inesperada.")
            return False

        except requests.exceptions.RequestException as e:
            print(f"[!] No he podido conectar con amuleweb: {e}")
            return False

    def fetch_kad_stats(self):
        """
        Recopila estadisticas de Kad de tres fuentes de amuleweb:
        1. /amuleweb-main-kad.php -> Grafico de nodos
        2. /stats.php -> Estado Kad (Connected/Disconnected/Firewalled)
        3. /stats_tree.php -> Arbol completo de estadisticas
        """
        if not self.logged_in:
            print("[!] No puedo trabajar sin una sesion activa.")
            return None

        try:
            # 1. Obtener estado de Kad desde el iframe /stats.php
            kad_status_data = self._fetch_kad_status()

            # 2. Obtener estadisticas detalladas desde /stats_tree.php
            stats_tree_data = self._fetch_stats_tree()

            # 3. Obtener el Kad ID local
            local_id = self.fetch_local_kad_id()

            # Empaquetar todo
            result = {
                "status": kad_status_data.get("status", "Unknown"),
                "kad_status": kad_status_data.get("kad_status", "Unknown"),
                "contacts": stats_tree_data.get("contacts", "0"),
                "active_searches": "0",
                "local_id": local_id,
            }

            # Anadir datos extra del arbol de estadisticas
            result.update(stats_tree_data.get("extra", {}))

            return result

        except Exception as e:
            print(f"[!] Error recopilando estadisticas: {e}")
            return None

    def _fetch_kad_status(self):
        """
        Lee el iframe /stats.php que contiene el estado de Kad.
        El template PHP usa $stats["kad_connected"] y $stats["kad_firewalled"].
        """
        defaults = {"status": "Disconnected", "kad_status": "Disconnected"}

        try:
            response = self.session.get(
                self.base_url + "/stats.php",
                headers={'Connection': 'close'},
                timeout=5
            )
            text = response.text

            # El template genera texto como:
            #   "Kad : Connected(OK)" o "Kad : Connected(Firewalled)" o "Kad : Disconnected"
            soup = BeautifulSoup(text, 'html.parser')
            full_text = soup.get_text(separator=' ', strip=True)

            # Buscar estado de Kad
            kad_match = re.search(r'Kad\s*:\s*(\w+)', full_text, re.IGNORECASE)
            if kad_match:
                raw_status = kad_match.group(1).strip()

                if raw_status.lower() == "connected":
                    # Verificar si es firewalled
                    if "Firewalled" in full_text:
                        return {"status": "Connected", "kad_status": "Tras cortafuegos (Firewalled)"}
                    else:
                        return {"status": "Connected", "kad_status": "Abierto (Open)"}
                elif raw_status.lower() == "connecting":
                    return {"status": "Connecting", "kad_status": "Conectando..."}

            return defaults

        except Exception as e:
            print(f"[!] Error leyendo estado Kad: {e}")
            return defaults

    def _fetch_stats_tree(self):
        """
        Lee el iframe /stats_tree.php que contiene el arbol completo de estadisticas.
        El template PHP usa amule_load_vars("stats_tree") y genera un arbol HTML
        con nodos como:
          - Kad Nodes (Total): X
          - Kad Overhead (Packets): ...
          - Firewalled (Kad)
        """
        defaults = {
            "contacts": "0",
            "extra": {
                "kad_overhead_session_pkts": "0",
                "kad_overhead_total_pkts": "0",
                "kad_clients_pct": "0",
                "kad_firewalled_udp_pct": "0",
                "kad_firewalled_tcp_pct": "0",
                "kad_sources_found": "0",
            }
        }

        try:
            response = self.session.get(
                self.base_url + "/stats_tree.php",
                headers={'Connection': 'close'},
                timeout=5
            )
            soup = BeautifulSoup(response.text, 'html.parser')
            full_text = soup.get_text(separator='\n', strip=True)

            def find(pattern, text=full_text):
                m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                return m.group(1).strip() if m else "0"

            # Contactos Kad (nodos conocidos)
            contacts = find(r'Kad\s+Nodes\s*\(Total\)\s*:\s*(\d+)')
            if contacts == "0":
                contacts = find(r'Nodes\s*:\s*(\d+)')

            # Overhead de Kad en paquetes
            kad_session = find(r'Kad Overhead \(Packets\):\s*[\d.,]+\s*\w*\s*\(([\d.,]+\s*\w*)\)')
            all_matches = re.findall(r'Kad Overhead \(Packets\):\s*[\d.,]+\s*\w*\s*\(([\d.,]+\s*\w*)\)', full_text, re.IGNORECASE)
            kad_total = all_matches[1].strip() if len(all_matches) >= 2 else kad_session

            # Porcentaje de clientes Kad
            kad_clients_pct = find(r'Kad:\s*\d+\s*\(([\d.]+)%\)')

            # Firewalled
            fw_block = re.search(r'Firewalled \(Kad\)(.*?)(?:Low ID|$)', full_text, re.IGNORECASE | re.DOTALL)
            fw_text = fw_block.group(1) if fw_block else ""
            fw_udp = find(r'UDP:\s*([\d.]+)%', fw_text) if fw_text else "0"
            fw_tcp = find(r'TCP:\s*([\d.]+)%', fw_text) if fw_text else "0"

            # Fuentes via Kad
            kad_sources = find(r'via Kad:\s*(\d+)')

            return {
                "contacts": contacts,
                "extra": {
                    "kad_overhead_session_pkts": kad_session,
                    "kad_overhead_total_pkts": kad_total,
                    "kad_clients_pct": kad_clients_pct,
                    "kad_firewalled_udp_pct": fw_udp,
                    "kad_firewalled_tcp_pct": fw_tcp,
                    "kad_sources_found": kad_sources,
                }
            }

        except Exception as e:
            print(f"[!] Error leyendo arbol de estadisticas: {e}")
            return defaults

    def fetch_local_kad_id(self):
        """
        Lee el archivo key_index.dat de aMule para sacar el Kad ID de 128 bits.
        """
        pref_path = os.path.expanduser("~/.aMule/key_index.dat")

        # Si no existe la ruta por defecto, buscar en el .env
        env_path = os.getenv("EMULE_KEY_INDEX_PATH", "")
        if env_path and os.path.exists(env_path):
            pref_path = env_path

        try:
            if os.path.exists(pref_path):
                with open(pref_path, "rb") as f:
                    user_hash = f.read(16)
                    if len(user_hash) == 16:
                        kad_id_hex = binascii.hexlify(user_hash).decode('ascii')
                        print(f"[+] Kad ID local: {kad_id_hex}")
                        return kad_id_hex
            else:
                print(f"[!] No encuentro key_index.dat en {pref_path}")

        except Exception as e:
            print(f"[!] Error leyendo Kad ID: {e}")

        return "0" * 32


# Ejecucion manual
if __name__ == "__main__":
    print("\n--- Captura manual de datos (amuleweb) ---")

    admin_pass = os.getenv("ADMIN_PASS", "")
    ip_address = os.getenv("IP_ADDRESS", "127.0.0.1")

    scraper = AMuleWebScraper(host=ip_address, port=4712, password=admin_pass)

    if scraper.login():
        stats = scraper.fetch_kad_stats()

        if stats:
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                output_path = os.path.join(project_root, "jsons", "kad_stats.json")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(stats, f, indent=4, ensure_ascii=False)
                print(f"[+] Guardado en '{output_path}'.")
            except Exception as e:
                print(f"[!] Error escribiendo JSON: {e}")
    else:
        print("[!] No he podido conectar con amuleweb. Guardando estado Disconnected...")
        disconnected_data = {
            "status": "Disconnected",
            "kad_status": "Disconnected",
            "contacts": "0",
            "active_searches": "0",
            "local_id": "Unknown"
        }
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_path = os.path.join(project_root, "jsons", "kad_stats.json")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(disconnected_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Error actualizando estado offline: {e}")
