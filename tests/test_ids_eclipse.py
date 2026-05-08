import pytest
from backend.ids_engine import KadIDSEngine

@pytest.fixture
def ids_engine(tmp_path):
    history_file = tmp_path / "ids_history.json"
    alerts_file = tmp_path / "ids_alerts.json"
    return KadIDSEngine(history_path=str(history_file), alerts_path=str(alerts_file))

def test_detect_eclipse_critical(ids_engine):
    """Test de detección de ataque Eclipse crítico (>5 nodos en buckets cercanos)."""
    local_id = "00000000000000000000000000000000"
    stats = {"local_id": local_id}
    
    # Generamos 7 nodos muy cercanos (Buckets 120-127)
    # LSB diferente -> Bucket 127
    nodes = []
    for i in range(7):
        node_id = "000000000000000000000000000000" + hex(i+1)[2:].zfill(2)
        nodes.append({"id": node_id, "ip": f"1.1.1.{i}"})
    
    # Añadimos algunos nodos lejanos para que el Chi-cuadrado no explote por falta de datos
    # MSB diferente -> Bucket 0
    nodes.append({"id": "80000000000000000000000000000000", "ip": "2.2.2.2"})
    nodes.append({"id": "C0000000000000000000000000000000", "ip": "3.3.3.3"})

    alerts, chi_p, bucket_counts = ids_engine._detect_eclipse(stats, nodes)
    
    # Debería haber una alerta crítica de Eclipse
    eclipse_alerts = [a for a in alerts if a["type"] == "eclipse" and a["severity"] == "critical"]
    assert len(eclipse_alerts) > 0
    assert "B117-B127" in eclipse_alerts[0]["detail_es"]

def test_detect_sybil_concentration(ids_engine):
    """Test de detección de ataque Sybil (concentración de IPs en un bucket)."""
    local_id = "00000000000000000000000000000000"
    stats = {"local_id": local_id}
    
    # 4 nodos de la misma subred /24 en el mismo bucket (Bucket 125)
    # Distancias 4, 5, 6, 7 -> bit_length 3 -> bit_pos 2 -> 127-2 = 125
    nodes = []
    for i in range(4, 8):
        node_id = "000000000000000000000000000000" + hex(i)[2:].zfill(2)
        nodes.append({"id": node_id, "ip": f"192.168.1.{i}"})
    
    alerts, chi_p, bucket_counts = ids_engine._detect_eclipse(stats, nodes)
    
    # Debería haber una alerta de Sybil
    sybil_alerts = [a for a in alerts if a["type"] == "sybil"]
    assert len(sybil_alerts) > 0
    assert "192.168.1" in sybil_alerts[0]["detail_es"]

def test_analyze_integration_eclipse(ids_engine):
    """Test de integración del método analyze para Eclipse."""
    stats = {
        "local_id": "00000000000000000000000000000000",
        "contacts": 100,
        "kad_overhead_session_pkts": "0"
    }
    # 6 nodos en proximidad crítica
    nodes = []
    for i in range(6):
        node_id = "000000000000000000000000000000" + hex(i+1)[2:].zfill(2)
        nodes.append({"id": node_id, "ip": "1.1.1.1"})
        
    result = ids_engine.analyze(stats, nodes, [])
    
    assert result["global_severity"] == "critical"
    types = [a["type"] for a in result["alerts"]]
    assert "eclipse" in types
