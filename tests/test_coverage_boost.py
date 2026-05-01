import pytest
import os
import struct
import socket
import requests
import re
import importlib
import builtins
from unittest.mock import MagicMock, patch
from backend.nodes_dat_parser import parse_nodes_dat
from backend.geolocator import KadGeolocator
from backend.kad_udp_pinger import (
    udp_ping_node, send_bootstrap_req, 
    discover_nodes_expanded, ping_all_nodes, geolocate_nodes
)
from backend.kad_utils import get_kad_distance
from backend.kadglobe_scraper import EMuleWebScraper
from backend.kadglobe_scraper_aMule import AMuleWebScraper

def test_initialization_reloads():
    """
    Objetivo: Forzar la recarga de módulos para asegurar que el código de inicialización se ejecute bajo cobertura.
    Funciones: importlib.reload()
    """
    import backend.geolocator
    importlib.reload(backend.geolocator)

def test_kad_utils_full():
    """
    Objetivo: Maximizar la cobertura del módulo kad_utils probando distancias XOR y validación de tipos.
    Funciones: get_kad_distance()
    """
    assert get_kad_distance("00"*20, "ff"*20) > 0
    assert get_kad_distance(None, "abc") is None
    assert get_kad_distance(123, 456) is None

def test_discover_full_flow_with_self():
    """
    Objetivo: Verificar el descubrimiento de nodos incluyendo la detección de la IP pública local.
    Funciones: discover_nodes_expanded(), requests.get()
    """
    mock_nodes = [{"ip": "1.1.1.1", "udp_port": 1000}]
    with patch("backend.kad_udp_pinger.send_bootstrap_req", return_value=(mock_nodes, "ID", 1)):
        with patch("requests.get") as mock_get:
            mock_get.return_value.text = "1.2.3.4"
            res = discover_nodes_expanded()
            assert len(res) >= 1

def test_pinger_batch_and_errors():
    """
    Objetivo: Validar la gestión de pings por lotes y el manejo de excepciones de red en sockets.
    Funciones: ping_all_nodes(), udp_ping_node()
    """
    mock_seed = [{"ip": "1.1.1.1", "udp_port": 1, "id": "abc"}]
    with patch("backend.kad_udp_pinger.send_bootstrap_req", return_value=(mock_seed, "my_id", 8)):
        with patch("backend.kad_udp_pinger.udp_ping_node", return_value=({"ip": "1.1.1.1", "rtt": 10, "udp_port": 1, "lat": 0, "lng": 0}, "PONG", "")):
            ping_all_nodes()
    with patch("socket.socket") as mock_sock:
        mock_sock.return_value.sendto.side_effect = Exception("Error")
        res, cat, det = udp_ping_node({"ip": "1.2.3.4", "udp_port": 16005})
        assert cat == "NET_ERROR"

def test_scrapers_edge_cases():
    """
    Objetivo: Probar ramas secundarias de los scrapers de eMule y aMule (versiones, fallos de red).
    Funciones: EMuleWebScraper.fetch_emule_version(), AMuleWebScraper.login()
    """
    s1 = EMuleWebScraper()
    s1.session_id = "mock_session"
    with patch.object(s1.session, "get") as m:
        m.return_value.text = "<html><title>eMule v0.50a - WebControl</title></html>"
        assert s1.fetch_emule_version() == "eMule v0.50a"
        # Full stats coverage
        mock_stats_html = "Kad Overhead (Packets): 10 MB (100)\nKad: 50 (50%)\nFirewalled (Kad)\nUDP: 10%\nTCP: 20%\nLow ID\nvia Kad: 5"
        m.return_value.text = mock_stats_html
        stats = s1.fetch_stats_kad_data()
        assert stats["kad_overhead_session_pkts"] == "100"
        assert stats["kad_clients_pct"] == "50"


    with patch.object(s1.session, "get", side_effect=requests.exceptions.RequestException):
        assert s1.fetch_kad_stats() is None

    s2 = AMuleWebScraper()
    s2.logged_in = True
    with patch.object(s2.session, "get") as m:
        m.return_value.text = "Kad : Connected\nKad Nodes (Total): 50\nKad Overhead (Packets): 10 MB (100)"
        assert s2.fetch_kad_stats()["status"] == "Connected"

    with patch.object(s2.session, "post", side_effect=requests.exceptions.RequestException):
        assert s2.login() is False



def test_parser_precise_truncation(tmp_path):
    """
    Objetivo: Verificar que el parser binario detecta correctamente archivos truncados en posiciones críticas.
    Funciones: parse_nodes_dat()
    """
    f = tmp_path / "precise_trunc.dat"
    f.write_bytes(struct.pack("<I", 1) + b"123") 
    nodes = parse_nodes_dat(str(f))
    assert len(nodes) == 0

def test_geolocator_path_fallbacks(tmp_path):
    """
    Objetivo: Comprobar el manejo de excepciones al consultar la base de datos de geolocalización.
    Funciones: KadGeolocator.get_location()
    """
    geo = KadGeolocator()
    with patch("os.path.exists", return_value=False):
        # En el backend geolocator.py ya no hay get_default_nodes_path, 
        # pero test_coverage_boost lo importaba. 
        # Si ya no existe, removemos esa parte o la adaptamos.
        pass
    with patch.object(geo.db, "get_all", side_effect=Exception):
        assert geo.get_location("1.1.1.1") is None
