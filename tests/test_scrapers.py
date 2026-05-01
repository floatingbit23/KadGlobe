import pytest
from unittest.mock import MagicMock, patch
from backend.kadglobe_scraper import EMuleWebScraper
from backend.kadglobe_scraper_aMule import AMuleWebScraper

@pytest.fixture
def mock_emule_response():
    """Simula una respuesta HTML de la página de estadísticas de eMule."""
    return """
Kad Overhead (Packets): 1.5 KB (200 bytes)
Kad Overhead (Packets): 10 MB (500 KB)
Kad: 1000 (15.5%)
Firewalled (Kad) UDP: 10.5% TCP: 5.2% Low ID
via Kad: 150
    """

def test_emule_scraper_parsing(mock_emule_response):
    """
    Objetivo: Verificar que el scraper de eMule extrae correctamente las métricas (overhead, clientes, sources) de un HTML real.
    Funciones: EMuleWebScraper.fetch_stats_kad_data()
    """
    scraper = EMuleWebScraper()
    scraper.session_id = "12345"
    
    with patch.object(scraper.session, "get") as mock_get:
        mock_get.return_value.text = mock_emule_response
        stats = scraper.fetch_stats_kad_data()
        
        assert stats["kad_overhead_session_pkts"] == "200 bytes"
        assert stats["kad_overhead_total_pkts"] == "500 KB"
        assert stats["kad_clients_pct"] == "15.5"
        assert stats["kad_firewalled_udp_pct"] == "10.5"
        assert stats["kad_sources_found"] == "150"

def test_amule_scraper_full_flow():
    """
    Objetivo: Validar el flujo completo de aMule: login exitoso y extracción de estadísticas desde múltiples páginas PHP.
    Funciones: AMuleWebScraper.login(), AMuleWebScraper.fetch_kad_stats()
    """
    scraper = AMuleWebScraper()
    
    with patch.object(scraper.session, "post") as mock_post:
        mock_post.return_value.text = "amuleweb" # Simular login exitoso
        assert scraper.login() is True
        
    with patch.object(scraper.session, "get") as mock_get:
        # Mock de stats.php (estado) y stats_tree.php (métricas)
        def get_side_effect(url, **kwargs):
            m = MagicMock()
            if "stats.php" in url:
                m.text = "Kad : Connected(OK) - Other info"
            elif "stats_tree.php" in url:
                m.text = "Kad Nodes (Total) : 123\nKad Overhead (Packets): 1.5 KB (200 bytes)\nKad: 1000 (15.5%)\nFirewalled (Kad) UDP: 1.0% TCP: 0.0% Low ID"
            else:
                m.text = "Generic response"
            return m
            
        mock_get.side_effect = get_side_effect
        stats = scraper.fetch_kad_stats()
        
        assert stats["status"] == "Connected"
        assert stats["contacts"] == "123"
        assert stats["kad_firewalled_udp_pct"] == "1.0"

def test_emule_version_detection():
    """
    Objetivo: Comprobar que el scraper identifica correctamente la versión de eMule mediante el título o el cuerpo del HTML.
    Funciones: EMuleWebScraper.fetch_emule_version()
    """
    scraper = EMuleWebScraper()
    scraper.session_id = "54321"
    
    with patch.object(scraper.session, "get") as mock_get:
        # Caso 1: Detección via <title>
        mock_get.return_value.text = "<html><title>eMule v0.50a - WebControl</title></html>"
        assert scraper.fetch_emule_version() == "eMule v0.50a"
        
        # Caso 2: Detección via body text
        mock_get.return_value.text = "<html><body>Running eMule v0.60d now</body></html>"
        assert scraper.fetch_emule_version() == "eMule v0.60d"

