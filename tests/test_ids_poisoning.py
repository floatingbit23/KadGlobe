import pytest
import os
import json
from backend.ids_engine import KadIDSEngine

@pytest.fixture
def ids_engine(tmp_path):
    history_file = tmp_path / "ids_history.json"
    alerts_file = tmp_path / "ids_alerts.json"
    engine = KadIDSEngine(history_path=str(history_file), alerts_path=str(alerts_file))
    engine.cycle_count = 10 # Pasamos el filtro de arranque frío
    return engine

def test_detect_poisoning_theoretical_normal(ids_engine):
    """Test que una distribución que sigue la ley de potencias NO genera alertas."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    
    # 100 nodos totales distribuidos teóricamente (B127 far, B0 close):
    # B127: 50, B126: 25, B125: 12, B124: 6, B123: 3, B122: 2...
    bucket_counts = {
        "127": 50, "126": 25, "125": 12, "124": 6, "123": 3, "122": 2, "121": 1, "120": 1
    }
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    # No debería haber alertas porque el Bucket 127 (Far) con 50 es lo ESPERADO
    assert len(alerts) == 0

def test_detect_poisoning_neighbor_critical(ids_engine):
    """Test que pocos nodos en el vecindario (bucket alto) disparan alerta crítica."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    
    # 100 nodos totales. Esperanza en B5 es casi 0.
    # Si encontramos 10 nodos en B5, es un ataque claro.
    bucket_counts = {str(127-i): 2 for i in range(10)} # 20 nodos lejanos (B127-B118)
    bucket_counts["5"] = 10                      # 10 nodos muy cercanos (ANOMALÍA)
    bucket_counts["127"] = 50                    # Añadimos nodos para pasar el umbral de 50 totales
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) > 0
    assert any(a["type"] == "poisoning" and a["severity"] == "critical" for a in alerts)
    assert any("B5" in a["detail_es"] for a in alerts)

def test_detect_poisoning_far_bucket_noise_reduction(ids_engine):
    """Test que el Bucket 0 no genera ruido si tiene una población razonable aunque sea alta."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    
    # Tenemos 150 nodos totales. El B127 tiene 80.
    # Esperanza teórica para B127 es 75 (150/2). 80 es muy normal.
    bucket_counts = {"127": 80, "126": 40, "125": 20, "124": 10} 
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) == 0 

def test_detect_poisoning_far_bucket_massive_flood(ids_engine):
    """Test que si el B0 tiene una inundación REALMENTE masiva (p.ej. 500 nodos), sí alerta."""
    stats = {"local_id": "ABCDEF1234567890ABCDEF1234567890"}
    
    # Total = 600 nodos. B127 tiene 500 (Esperanza 300).
    # Z-score será alto (> 4.0).
    bucket_counts = {"127": 500, "126": 50, "125": 25, "124": 15, "123": 10}
    
    alerts = ids_engine._detect_poisoning(stats, bucket_counts)
    assert len(alerts) > 0
    assert alerts[0]["indicator"]["bucket"] == 127

def test_analyze_integration_neighborhood_poisoning(ids_engine):
    """Test de integración: el motor prioriza el vecindario."""
    stats = {
        "local_id": "ABCDEF1234567890ABCDEF1234567890",
        "contacts": 200,
        "kad_overhead_session_pkts": "10 k"
    }
    
    # Simulamos un ataque de Eclipse/Poisoning en el vecindario (B127)
    # ID local: ABCDEF...90
    # ID atacante: ABCDEF...91 (Difieren solo en el último bit -> Bucket 159 o 127 según implementación)
    # En nuestro kad_utils, 127 es el máximo.
    nodes = []
    # 25 nodos en el mismo bucket cercano
    for _ in range(25):
        nodes.append({"id": "ABCDEF1234567890ABCDEF1234567891", "ip": "1.1.1.1"})
    
    # 100 nodos "normales" para dar volumen
    for i in range(100):
        nodes.append({"id": f"{i:032x}", "ip": f"2.2.2.{i}"})
        
    alerts_data = ids_engine.analyze(stats, nodes, [])
    
    # Debe detectar la anomalía de Poisoning en el vecindario
    types = [a["type"] for a in alerts_data["alerts"]]
    assert "poisoning" in types
    
    # La severidad debe ser crítica por la cercanía (idx < 10)
    assert any(a["severity"] == "critical" for a in alerts_data["alerts"] if a["type"] == "poisoning")
