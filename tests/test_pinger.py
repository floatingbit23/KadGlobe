import pytest
from unittest.mock import patch, MagicMock
import socket
import struct
import binascii

from backend.kad_udp_pinger import udp_ping_node, send_bootstrap_req, ping_all_nodes, CATEGORY_PONG, CATEGORY_TIMEOUT

def test_send_ping_success():
    """
    Objetivo: Validar que un nodo responde correctamente a un paquete de ping UDP (0xE4 0x61).
    Funciones: udp_ping_node(), socket.recvfrom()
    """
    with patch("socket.socket") as mock_socket:
        instance = mock_socket.return_value
        # Simulamos un paquete PONG (0xE4 0x61)
        instance.recvfrom.return_value = (bytes([0xE4, 0x61]), ("1.1.1.1", 16005))
        
        node = {"ip": "1.1.1.1", "udp_port": 16005}
        result, cat, det = udp_ping_node(node)
        assert result is not None
        assert cat == CATEGORY_PONG
        assert "rtt" in result
        assert isinstance(result["rtt"], int)

def test_send_ping_timeout():
    """
    Objetivo: Verificar que el sistema gestiona correctamente la falta de respuesta de un nodo mediante un timeout.
    Funciones: udp_ping_node(), socket.timeout
    """
    with patch("socket.socket") as mock_socket:
        instance = mock_socket.return_value
        instance.recvfrom.side_effect = socket.timeout
        
        node = {"ip": "1.1.1.1", "udp_port": 16005}
        result, cat, det = udp_ping_node(node)
        assert result is None
        assert cat == CATEGORY_TIMEOUT

def test_send_bootstrap_req_success():
    """
    Objetivo: Validar el parseo de una respuesta KADEMLIA2_BOOTSTRAP_RES (0x09) que contiene nuevos nodos conocidos.
    Funciones: send_bootstrap_req(), struct.unpack()
    """
    with patch("socket.socket") as mock_socket:
        instance = mock_socket.return_value
        
        # Construir paquete KADEMLIA2_BOOTSTRAP_RES (0x09)
        # Header (2 bytes) + ID (16 bytes) + Port (2 bytes) + Ver (1 byte) + Count (2 bytes)
        header = bytes([0xE4, 0x09])
        my_id = b"A" * 16
        my_port = struct.pack("<H", 16005)
        ver = 8
        count = struct.pack("<H", 1)
        
        # Nodo: ID(16) + IP(4) + UDP(2) + TCP(2) + Ver(1) = 25 bytes
        node_id = b"B" * 16
        # Reversed IP in current implementation: ip_str = '.'.join(str(b) for b in reversed(raw_ip))
        node_ip = bytes([4, 3, 2, 2]) # Will be parsed as 2.2.3.4
        node_ports = struct.pack("<HH", 1234, 5678)
        node_ver = bytes([8])
        
        payload = header + my_id + my_port + bytes([ver]) + count + node_id + node_ip + node_ports + node_ver
        instance.recvfrom.return_value = (payload, ("1.1.1.1", 16005))
        
        nodes, mid, mver = send_bootstrap_req("1.1.1.1", 16005)
        assert len(nodes) == 1
        assert nodes[0]["ip"] == "2.2.3.4"
        assert mid == binascii.hexlify(my_id).decode()
        assert mver == 8

@patch("os.replace")
@patch("backend.kad_udp_pinger.send_bootstrap_req")
@patch("backend.kad_udp_pinger.geolocate_nodes")
@patch("backend.kad_udp_pinger.udp_ping_node")
@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=MagicMock)
@patch("json.load")
def test_ping_all_nodes_flow(mock_json, mock_open, mock_exists, mock_udp, mock_geo, mock_boot, mock_replace):
    """
    Objetivo: Verificar el flujo completo del orquestador: descubrimiento, ping masivo, geolocalización y guardado de resultados.
    Funciones: ping_all_nodes(), udp_ping_node(), geolocate_nodes(), atomic_write_json()
    """
    mock_boot.return_value = ([{"ip": "1.1.1.1", "udp_port": 16005}], "ID", 8)
    mock_geo.return_value = [{"ip": "1.1.1.1", "udp_port": 16005, "lat": 10, "lng": 20}]
    # udp_ping_node debe retornar (resultado_dict, categoria, detalle)
    mock_udp.return_value = ({"ip": "1.1.1.1", "udp_port": 16005, "lat": 10, "lng": 20, "rtt": 50}, CATEGORY_PONG, "OK")
    
    with patch("json.dump") as mock_write:
        ping_all_nodes()
        assert mock_write.called
        data = mock_write.call_args[0][0]
        assert data[0]["ip"] == "1.1.1.1"
        assert data[0]["rtt"] == 50

def test_pinger_geolocate_nodes():
    """
    Objetivo: Validar que el pinger integra correctamente el motor de geolocalización para enriquecer los datos de los nodos.
    Funciones: geolocate_nodes(), KadGeolocator.get_location()
    """
    from backend.kad_udp_pinger import geolocate_nodes, GEO_CACHE
    GEO_CACHE.clear()
    with patch("IP2Location.IP2Location") as mock_db:
        instance = mock_db.return_value
        rec = MagicMock()
        rec.latitude = 10.0
        rec.longitude = 20.0
        instance.get_all.return_value = rec
        
        with patch("os.path.exists", return_value=True):
            nodes = [{"ip": "1.1.1.1"}]
            result = geolocate_nodes(nodes)
            assert result[0]["lat"] == 10.0

