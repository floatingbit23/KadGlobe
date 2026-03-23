import json
import time
import os
from concurrent.futures import ThreadPoolExecutor

# COLORES PARA LA TERMINAL
import builtins
_orig_print = builtins.print
def _color_print(*args, **kwargs):
    text = " ".join(map(str, args))
    if text.lstrip().startswith("[!]"):
        _orig_print(f"\033[91m{text}\033[0m", **kwargs)
    else:
        _orig_print(f"\033[92m{text}\033[0m", **kwargs)
builtins.print = _color_print

try:
    import ping3
    ping3.EXCEPTIONS = False # Devuelve None en vez de lanzar excepciones en nodos silenciosos
except ImportError:
    print("[!] ping3 no está instalado. Ejecuta: pip install ping3")
    raise

"""
Ping Sweep ICMP Concurrente para KadGlobe
Obtiene el RTT real de los nodos Kademlia via ICMP Echo, el método más fiable.
"""

INPUT_FILE  = "../jsons/kad_nodes_geospatial.json"
OUTPUT_FILE = "../jsons/kad_responsive_nodes.json"
MAX_WORKERS = 50   # Pings simultáneos - suficientes sin saturar el router
TIMEOUT_S   = 2    # Tiempo máximo de espera por nodo (segundos)


def ping_node(node):
    """
    Envía un ICMP Echo a la IP del nodo y devuelve un dict enriquecido si responde.
    Devuelve None si el nodo está desconectado o tiene firewall ICMP.
    """
    ip = node.get("ip")
    if not ip:
        return None

    # ping3.ping() devuelve el RTT en segundos, o False/None si no hay respuesta
    rtt_seconds = ping3.ping(ip, timeout=TIMEOUT_S)

    if rtt_seconds and rtt_seconds > 0:
        rtt_ms = int(rtt_seconds * 1000)
        return {
            "ip": ip,
            "udp_port": node.get("udp_port", 0),
            "tcp_port": 0,
            "id": node.get("client_id", ""),
            "lat": node.get("lat"),
            "lon": node.get("lon"),
            "country": node.get("country", ""),
            "rtt": rtt_ms
        }
    return None


def ping_all_nodes():
    """
    Barrido ICMP concurrente sobre todos los nodos del archivo maestro.
    """
    if not os.path.exists(INPUT_FILE):
        print(f"[!] Archivo maestro no hallado: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    print(f"\n[*] Iniciando ICMP Ping Sweep sobre {len(nodes)} nodos ({MAX_WORKERS} workers paralelos)...")
    start = time.time()

    responsive_nodes = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(ping_node, nodes))

    for r in results:
        if r is not None:
            responsive_nodes.append(r)

    elapsed = time.time() - start
    print(f"[+] Sweep completado en {elapsed:.2f}s.")
    print(f"[+] Nodos que respondieron al ping ICMP: {len(responsive_nodes)} / {len(nodes)} VIVOS.\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(responsive_nodes, f, indent=4)


if __name__ == "__main__":
    ping_all_nodes()
