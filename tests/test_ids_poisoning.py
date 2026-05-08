import pytest
import os
import json
from backend.ids_engine import KadIDSEngine

@pytest.fixture
def ids_engine(tmp_path):
    history_file = tmp_path / "ids_history.json"
    alerts_file = tmp_path / "ids_alerts.json"
    return KadIDSEngine(history_path=str(history_file), alerts_path=str(alerts_file))

def test_detect_poisoning_normal(ids_engine):
    """Test que una distribución normal no genera alertas de poisoning."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    # Distribución uniforme: 2 nodos por bucket en 10 buckets
    bucket_counts = {i: 2 for i in range(10)}
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) == 0

def test_detect_poisoning_local_anomaly(ids_engine):
    """Test de detección de envenenamiento local (un bucket destaca sobre el resto)."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    # Mayoría con 2 nodos, uno con 20 nodos
    bucket_counts = {i: 2 for i in range(10)}
    bucket_counts[5] = 20 # El bucket 5 tiene 10x la media
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) > 0
    assert any(a["type"] == "poisoning" for a in alerts)
    assert alerts[0]["indicator"]["bucket"] == 5 or alerts[0]["indicator"]["bucket"] == "5"

def test_detect_poisoning_min_population_filter(ids_engine):
    """Test que el filtro de población mínima (5) evita alertas ruidosas."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    # Un bucket tiene 4 nodos, otros tienen 0.1 (matemáticamente alto Z, pero poca población)
    bucket_counts = {0: 0.1, 1: 0.1, 2: 4} 
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) == 0 # El bucket 2 tiene < 5 nodos

def test_detect_poisoning_temporal_anomaly(ids_engine):
    """Test de detección de envenenamiento temporal (un bucket crece respecto a su pasado)."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    
    # Llenamos el historial con valores bajos para el bucket 10 (media 1)
    for _ in range(10):
        ids_engine.history.append({
            "timestamp": "2026-05-08T00:00:00",
            "bucket_counts": {"10": 1, "0": 1}
        })
    
    # Situación actual: el bucket 10 salta a 15 nodos
    # (Localmente podría no destacar si otros también son altos, pero temporalmente sí)
    bucket_counts = {"10": 15, "0": 15}
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) > 0
    # Debería detectar el bucket 10 (Z temporal alto)
    poisoned_buckets = [str(a["indicator"]["bucket"]) for a in alerts]
    assert "10" in poisoned_buckets

def test_analyze_integration_poisoning(ids_engine):
    """Test de integración del motor completo con Poisoning."""
    stats = {
        "local_id": "ABCDEF1234567890ABCDEF1234567890",
        "contacts": 100,
        "kad_overhead_session_pkts": "10 k"
    }
    # Simulamos 100 nodos en el bucket 127 (Ataque masivo)
    nodes = [{"id": "ABCDEF1234567890ABCDEF1234567891", "ip": "1.1.1.1"} for _ in range(100)]
    # Añadimos 20 buckets con 1 nodo cada uno (Fondo)
    for i in range(20):
        fake_id = list("ABCDEF1234567890ABCDEF1234567890")
        # Cambiamos bytes para asegurar buckets distintos (distancia XOR varía)
        fake_id[i % 30] = hex((i + 1) % 16)[2:]
        nodes.append({"id": "".join(fake_id), "ip": f"2.2.2.{i}"})
    
    alerts_data = ids_engine.analyze(stats, nodes, [])
    
    # Debería haber alertas de Eclipse (por proximidad) y Poisoning (por pico en B127)
    types = [a["type"] for a in alerts_data["alerts"]]
    assert "eclipse" in types
    assert "poisoning" in types
    assert alerts_data["global_severity"] == "critical"
