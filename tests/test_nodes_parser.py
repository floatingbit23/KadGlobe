import pytest
import struct
import os
import binascii
from backend.nodes_dat_parser import parse_nodes_dat

def test_parse_nodes_dat_empty():
    """
    Objetivo: Comprobar que el sistema devuelve una lista vacía de forma segura al intentar leer un archivo inexistente.
    Funciones: parse_nodes_dat()
    """
    nodes = parse_nodes_dat("non_existent_file.dat")
    assert nodes == []

def test_parse_nodes_dat_v2(tmp_path):
    """
    Objetivo: Validar el correcto parseo del formato moderno (V2) de nodes.dat (cabecera de 12 bytes y nodos de 34 bytes).
    Funciones: parse_nodes_dat(), struct.pack()
    """
    # Cabecera: magic_zero=0, version=2, count=1 (Total 12 bytes)
    header = struct.pack("<III", 0, 2, 1)
    # Nodo (34 bytes en V2): 16B ID, 4B IP (1.2.3.4), 2B UDP, 2B TCP, 1B Ver + 9B extra
    node_id = b"1234567890123456"
    ip_bytes = struct.pack("<BBBB", 1, 2, 3, 4)
    # node_id(16) + ip_bytes(4) + udp(2) + tcp(2) + ver(1) = 25 bytes
    node_data = struct.pack("<16s4sHHB", node_id, ip_bytes, 4672, 4662, 8)
    node_full = node_data + b"X" * 9 # Total 34 bytes

    d_file = tmp_path / "nodes_v2.dat"
    d_file.write_bytes(header + node_full)

    nodes = parse_nodes_dat(str(d_file))
    assert len(nodes) == 1
    assert nodes[0]["ip"] == "1.2.3.4"
    assert nodes[0]["udp_port"] == 4672

def test_parse_nodes_dat_legacy(tmp_path):
    """
    Objetivo: Asegurar la compatibilidad hacia atrás con el formato antiguo (legacy) de archivos de nodos.
    Funciones: parse_nodes_dat(), struct.pack()
    """
    # Cabecera legacy: los primeros 4 bytes son el count.
    header = struct.pack("<I", 1)
    # Nodo (25 bytes en legacy)
    node = struct.pack("<16s4sHHB", b"A"*16, struct.pack("<BBBB", 8, 8, 8, 8), 1234, 5678, 9)

    d_file = tmp_path / "nodes_legacy.dat"
    d_file.write_bytes(header + node)

    nodes = parse_nodes_dat(str(d_file))
    assert len(nodes) == 1
    assert nodes[0]["ip"] == "8.8.8.8"

def test_parse_nodes_dat_broken(tmp_path):
    """
    Objetivo: Verificar que el parser ignora nodos parciales o incompletos al final del archivo sin fallar.
    Funciones: parse_nodes_dat()
    """
    # count=2
    header = struct.pack("<I", 2)
    node1 = b"1" * 25
    node2 = b"2" * 10 # Truncado

    d_file = tmp_path / "nodes_broken.dat"
    d_file.write_bytes(header + node1 + node2)

    nodes = parse_nodes_dat(str(d_file))
    assert len(nodes) == 1

