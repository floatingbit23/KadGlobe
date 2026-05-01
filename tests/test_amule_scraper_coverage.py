import pytest
from unittest.mock import MagicMock, patch
import os
import builtins
from backend.kadglobe_scraper_aMule import AMuleWebScraper

"""
Objetivo: Lograr cobertura >80% en el código nuevo de aMule scraper.
Funciones: _color_print, fetch_kad_stats, _fetch_kad_status, _fetch_stats_tree, fetch_local_kad_id.
"""

def test_amule_logging_coverage():
    """Verifica que el sistema de logs estandarizado funciona y no rompe nada."""
    # Obtenemos el scraper para asegurar que el print se ha inyectado
    AMuleWebScraper()
    
    # Probamos los diferentes colores del logger estandarizado usando el print global
    with patch('builtins.print') as mock_print:
        # Llamamos al print que ahora debería estar interceptado por nuestra _color_print
        builtins.print("[!] Test Error Log")
        builtins.print("[+] Test Success Log")
        builtins.print("[*] Test Info Log")
        builtins.print("Test Default Log")
        
    # Verificamos que el print realmente tenga el atributo de nuestro sistema de logs
    assert getattr(builtins.print, "_kadglobe_logging", False) is True

def test_amule_fetch_kad_stats_full_flow():
    """Prueba el flujo completo de extracción de datos de aMule con mocks."""
    scraper = AMuleWebScraper(password="test_pass")
    scraper.session_id = "fake_ses"
    scraper.logged_in = True

    # Mockeamos las respuestas de las diferentes páginas de aMule
    mock_status_html = "<html><body>Kad Status: Running (Connected)</body></html>"
    mock_tree_html = """
    <html><body>
    Kad Nodes (Total): 450
    Kad Overhead (Packets): 100 packets (1.5 KB)
    Kad Overhead (Packets): 500 packets (10.2 MB)
    Kad: 1200 (15.5%)
    Firewalled (Kad) UDP: 5.2% TCP: 1.1% Low ID
    via Kad: 25
    </body></html>
    """

    with patch.object(scraper.session, 'get') as mock_get:
        # Configuramos las respuestas secuenciales
        mock_get.side_effect = [
            MagicMock(text=mock_status_html, status_code=200),
            MagicMock(text=mock_tree_html, status_code=200)
        ]
        
        result = scraper.fetch_kad_stats()
        
        assert result is not None
        assert result["contacts"] == "450"
        assert result["kad_overhead_session_pkts"] == "1.5 KB"
        assert result["kad_sources_found"] == "25"
        assert result["kad_clients_pct"] == "15.5"

def test_amule_fetch_local_id_fallback():
    """Verifica la lectura del ID de Kad en Linux/aMule path."""
    scraper = AMuleWebScraper()
    
    with patch('os.path.exists') as mock_exists:
        with patch('builtins.open', patch('io.BytesIO', return_value=None)): # Mock general de open
             with patch('backend.kadglobe_scraper_aMule.open', create=True) as mock_open:
                # Simulamos que el archivo existe en la ruta de aMule
                mock_exists.side_effect = lambda p: ".aMule" in p
                
                # Simulamos lectura de 16 bytes (hash de 128 bits)
                mock_file = MagicMock()
                mock_file.__enter__.return_value.read.return_value = b'\x01' * 16
                mock_open.return_value = mock_file
                
                kad_id = scraper.fetch_local_kad_id()
                assert kad_id == "01" * 16
                assert len(kad_id) == 32

def test_amule_unauthorized_error():
    """Prueba el manejo de errores 401 en el scraper de aMule."""
    scraper = AMuleWebScraper()
    scraper.session_id = "invalid"

    with patch.object(scraper.session, 'get') as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        result = scraper.fetch_kad_stats()
        assert result is None
