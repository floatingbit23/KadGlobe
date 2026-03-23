"""
Módulo para parsear el archivo binario `nodes.dat` de eMule. 
El archivo 'nodes.dat' contiene la tabla de ruteo persistente de Kademlia.

Header/Cabecera:
- Si los primeros 4 bytes (uint32) son '0', significa que estamos ante el formato nuevo.
- Los siguientes 4 bytes (uint32) representan la versión (ej. 2 o 3).
- Los siguientes 4 bytes (uint32) representan el número total de nodos de contacto (count).

Estructura de cada nodo:
- Cada nodo de contacto ocupa exactamente 34 bytes en esta versión (v2):
    - 16 bytes: ID de 128-bits
    - 4 bytes: Dirección IP (uint32, IPv4 en formato little-endian)
    - 2 bytes: Puerto UDP (uint16)
    - 2 bytes: Puerto TCP (uint16)
    - 1 byte: Versión/Tipo (uint8)
    - 9 bytes: Metadatos adicionales de Kad (KadUDPKey, flags de verificación, etc. - 34 en total)
"""

import struct
import socket
import binascii

def parse_nodes_dat(file_path="nodes.dat"): # si no se especifica una ruta, se asume que el archivo está en el directorio actual

    """
    Esta función parsea el archivo 'nodes.dat' de Kademlia y devuelve una lista de diccionarios 
    que contienen los detalles de conexión de cada nodo.
    """

    nodes = [] # Lista que contendrá los nodos parseados
    
    try:
        # Abro el archivo en modo lectura binaria (read binary)
        with open(file_path, "rb") as f:
            data = f.read()
            
        if len(data) < 12: # Si el archivo es menor a 12 bytes, no puede contener una cabecera válida
            raise ValueError("El archivo es demasiado pequeño para contener una cabecera 'nodes.dat' válida.")
            
        # Desempaqueto la cabecera de 12 bytes

        # struct.unpack() desempaqueta datos binarios (.dat)
        # < : little-endian (el orden de bytes)
        # III : 3 Unsigned ints (12 bytes)
        # data[0:12] : toma solo los primeros 12 bytes del archivo (donde vive la cabecera)
        magic_zero, version, count = struct.unpack("<III", data[0:12])
        # magic_zero : formato de archivo
        # version : version del formato
        # count : cantidad de nodos
        
        offset = 0 # Inicializo el offset en 0

        if magic_zero == 0: # Si magic_zero es 0, es formato nuevo (Versión >= 2)
            offset = 12 # Salto los 12 bytes de la cabecera
            node_size = 34 # Tamaño de cada nodo en formato nuevo

        else: # Si magic_zero no es 0, es formato clásico/legacy (Versión 0 o 1)

            # En el formato antiguo, los primeros 4 bytes indican la cantidad de nodos directamente.
            count = magic_zero # cantidad de nodos
            version = 0 if magic_zero else 1 # version 0 o 1
            node_size = 25 # Tamaño de cada nodo en formato antiguo
            offset = 4 # Salto los 4 bytes de la cabecera
            
        # Imprimo la información de la cabecera
        print(f"[*] Formato detectado: Versión {version}, Cantidad de nodos: {count}, Tamaño de nodo: {node_size} bytes")
        
        parsed_nodes = 0 # Inicializo el contador de nodos parseados

        # Mientras el (offset + tamaño del nodo) sea menor o igual a la longitud de los datos Y el contador de nodos parseados sea menor a la cantidad total de nodos
        while offset + node_size <= len(data) and parsed_nodes < count:

            chunk = data[offset : offset + node_size] # Tomo un chunk de datos del tamaño de un nodo
            
            # La información fundamental de ruteo se encuentra en los primeros 25 bytes (chunk[0:25]).
            # <16s : cadena de 16 bytes (ID de 128-bits)
            # I    : uint32 de 4 bytes (IPv4 del nodo)
            # H    : uint16 de 2 bytes (Puerto UDP para mensajes Kad)
            # H    : uint16 de 2 bytes (Puerto TCP para transferencia de datos)
            # B    : uint8 de 1 byte (Versión del cliente del nodo)

            # Desempaqueto el chunk de datos
            node_id_bytes, ip_int, udp_port, tcp_port, node_version = struct.unpack("<16sIHHB", chunk[0:25])

            # Convierto el ID del nodo a formato hexadecimal
            node_id_hex = binascii.hexlify(node_id_bytes).decode('ascii')

            # Convierto el entero de la IP a una cadena con formato decimal con puntos.
            # Lo empaqueto forzando little-endian, y luego lo traduzco a una cadena legible.
            # struct.pack('<I', ip_int): empaqueta el entero de la IP en formato little-endian
            # socket.inet_ntoa(): convierte una dirección IP en formato binario (int) a formato decimal con puntos (string)
            ip_str = socket.inet_ntoa(struct.pack('<I', ip_int))
            
            # Añadimos el nodo parseado a la lista
            nodes.append({
                "id": node_id_hex,
                "ip": ip_str,
                "udp_port": udp_port,
                "tcp_port": tcp_port,
                "version": node_version
            })
            
            offset += node_size # Avanzo al siguiente nodo
            parsed_nodes += 1 # Incremento el contador de nodos parseados
        
        print(f"[*] Se han parseado exitosamente {parsed_nodes} nodos.")
        return nodes
        
    except FileNotFoundError:
        print(f"[!] Error: No se ha podido encontrar el archivo '{file_path}'.")
        return []

    except Exception as e: 
        print(f"[!] Advertencia: Ha ocurrido un error mientras se parseaba el fichero: {str(e)}")
        return nodes

# Función para probar el parseador (no se ejecuta si se importa el módulo)
if __name__ == "__main__": 

    # Si ejecuto esto de forma independiente, asumo la lectura del nodes.dat en el directorio raíz
    import os

    extracted_nodes = parse_nodes_dat("../nodes.dat") # Parseo el archivo nodes.dat

    if extracted_nodes: # Si se han extraído nodos

        # Imprimo los nodos parseados
        print("\n[+] Todos los nodos extraídos:")

        i = 1 # Inicializo el contador de nodos parseados
        for n in extracted_nodes: # Recorro la lista de nodos parseados
            print(f"Nodo nº{i} - ID: {n['id'][:8]}... | IP: {n['ip']:15} | UDP: {n['udp_port']:<5} | TCP: {n['tcp_port']:<5} | Ver: {n['version']}")
            i += 1 # Incremento el contador de nodos parseados

