import pytest
from unittest.mock import patch, MagicMock

def test_geolocator_import():
    """
    Objetivo: Verificar que el módulo de geolocalización es importable y la clase principal existe.
    Funciones: import backend.geolocator
    """
    from backend.geolocator import KadGeolocator
    assert KadGeolocator is not None

def test_pinger_import():
    """
    Objetivo: Confirmar que las funciones del motor de pings UDP están disponibles para su ejecución.
    Funciones: import backend.kad_udp_pinger
    """
    from backend.kad_udp_pinger import ping_all_nodes, udp_ping_node
    assert ping_all_nodes is not None
    assert udp_ping_node is not None

def test_nodes_parser_import():
    """
    Objetivo: Asegurar que el componente de parsing binario puede ser cargado correctamente.
    Funciones: import backend.nodes_dat_parser
    """
    from backend.nodes_dat_parser import parse_nodes_dat
    assert parse_nodes_dat is not None

def test_scraper_emule_import():
    """
    Objetivo: Validar la disponibilidad del scraper específico para eMule WebUI.
    Funciones: import backend.kadglobe_scraper
    """
    from backend.kadglobe_scraper import EMuleWebScraper
    assert EMuleWebScraper is not None

def test_scraper_amule_import():
    """
    Objetivo: Validar la disponibilidad del scraper específico para aMule WebUI (Linux).
    Funciones: import backend.kadglobe_scraper_aMule
    """
    from backend.kadglobe_scraper_aMule import AMuleWebScraper
    assert AMuleWebScraper is not None