def test_scraper_login_success():
    """
    Objetivo: Validar que el scraper de eMule captura correctamente el ID de sesión tras un login exitoso.
    Funciones: EMuleWebScraper.login()
    """
    scraper = EMuleWebScraper()
    with patch.object(scraper.session, "post") as mock_post:
        # eMule redirige con el ses=ID en el cuerpo o URL
        mock_post.return_value.text = '<meta http-equiv="refresh" content="0; url=?ses=abcde123">'
        assert scraper.login() is True
        assert scraper.session_id == "abcde123"

def test_scraper_login_fail():
    """
    Objetivo: Asegurar que el sistema detecta y maneja adecuadamente los fallos de autenticación (contraseña incorrecta).
    Funciones: EMuleWebScraper.login()
    """
    scraper = EMuleWebScraper()
    with patch.object(scraper.session, "post") as mock_post:
        mock_post.return_value.text = "Invalid password"
        assert scraper.login() is False
        assert scraper.session_id is None

def test_emule_fetch_kad_stats():
    """
    Objetivo: Verificar la extracción consolidada de estados de conexión y número de contactos Kad en eMule.
    Funciones: EMuleWebScraper.fetch_kad_stats()
    """
    scraper = EMuleWebScraper()
    scraper.session_id = "abc"
    
    html_kad = "Kad Status Connected Contacts Current Searches 100 5"
    with patch.object(scraper.session, "get") as mock_get:
        # Primero pide la página de Kad, luego Stats
        def side_effect(url, **kwargs):
            m = MagicMock()
            if "w=kad" in url:
                m.text = html_kad
            else:
                m.text = "Kad Overhead (Packets): 1.5 KB (200 bytes)\nKad Overhead (Packets): 10 MB (500 KB)\nKad: 1000 (15.5%)"
            return m
        mock_get.side_effect = side_effect
        
        with patch.object(scraper, "fetch_local_kad_id", return_value="fca7f5"):
            stats = scraper.fetch_kad_stats()
            assert stats["status"] == "Connected"
            assert stats["contacts"] == "100"
            assert stats["local_id"] == "fca7f5"

def test_fetch_local_kad_id(tmp_path):
    """
    Objetivo: Validar la lectura del ID de nodo local desde el archivo key_index.dat binario.
    Funciones: EMuleWebScraper.fetch_local_kad_id()
    """
    scraper = EMuleWebScraper()
    dummy_key = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12\x13\x14\x15\x16"
    key_file = tmp_path / "key_index.dat"
    key_file.write_bytes(dummy_key)
    
    with patch("os.getenv", return_value=str(key_file)):
        with patch("os.path.exists", return_value=True):
            kid = scraper.fetch_local_kad_id()
            assert kid == dummy_key.hex()

def test_emule_scraper_401_error():
    """
    Objetivo: Verificar la resiliencia del scraper ante errores 401 (No autorizado) devolviendo datos nulos seguros.
    Funciones: EMuleWebScraper.fetch_stats_kad_data()
    """
    scraper = EMuleWebScraper()
    scraper.session_id = "expired_session"
    
    with patch.object(scraper.session, "get") as mock_get:
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = "Unauthorized"
        
        # En caso de error de red o 401, el scraper debería devolver valores por defecto o vacíos
        stats = scraper.fetch_stats_kad_data()
        assert stats["kad_clients_pct"] == "0"
        assert stats["kad_sources_found"] == "0"

def test_emule_scraper_empty_response():
    """
    Objetivo: Asegurar que el scraper no falla ante respuestas HTTP vacías, inicializando los contadores a "0".
    Funciones: EMuleWebScraper.fetch_stats_kad_data()
    """
    scraper = EMuleWebScraper()
    scraper.session_id = "valid"
    
    with patch.object(scraper.session, "get") as mock_get:
        mock_get.return_value.text = "" # Respuesta vacía
        stats = scraper.fetch_stats_kad_data()
        
        # El scraper debería inicializar el dict pero no encontrar nada (matches fallidos)
        assert stats["kad_clients_pct"] == "0"
        assert stats["kad_firewalled_udp_pct"] == "0"
