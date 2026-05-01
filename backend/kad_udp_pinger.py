import math
import json
import time
import os
import sys
import socket
import struct
import random
import requests
from concurrent.futures import ThreadPoolExecutor
import builtins
import datetime

from dotenv import load_dotenv

load_dotenv() # Cargamos variables desde .env (puertos, etc.)
"""
Kad UDP Probe — Descubrimiento inteligente de nodos activos, Crawl recursivo y medición de latencia.

Este script realiza un flujo de descubrimiento en 4 fases:
  1. SEMILLA: Obtiene una lista inicial de contactos desde el eMule local (Bootstrap Req a 127.0.0.1).
  2. SELECCIÓN (RTT): Mide la latencia de la semilla y selecciona a los 4 líderes más rápidos.
  3. EXPANSIÓN (Crawl 1-hop): Solicita contactos a esos 4 líderes para expandir el horizonte de la red.
  4. SONDEO FINAL: Mide el RTT de todos los nodos descubiertos e identifica el nodo propio (Self-Node).

Opcodes utilizados (definidos en eMule en el archivo "opcodes.h"):
  - 0xE4: Identificador de protocolo Kademlia (header byte)
  - 0x01: KADEMLIA2_BOOTSTRAP_REQ  (petición de contactos frescos)
  - 0x09: KADEMLIA2_BOOTSTRAP_RES  (respuesta con lista de contactos)
  - 0x60: KADEMLIA2_PING           (petición de vida, sin payload)
  - 0x61: KADEMLIA2_PONG           (respuesta de vida, incluye puerto UDP)
"""

if not getattr(builtins.print, "_kadglobe_logging", False):
    _orig_print = builtins.print

    def _color_print(*args, **kwargs):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        text = " ".join(map(str, args))
        stripped_text = text.lstrip()
        
        if stripped_text.startswith("[!]"):
            _orig_print(f"{timestamp}\033[91m{text}\033[0m", **kwargs)
        elif stripped_text.startswith("[+]"):
            _orig_print(f"{timestamp}\033[92m{text}\033[0m", **kwargs)
        elif stripped_text.startswith("[*]") or stripped_text.startswith("[i]"):
            _orig_print(f"{timestamp}\033[97m{text}\033[0m", **kwargs)
        else:
            _orig_print(f"{timestamp}{text}", **kwargs)

    _color_print._kadglobe_logging = True
    builtins.print = _color_print

import random

# Caché en memoria para no geolocalizar la misma IP varias veces en una ronda
GEO_CACHE = {}

