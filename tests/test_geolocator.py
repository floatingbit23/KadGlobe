import pytest
from unittest.mock import MagicMock, patch
from backend.geolocator import KadGeolocator

@pytest.fixture
def mock_db():
    """Mock de la base de datos IP2Location."""
    with patch("IP2Location.IP2Location") as mock:
        instance = mock.return_value
        
        def side_effect(ip):
            rec = MagicMock()
            if ip == "0.0.0.0":
                rec.latitude = 0.0
                rec.longitude = 0.0
                rec.city = "Unknown"
                rec.country_long = "Unknown"
                rec.country_short = "??"
            else:
                rec.latitude = 40.4167
                rec.longitude = -3.7033
                rec.city = "Madrid"
                rec.country_long = "Spain"
                rec.country_short = "ES"
            return rec
            
        instance.get_all.side_effect = side_effect
        yield instance

def test_get_location_success(mock_db):
    """
    Objetivo: Verificar que una dirección IP válida se geolocaliza correctamente devolviendo coordenadas y ciudad.
    Funciones: KadGeolocator.get_location()
    """
    with patch("os.path.exists", return_value=True):
        geo = KadGeolocator()
        loc = geo.get_location("1.2.3.4")
        
        assert loc["lat"] == 40.4167
        assert loc["city"] == "Madrid"
        assert loc["country_code"] == "es"

def test_get_location_invalid_db():
    """
    Objetivo: Comprobar que el sistema maneja correctamente la ausencia de la base de datos IP2Location.
    Funciones: KadGeolocator.__init__(), KadGeolocator.get_location()
    """
    with patch("os.path.exists", return_value=False):
        geo = KadGeolocator()
        assert geo.get_location("1.2.3.4") is None

def test_process_kad_nodes(mock_db, tmp_path):
    """
    Objetivo: Validar el flujo completo de lectura de nodes.dat, geolocalización de IPs y exportación a JSON.
    Funciones: KadGeolocator.process_kad_nodes(), parse_nodes_dat()
    """
    mock_nodes = [
        {"id": "abc", "ip": "1.2.3.4", "udp_port": 123},
        {"id": "def", "ip": "0.0.0.0", "udp_port": 456} # IP inválida para probar el filtro
    ]
    
    # Mockear el parseador de nodes.dat
    with patch("backend.geolocator.parse_nodes_dat", return_value=mock_nodes):
        with patch("os.path.exists", return_value=True):
            geo = KadGeolocator()
            output_file = tmp_path / "output.json"
            
            geo.process_kad_nodes(nodes_file="dummy.dat", output_file=str(output_file))
            
            assert output_file.exists()
            import json
            data = json.loads(output_file.read_text())
            # Debería haber 1 nodo (el de Madrid), el 0.0.0.0 se descarta por el filtro
            assert len(data) == 1
            assert data[0]["city"] == "Madrid"

def test_geolocator_initialization_path():
    """
    Objetivo: Asegurar que la clase KadGeolocator prioriza la ruta de la base de datos configurada en el .env.
    Funciones: KadGeolocator.__init__()
    """
    with patch("os.getenv", return_value="custom_path.bin"):
        with patch("os.path.exists", side_effect=lambda p: p == "custom_path.bin"):
            with patch("IP2Location.IP2Location") as mock_ip2:
                geo = KadGeolocator()
                assert geo.db_path == "custom_path.bin"

def test_get_location_db_corrupt(mock_db):
    """
    Objetivo: Verificar que el sistema es resiliente ante errores inesperados o corrupción de la base de datos IP2Location.
    Funciones: KadGeolocator.get_location()
    """
    with patch("os.path.exists", return_value=True):
        geo = KadGeolocator()
        # Simulamos que get_all lanza una excepción inesperada
        mock_db.get_all.side_effect = Exception("DB Corrupt")
        loc = geo.get_location("8.8.8.8")
        assert loc is None

def test_get_location_not_found(mock_db):
    """
    Objetivo: Confirmar que las IPs no encontradas en la base de datos (lat/lng = 0.0) se identifican para su posterior filtrado.
    Funciones: KadGeolocator.get_location()
    """
    with patch("os.path.exists", return_value=True):
        geo = KadGeolocator()
        # En el fixture, 0.0.0.0 devuelve lat=0.0
        loc = geo.get_location("0.0.0.0")
        assert loc["lat"] == 0.0
        assert loc["city"] == "Unknown"
