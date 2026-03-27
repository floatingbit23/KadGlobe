import json
import time
import os
import ping3

# Utilizo ThreadPoolExecutor para lanzar múltiples pings a la vez sin bloquear el programa, 
# ya que esperar la respuesta de un nodo a la vez sería extremadamente lento.
from concurrent.futures import ThreadPoolExecutor

# Configuro una función personalizada para imprimir en la terminal con colores.
# Así puedo distinguir visualmente entre mensajes de éxito (verde) y errores (rojo).
import builtins
_orig_print = builtins.print
def _color_print(*args, **kwargs):
    text = " ".join(map(str, args))
    if text.lstrip().startswith("[!]"):
        _orig_print(f"\033[91m{text}\033[0m", **kwargs)
    else:
        _orig_print(f"\033[92m{text}\033[0m", **kwargs)
builtins.print = _color_print

# Configuro ping3 para que me devuelva None en lugar de fallar si el nodo no responde (Pings perdidos).
ping3.EXCEPTIONS = False

"""
Este script realiza un 'Ping Sweep' sobre mis nodos Kademlia extraidos de nodes.dat.
Uso el protocolo ICMP Echo (ping clásico) porque es el método más  fiable para medir la latencia real (RTT) de un nodo en internet.
"""

# Punto de referencia: Carpeta raíz del proyecto (un nivel arriba del backend)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Defino las rutas de mis archivos JSON de forma absoluta.
INPUT_FILE  = os.path.join(project_root, "jsons", "kad_nodes_geospatial.json")
OUTPUT_FILE = os.path.join(project_root, "jsons", "kad_responsive_nodes.json")

# Lanzo 50 pings simultáneos. Es un equilibrio bueno para ir rápido sin saturar la conexión de mi router doméstico con demasiadas peticiones.
MAX_WORKERS = 50   
TIMEOUT_S = 3    # Si un nodo tarda más de 3 segundos en responder, lo considero 'muerto' o filtrado.

# Esta función gestiona el envío del ping a un nodo individual.
def ping_node(node):

    # Si el nodo responde, calculará su tiempo de respuesta en milisegundos  y preparará un diccionario con toda su información para el heatmap.

    ip = node.get("ip") # Obtengo la IP del nodo.

    if not ip:
        return None

    # Lanzo el ping a la IP. Me devuelve el RTT en segundos.
    try:
        rtt_seconds = ping3.ping(ip, timeout=TIMEOUT_S)
    except PermissionError:
        # Este error es típico en Linux cuando no se tienen permisos para usar sockets RAW (ICMP).
        if os.name != "nt": # 'nt' means Windows, 'posix' means Linux/Mac
            print(f"\n[!] ERROR DE PERMISOS: No tienes privilegios para enviar pings ICMP en este sistema Linux.")
            print(f"[!] Por favor, ejecuta el siguiente comando en tu terminal para dar permisos a Python:")
            print(f"    sudo setcap cap_net_raw+ep $(readlink -f $(which python3))\n")
        else:
            print(f"\n[!] ERROR DE PERMISOS: Asegúrate de ejecutar este script con privilegios de Administrador.")
        
        # Para evitar saturar la terminal con el mismo mensaje, detenemos la ejecución de este hilo si es crítico.
        # En una ejecución real, el usuario debería aplicar el setcap y reiniciar.
        os._exit(1)
    except Exception as e:
        # Cualquier otro error lo ignoramos y devolvemos None.
        return None

    # Si recibo una respuesta válida (mayor que 0), convierto el tiempo a milisegundos (ms).
    if rtt_seconds and rtt_seconds > 0:

        rtt_ms = int(rtt_seconds * 1000) # Convierto el tiempo a milisegundos (ms).

        # Preparo un diccionario con toda la información del nodo para el heatmap.
        return {
            "ip": ip,
            "udp_port": node.get("udp_port", 0),
            "tcp_port": 0,
            "id": node.get("client_id", ""),
            "lat": node.get("lat"),
            "lng": node.get("lng"),
            "country": node.get("country", ""),
            "rtt": rtt_ms # Este valor es el que usará mi frontend para pintar el nodo de verde, amarillo o rojo.
        }
    
    return None


# Esta es la función principal donde orquesto todo el Ping Sweeping
def ping_all_nodes():
    
    """
    Leo mi lista de nodos, lanzo la ejecución paralela y guardo los resultados.
    """

    # Verifico si el archivo maestro existe.
    if not os.path.exists(INPUT_FILE):
        print(f"[!] Archivo maestro no hallado: {INPUT_FILE}. Primero necesito que geolocator.py genere este archivo.")
        return

    # Cargo mis nodos desde el archivo JSON que generó previamente mi geolocalizador (kad_nodes_geospatial.json)
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    print(f"\n[*] Estoy iniciando el ICMP Ping Sweep sobre {len(nodes)} nodos...")

    start = time.time() # Tomo el tiempo inicial para calcular la duración del Sweeping

    responsive_nodes = [] # Lista donde guardaré los nodos que respondan al ping

    # Uso el ThreadPoolExecutor para mapear mi función ping_node() a toda la lista de nodos
    # Así puedo procesar 50 nodos a la vez de forma asíncrona
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(ping_node, nodes))

    # Filtro los resultados para quedarme solo con los nodos que realmente respondieron
    for r in results:
        if r is not None:
            responsive_nodes.append(r) # Añadimos los nodos con su información geográfica a la lista

    elapsed = time.time() - start # Calculo el tiempo que tardó el Sweeping

    print(f"[+] He terminado el barrido en {elapsed:.2f} segundos.") # Imprimo el tiempo que tardó el Sweeping
    print(f"[+] He detectado {len(responsive_nodes)} nodos vivos de un total de {len(nodes)}.\n")

    # Finalmente, guardo la lista de 'nodos vivos' en un JSON dedicado (kad_responsive_nodes.json)
    # El archivo app.js de mi frontend leerá este archivo para actualizar el mapa térmico
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(responsive_nodes, f, indent=4)


if __name__ == "__main__":
    # Si ejecuto el script directamente, inicio el proceso de ping.
    ping_all_nodes()