def atomic_write_json(path, data):
    """Escribe un JSON de forma segura usando un archivo temporal."""
    temp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, path)
    except Exception as e:
        print(f"[!] Error en escritura atómica: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)

# Punto de referencia: Carpeta raíz del proyecto (un nivel arriba del backend)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUTPUT_FILE = os.path.join(project_root, "jsons", "kad_udp_responsive_nodes.json")

MAX_WORKERS = 50   
TIMEOUT_S = 5    

# Constantes del protocolo Kademlia (eMule opcodes.h)
KAD_PROTOCOL_ID            = 0xE4
KADEMLIA2_BOOTSTRAP_REQ    = 0x01   # Petición de contactos frescos
KADEMLIA2_BOOTSTRAP_RES    = 0x09   # Respuesta con lista de contactos
KADEMLIA2_PING             = 0x60   # Ping (sin payload, 2 bytes totales)
KADEMLIA2_PONG             = 0x61   # Pong (respuesta esperada)

# Puerto UDP del eMule local (configurado en eMule -> Opciones -> Conexión)
EMULE_LOCAL_UDP_PORT = int(os.getenv("EMULE_KAD_UDP_PORT", 16005))

# Tamaño de cada contacto en el BOOTSTRAP_RES: 16B KadID + 4B IP + 2B UDP + 2B TCP + 1B version = 25 bytes
CONTACT_SIZE = 25

# Categorías de diagnóstico para clasificar la respuesta de cada nodo
CATEGORY_PONG       = "PONG"         # Respondió con KADEMLIA2_PONG válido (nodo vivo, sin ofuscación)
CATEGORY_UNKNOWN    = "UNKNOWN_RESP" # Respondió con algo que NO es un PONG estándar (posible ofuscación)
CATEGORY_RESET      = "CONN_RESET"   # Puerto cerrado activamente (no hay servicio Kad en ese puerto)
CATEGORY_TIMEOUT    = "TIMEOUT"      # Sin respuesta (nodo apagado, IP cambió, o firewall bloquea)
CATEGORY_ERROR      = "NET_ERROR"    # Error de red inesperado

# ─────────────────────────────────────────────────────────────────────────────
# Fase 1: Descubrimiento de nodos frescos via Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def send_bootstrap_req(ip, port, timeout=TIMEOUT_S):
    """
    Envía un paquete KADEMLIA2_BOOTSTRAP_REQ (0xE4 0x01) a una IP/puerto 
    y retorna una tupla: (lista_de_contactos, sender_id_hex).
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # Enviar BOOTSTRAP_REQ (2 bytes, sin payload)
        sock.sendto(bytes([KAD_PROTOCOL_ID, KADEMLIA2_BOOTSTRAP_REQ]), (ip, port))
        
        data, _ = sock.recvfrom(4096)
        
        # Validar header
        if len(data) < 23 or data[0] != KAD_PROTOCOL_ID or data[1] != KADEMLIA2_BOOTSTRAP_RES:
            return [], None, 0
        
        # Extraer el KadID del emisor (Bytes 2 al 18)
        sender_id = data[2:18].hex()
        
        # Extraer la versión del emisor (Byte 20)
        sender_version = data[20]
        
        # Parsear contactos (Offset 21: Cantidad de contactos uint16 LE)
        contact_count = struct.unpack('<H', data[21:23])[0]
        
        found = []
        offset = 23
        for _ in range(contact_count):
            if offset + CONTACT_SIZE > len(data): break
            
            kad_id = data[offset:offset+16].hex()
            raw_ip = data[offset+16:offset+20]
            ip_str = '.'.join(str(b) for b in reversed(raw_ip))
            
            udp_p = struct.unpack('<H', data[offset+20:offset+22])[0]
            tcp_p = struct.unpack('<H', data[offset+22:offset+24])[0]
            ver   = data[offset+24]
            
            found.append({
                "ip": ip_str,
                "udp_port": udp_p,
                "tcp_port": tcp_p,
                "client_id": kad_id,
                "kad_version": ver
            })
            offset += CONTACT_SIZE
            
        return found, sender_id, sender_version
        
    except Exception:
        return [], None, 0
    finally:
        if sock: sock.close()

def discover_nodes_expanded():
    """
    Fase 1: Obtiene nodos del eMule local y su ID de cliente.
    Fase 1.5: Pregunta a 4 de esos nodos por sus contactos (Expansión 1-hop).
    """
    print(f"\n[*] Fase 1: Solicitando semilla al eMule local (127.0.0.1:{EMULE_LOCAL_UDP_PORT})...")
    seed_nodes, _, _ = send_bootstrap_req('127.0.0.1', EMULE_LOCAL_UDP_PORT)
    
    if not seed_nodes:
        print("[!] No se pudo contactar con eMule local. ¿Está abierto?")
        return []
        
    print(f"[+] Semilla inicial: {len(seed_nodes)} nodos obtenidos.")
    all_discovered = {n['ip']: n for n in seed_nodes}
    
    # 2. Identificar nuestro propio nodo (Auto-representación)
    try:
        my_public_ip = requests.get('https://api.ipify.org', timeout=3).text
        if my_public_ip not in all_discovered:
            all_discovered[my_public_ip] = {
                "ip": my_public_ip,
                "udp_port": EMULE_LOCAL_UDP_PORT,
                "tcp_port": 0,
                "client_id": "SELF",
                "kad_version": 0,
                "is_self": True
            }
            print(f"[+] Tu nodo identificado: {my_public_ip} (Pilar destacado)")
    except Exception:
        pass

    # 3. Expansión (Crawl 1-hop)
    # Seleccionamos 4 vecinos remotos elegidos al azar para mayor diversidad
    targets = random.sample(seed_nodes, min(len(seed_nodes), 4))
    print(f"[*] Fase 1.5: Expandiendo horizonte vía {len(targets)} vecinos remotos...")
    
    for t in targets:
        remote_contacts, _, _ = send_bootstrap_req(t['ip'], t['udp_port'], timeout=2.0)
        new_found = 0
        for rc in remote_contacts:
            if rc['ip'] not in all_discovered:
                all_discovered[rc['ip']] = rc
                new_found += 1
        if new_found > 0:
            print(f"    [+] {t['ip']} nos entregó {new_found} nuevos vecinos.")
            
    return list(all_discovered.values())

# ─────────────────────────────────────────────────────────────────────────────
# Fase 2: Geolocalización de nodos descubiertos
# ─────────────────────────────────────────────────────────────────────────────

def geolocate_nodes(nodes):
    """
    Geolocaliza los nodos descubiertos usando la base de datos IP2Location.
    Añade lat, lng y country a cada nodo.
    """
    try:
        import IP2Location
        
        # Buscar la base de datos IP2Location
        db_path = os.path.join(project_root, "data", "IP2LOCATION-LITE-DB5.BIN")
        if not os.path.exists(db_path):
            print(f"[!] Base de datos IP2Location no encontrada en {db_path}. Nodos sin geolocalizar.")
            return nodes
        
        db = IP2Location.IP2Location(db_path)
        
        geolocated = []
        for node in nodes:
            ip = node["ip"]
            # 1. Consultar Cache
            if ip in GEO_CACHE:
                node.update(GEO_CACHE[ip])
                geolocated.append(node)
                continue

            # 2. Consultar DB
            try:
                rec = db.get_all(ip)
                geo_data = {
                    "lat": float(rec.latitude) if rec.latitude else 0.0,
                    "lng": float(rec.longitude) if rec.longitude else 0.0,
                    "city": str(rec.city) if getattr(rec, 'city', None) else "Unknown",
                    "country": str(rec.country_long) if getattr(rec, 'country_long', None) else "Unknown",
                    "country_code": str(rec.country_short).lower() if getattr(rec, 'country_short', None) else "unknown"
                }
                
                # Descartar nodos con coordenadas 0,0 (no geolocalizados)
                if math.isclose(geo_data["lat"], 0.0) and math.isclose(geo_data["lng"], 0.0):
                    continue
                
                node.update(geo_data)
                GEO_CACHE[ip] = geo_data # Guardar en cache
                geolocated.append(node)
            except Exception:
                continue
        
        db.close()
        print(f"[+] Geolocalizados {len(geolocated)}/{len(nodes)} nodos.")
        return geolocated
    
    except ImportError:
        print("[!] Modulo IP2Location no instalado. Nodos sin geolocalizar.")
        return nodes

# ─────────────────────────────────────────────────────────────────────────────
# Fase 3: Sondeo UDP (PING/PONG) y medición de RTT
# ─────────────────────────────────────────────────────────────────────────────

def udp_ping_node(node):
    """
    Envía un paquete KADEMLIA2_PING (0xE4 0x60) por UDP al nodo y clasifica la respuesta.
    
    Retorna una tupla: (resultado_dict | None, categoría, detalle)
    """
    ip = node.get("ip")
    port = node.get("udp_port")

    if not ip or not port:
        return (None, CATEGORY_ERROR, "IP o puerto faltante en el nodo")

    sock = None
    try:
        packet = bytes([KAD_PROTOCOL_ID, KADEMLIA2_PING])
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(TIMEOUT_S)
        
        start_time = time.time()
        sock.sendto(packet, (ip, port))
        
        data, _ = sock.recvfrom(1024)
        rtt_seconds = time.time() - start_time
        rtt_ms = int(rtt_seconds * 1000)
        
        # Caso 1: KADEMLIA2_PONG válido (0xE4 0x61)
        if data and len(data) >= 2 and data[0] == KAD_PROTOCOL_ID and data[1] == KADEMLIA2_PONG:
            result = {
                "ip": ip,
                "udp_port": port,
                "tcp_port": node.get("tcp_port", 0),
                "id": node.get("client_id", ""),
                "lat": node.get("lat"),
                "lng": node.get("lng"),
                "city": node.get("city", "Unknown"),
                "country": node.get("country", ""),
                "country_code": node.get("country_code", "unknown"),
                "rtt": rtt_ms
            }
            return (result, CATEGORY_PONG, f"RTT={rtt_ms}ms")
        
        # Caso 2: Respondió con algo desconocido
        else:
            header_hex = data[:8].hex() if data else "vacio"
            return (None, CATEGORY_UNKNOWN, f"RTT={rtt_ms}ms, {len(data)}B, header={header_hex}")

    except socket.timeout:
        return (None, CATEGORY_TIMEOUT, "Sin respuesta en 5s")
    
    except ConnectionResetError:
        return (None, CATEGORY_RESET, "Puerto cerrado (ICMP Port Unreachable)")
    
    except OSError as e:
        return (None, CATEGORY_ERROR, f"OSError: {e}")
    
    except Exception as e:
        return (None, CATEGORY_ERROR, f"{type(e).__name__}: {e}")
    
    finally:
        if sock:
            sock.close()

# ─────────────────────────────────────────────────────────────────────────────
# Orquestador principal: Bootstrap → Geolocalización → Ping Sweep
# ─────────────────────────────────────────────────────────────────────────────

def ping_all_nodes():
    print("\n[i] Ejecutando Kad UDP Probe (Modo Inteligente RTT-Selection)...")
    
    # 1. Seed inicial (eMule local)
    print(f"[*] Fase 1: Solicitando semilla al eMule local (127.0.0.1:{EMULE_LOCAL_UDP_PORT})...")
    seed, dynamic_id, kad_ver = send_bootstrap_req('127.0.0.1', EMULE_LOCAL_UDP_PORT)

    # Mapeo de versiones conocidas
    KAD_VERSION_MAP = {
        6: "v0.48a",
        7: "v0.49c",
        8: "v0.50a",
        9: "v0.60 / aMule",
        10: "v0.60d / v0.70 (Community Edition)"
    }
    
    ver_str = KAD_VERSION_MAP.get(kad_ver, f"Desconocida (Kad Ver: {kad_ver})")

    # Sale del script si no hay seed (es decir si no se pudo contactar con el cliente eMule local)
    if not seed:
        print("[!] No se pudo contactar con el cliente eMule local. Abortando.")
        sys.exit(1) 

    print(f"[+] Conectado a eMule (Kad Version: {kad_ver} -> {ver_str})")

    # Auto-identificación de nuestro nodo
    my_ip = None
    for provider in ['https://api.ipify.org', 'https://ifconfig.me/ip']:
        try:
            my_ip = requests.get(provider, timeout=3).text.strip()
            if my_ip: break
        except Exception:
            continue

    # 2. Pre-Ping para elegir líderes por RTT
    print(f"\n[*] Fase 2: Midiendo RTT de los {len(seed)} nodos de la semilla...")
    seed_geolocated = geolocate_nodes(seed)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        seed_raw_results = list(executor.map(udp_ping_node, seed_geolocated))
    
    # Extraer los que respondieron PONG (result es el dict con RTT)
    seed_pongs = [res for (res, cat, det) in seed_raw_results if cat == CATEGORY_PONG]
    fastest_leaders = sorted(seed_pongs, key=lambda x: x.get('rtt', 9999))[:4]
    
    if fastest_leaders:
        print(f"[+] Líderes de expansión seleccionados (Top {len(fastest_leaders)} por RTT):")
        for l in fastest_leaders:
            print(f"    - {l['ip']} (RTT: {l['rtt']}ms)")
    else:
        print("[!] Ningún nodo de la semilla respondió al ping inicial. Usando fallback aleatorio.")
        fastest_leaders = random.sample(seed_geolocated, min(len(seed_geolocated), 4))

    # 3. Fase de Expansión (Crawl)
    # Incluimos los resultados del pre-ping en el set global
    all_discovered = {n['ip']: n for n in seed_geolocated}
    
    # Aseguramos que los datos del ping (RTT, etc) se guarden en el set global
    for res in seed_pongs:
        ip = res['ip']
        if ip in all_discovered:
            all_discovered[ip].update(res)
            all_discovered[ip]['category'] = CATEGORY_PONG

    # Identificamos nuestro nodo con prioridad máxima
    if my_ip:
        if my_ip not in all_discovered:
            all_discovered[my_ip] = {"ip": my_ip, "udp_port": EMULE_LOCAL_UDP_PORT}
        
        all_discovered[my_ip].update({
            "is_self": True,
            "client_id": dynamic_id or "fca7f58bab6d4199d227ea423f9a8155" # ID dinámico o fallback
        })
        print(f"\n[+] Identidad confirmada para: {my_ip} (Pilar destacado)")
    
    print("\n[*] Fase 3: Expandiendo horizonte vía los líderes más rápidos...")
    for leader in fastest_leaders:
        remote_contacts, _, _ = send_bootstrap_req(leader['ip'], leader['udp_port'], timeout=2.0)
        new_found = 0
        for rc in remote_contacts:
            if rc['ip'] not in all_discovered:
                all_discovered[rc['ip']] = rc
                new_found += 1
        if new_found > 0:
            print(f"    [+] {leader['ip']} entregó {new_found} nuevos vecinos.")

    # 4. Fase de Sondeo Final
    new_nodes = [n for n in all_discovered.values() if 'category' not in n]
    print(f"\n[*] Fase 4: Sondeo final a {len(new_nodes)} nuevos nodos geolocalizados...")
    new_geolocated = geolocate_nodes(new_nodes)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        final_raw_results = list(executor.map(udp_ping_node, new_geolocated))
    
    # Consolidar todos los éxitos
    # Recopilamos todos los nodos que respondieron PONG
    all_pongs_raw = [n for n in all_discovered.values() if n.get('category') == CATEGORY_PONG]
    all_pongs_raw += [res for (res, cat, det) in final_raw_results if cat == CATEGORY_PONG]
    
    # Generar lista final limpia para el JSON
    final_json_list = []
    seen_ips = set()
    for n in all_pongs_raw:
        ip = n['ip']
        if ip not in seen_ips:
            # Recuperamos metadatos persistentes (como is_self) del diccionario maestro
            master_data = all_discovered.get(ip, {})
            
            final_json_list.append({
                "ip": ip,
                "udp_port": n["udp_port"],
                "id": n.get("client_id", n.get("id", "Error")),
                "lat": n["lat"],
                "lng": n["lng"],
                "city": n.get("city", "Unknown"),
                "country": n.get("country", "Unknown"),
                "country_code": n.get("country_code", "unknown"),
                "rtt": n["rtt"],
                "is_self": master_data.get("is_self", False),
                "is_fresh": True
            })
            seen_ips.add(ip)

    # Guardar resultados de forma atómica
    atomic_write_json(OUTPUT_FILE, final_json_list)

    print("\n[+] Kad UDP Probe Inteligente finalizado.")
    print(f"    - Nodos totales descubiertos: {len(all_discovered)}")
    print(f"    - Nodos vivos (PONG): {len(final_json_list)}")
    print(f"    - Resultados guardados en: {OUTPUT_FILE}")

if __name__ == "__main__":
    ping_all_nodes()
