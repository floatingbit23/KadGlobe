import pytest
import os
import sys
from unittest.mock import MagicMock

# Añadimos el directorio raíz al path para poder importar desde 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.kad_utils import get_kad_distance, get_kad_bucket
from backend.nodes_dat_parser import parse_nodes_dat
from backend.geolocator import KadGeolocator

# 1. Verificar la lógica XOR y Buckets
def test_xor_logic():
    """
    Objetivo: Validar los cálculos matemáticos de distancia lógica y asignación de buckets en Kademlia.
    Funciones: get_kad_distance(), get_kad_bucket()
    """
    id_self = "00000000000000000000000000000000"
    id_far  = "80000000000000000000000000000000" # MSB diferente -> Bucket 127
    id_near = "00000000000000000000000000000001" # LSB diferente -> Bucket 0
    
    assert get_kad_bucket(id_self, id_far) == 127
    assert get_kad_bucket(id_self, id_near) == 0
    assert get_kad_distance(id_self, id_self) == 0
    assert get_kad_bucket(id_self, id_self) == 0

# 2. Verificar robustez del parser de nodes.dat
def test_parser_robustness(tmp_path):
    """
    Objetivo: Comprobar la resiliencia del parser binario ante archivos inexistentes o corruptos.
    Funciones: parse_nodes_dat()
    """
    # Test con archivo inexistente
    nodes = parse_nodes_dat("non_existent_file.dat")
    assert nodes == []
    
    # Test con archivo corrupto (demasiado pequeño)
    corrupt_file = tmp_path / "corrupt.dat"
    corrupt_file.write_bytes(b"\x00\x00\x01") # Solo 3 bytes
    nodes = parse_nodes_dat(str(corrupt_file))
    assert nodes == []

# 3. Verificar geolocalización (Mockeando IP2Location para no depender del binario)
def test_geolocator_valid_coords():
    """
    Objetivo: Validar que el geolocalizador traduce correctamente los datos del binario a un diccionario estructurado.
    Funciones: KadGeolocator.get_location()
    """
    geo = KadGeolocator()
    # Forzamos un mock en el objeto db si existe, o simulamos uno
    geo.db = MagicMock()
    
    mock_rec = MagicMock()
    mock_rec.latitude = 40.4167
    mock_rec.longitude = -3.7033
    mock_rec.city = "Madrid"
    mock_rec.country_long = "Spain"
    mock_rec.country_short = "ES"
    
    geo.db.get_all.return_value = mock_rec
    
    result = geo.get_location("1.1.1.1")
    assert result["lat"] == pytest.approx(40.4167)
    assert result["lng"] == pytest.approx(-3.7033)
    assert result["country"] == "Spain"

# 4. Verificar manejo de IPs inválidas o sin datos
def test_geolocator_invalid_ip():
    """
    Objetivo: Asegurar que el sistema maneja IPs desconocidas devolviendo coordenadas 0.0.
    Funciones: KadGeolocator.get_location()
    """
    geo = KadGeolocator()
    geo.db = MagicMock()
    
    # Simulamos que IP2Location devuelve un registro con 0,0 (lo que suele pasar si no encuentra la IP)
    mock_rec = MagicMock()
    mock_rec.latitude = 0.0
    mock_rec.longitude = 0.0
    geo.db.get_all.return_value = mock_rec
    
    result = geo.get_location("invalid_ip")
    assert result["lat"] == pytest.approx(0.0)
    assert result["lng"] == pytest.approx(0.0)
