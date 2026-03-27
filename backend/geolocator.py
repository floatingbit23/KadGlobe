"""
Módulo para coordinar la traducción de las IPs que extraemos de `nodes.dat` en coordenadas geográficas reales de latitud y longitud. 
Utiliza la librería IP2Location y la base de datos local DB5 LITE.
"""
import os
import json
import IP2Location # 
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

# Importo el parseador que ya construimos para obtener los nodos
from nodes_dat_parser import parse_nodes_dat

# Cargo la configuración del entorno (.env)
load_dotenv()

# Clase que se encarga de geolocalizar las IPs
class KadGeolocator: 

    # Función que inicializa el geolocalizador
    def __init__(self): 
        # Recupero la ruta de la base de datos desde el entorno (.env)
        self.db_path = os.getenv("IP2LOCATION_DB_PATH", "../data/IP2LOCATION-LITE-DB5.BIN")
        self.db = None 
        
        if os.path.exists(self.db_path): # Si existe la base de datos

            try:
                self.db = IP2Location.IP2Location(self.db_path) # Cargo la base de datos binaria
                print(f"[+] BBDD cargada exitosamente: {self.db_path}")
            except Exception as e:
                print(f"[!] Error al abrir la base de datos: {e}")
        else:
            print(f"[!] Advertencia: No he encontrado la BBDD en {self.db_path}")


    # Función que se encarga de geolocalizar las IPs
    def get_location(self, ip): 

        # Dada una IP, devuelvo un diccionario con sus coordenadas y ciudad.
        
        if not self.db: # Si no existe la base de datos
            return None # Devuelvo None
            
        try:

            rec = self.db.get_all(ip) # Obtengo la información de la IP

            # Devuelvo un diccionario con las coordenadas, la ciudad y el país
            
            return {
                # Forzamos que lat y lng sean números flotantes (float) para que el filtro posterior funcione bien
                "lat": float(getattr(rec, 'latitude', 0.0)),
                "lng": float(getattr(rec, 'longitude', 0.0)),
                "city": getattr(rec, 'city', "Unknown"),
                "country": getattr(rec, 'country_long', "Unknown"),
                "country_code": str(getattr(rec, 'country_short', "unknown")).lower()
            }

        except Exception as e: # Si ocurre un error al geolocalizar la IP
            print(f"[!] Error geolocalizando la IP {ip}: {e}")
            return None

    # Función que se encarga de procesar los nodos
    def process_kad_nodes(self, nodes_file="../nodes.dat", output_file="../jsons/kad_nodes_geospatial.json"): 
        
        """
        Es el proceso principal: parseo el archivo binario, traduzco cada IP y guardo el JSON final en la carpeta de jsons.
        """
        
        # 1. Extraigo los nodos usando el parseador binario
        print(f"[*] Iniciando el procesamiento de {nodes_file}...")
        raw_nodes = parse_nodes_dat(nodes_file) # Obtengo los nodos del archivo binario
        

        if not raw_nodes:
            print("[!] No he podido recuperar ningún nodo del archivo binario.")
            return
            
        geospatial_nodes = [] # Lista donde guardaré los nodos geolocalizados
        wasted_nodes = 0 # Contador de nodos desperdiciados
    
        print(f"[*] Traduciendo las {len(raw_nodes)} IPs a coordenadas geográficas...")
        
        
        for node in raw_nodes: # Por cada nodo del archivo binario

            loc = self.get_location(node['ip']) # Obtengo la información de la IP
            
            # Solo guardamos nodos con coordenadas válidas (que no sean 0,0)
            if loc and (loc['lat'] != 0.000000 or loc['lng'] != 0.000000):

                geospatial_nodes.append({ # Añadimos los nodos con su información geográfica a la lista
                    "id": node['id'], # ID de la IP
                    "ip": node['ip'], # Dirección IP real
                    "lat": loc['lat'], # Latitud de la IP
                    "lng": loc['lng'], # Longitud de la IP
                    "city": loc['city'], # Ciudad de la IP
                    "country": loc['country'], # País de la IP
                    "country_code": loc.get('country_code', 'unknown'), # Código ISO de 2 letras
                    "udp_port": node.get('udp_port', 4672), # Puerto vital para los Handshakes UDP
                    "size": 0.01  # Tamaño por defecto para la representación en el globo terráqueo
                })
            
            else:
                wasted_nodes += 1 # Incremento el contador de nodos desperdiciados
        
        # Guardo el resultado en formato JSON para el Frontend (kad_nodes_geospatial.json)
        try:
            with open(output_file, "w", encoding="utf-8") as f: # Abro el archivo en modo escritura
                json.dump(geospatial_nodes, f, indent=4, ensure_ascii=False) # Guardo los nodos en el archivo JSON
            
            print(f"\n[+] ¡Éxito! Se han guardado {len(geospatial_nodes)} nodos geolocalizados en '{output_file}'.")
            print(f"[!] Se han descartado {wasted_nodes} nodos.\n")
        
        except Exception as e: 
            print(f"[!] Error al guardar el archivo JSON: {e}")

    # Función que se encarga de cerrar ("descargar") la base de datos al terminar
    def __del__(self): 
        if self.db: # Si existe la base de datos
            self.db.close() # Cierro la base de datos


# Bloque principal de ejecución
if __name__ == "__main__":

    # Prueba de ejecución del geolocalizador
    print("\n--- KadGlobe Geospatial Mapper ---\n")
    
    geo = KadGeolocator() # Inicializo el geolocalizador
    
    # Busco primero la ruta matriz de mi eMule original configurada en .env
    nodes_path = os.getenv("EMULE_NODES_DAT_PATH", "")

    # Si la ruta proporcionada en el .env falla (por permisos o no existe), retrocedo al default
    if not nodes_path or not os.path.exists(nodes_path):
        
        # Lógica de detección automática para Linux (aMule)
        if os.name != "nt": # Si no estamos en Windows...
            amule_path = os.path.expanduser("~/.aMule/nodes.dat")
            if os.path.exists(amule_path):
                nodes_path = amule_path
                print(f"[*] Detectado sistema Linux. Usando ruta de aMule: {nodes_path}")

        # Si aún no tenemos ruta válida, probamos el relativo local
        if not nodes_path or not os.path.exists(nodes_path):
            nodes_path = "../nodes.dat"
            if not os.path.exists(nodes_path): 
                nodes_path = "nodes.dat" # Prueba en el actual
        
    geo.process_kad_nodes(nodes_file=nodes_path) # Proceso el archivo nodes.dat

