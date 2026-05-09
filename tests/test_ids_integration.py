import pytest
import json
import os
from backend.ids_engine import KadIDSEngine

@pytest.fixture
def ids_engine(tmp_path):
    history_file = tmp_path / "ids_history.json"
    alerts_file = tmp_path / "ids_alerts.json"
    return KadIDSEngine(history_path=str(history_file), alerts_path=str(alerts_file))

def test_analyze_generates_valid_json_schema(ids_engine):
    """
    Test de integración: Verifica que analyze() genera un JSON con la estructura correcta.
    """
    stats = {
        "local_id": "00000000000000000000000000000000",
        "contacts": 100,
        "kad_overhead_session_pkts": "10.5 k",
        "active_searches": 0
    }
    nodes = [
        {"id": "00000000000000000000000000000001", "ip": "1.1.1.1"},
        {"id": "80000000000000000000000000000000", "ip": "2.2.2.2"}
    ]
    udp_nodes = [
        {"ip": "8.8.8.8", "lat": 40.0, "lng": -3.0, "rtt": 50}
    ]
    
    # Ejecutamos el análisis
    result = ids_engine.analyze(stats, nodes, udp_nodes)
    
    # 1. Verificamos el retorno de la función
    assert "timestamp" in result
    assert "global_severity" in result
    assert "alerts" in result
    assert isinstance(result["alerts"], list)
    assert "stats" in result
    assert "chi_squared_p_value" in result["stats"]
    assert "contacts_cv" in result["stats"]
    assert "overhead_rate" in result["stats"]
    
    # 2. Verificamos que el archivo se haya escrito en disco
    assert os.path.exists(ids_engine.alerts_path)
    
    with open(ids_engine.alerts_path, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
        
    assert disk_data == result
    
def test_analyze_handles_empty_inputs(ids_engine):
    """Verifica que el motor no crashea con datos vacíos."""
    # Intentamos pasar None o dicts vacíos
    result = ids_engine.analyze({}, [], [])
    assert result["global_severity"] == "ok"
    assert len(result["alerts"]) == 0

def test_analyze_full_cycle_with_alerts(ids_engine):
    """
    Simula un ciclo con múltiples amenazas para verificar la agregación.
    """
    local_id = "00000000000000000000000000000000"
    
    # 1. Fuerza Eclipse (8 nodos cercanos para superar el nuevo umbral >6 con margen)
    nodes = []
    for i in range(8):
        node_id = "000000000000000000000000000000" + hex(i+1)[2:].zfill(2)
        nodes.append({"id": node_id, "ip": "1.1.1.1"})
    
    # 2. Fuerza DoS (incremento súbito de overhead)
    # Necesitamos al menos 5 tasas de referencia + 1 actual = 6+ tasas = 7+ muestras en el historial
    for i in range(7):
        st = {"local_id": local_id, "contacts": 100, "kad_overhead_session_pkts": str(i * 100), "active_searches": 0}
        ids_engine.analyze(st, nodes, [])
    
    # El pico final
    stats_final = {"local_id": local_id, "contacts": 100, "kad_overhead_session_pkts": "25000", "active_searches": 0} # Pico masivo
    result = ids_engine.analyze(stats_final, nodes, [])
    
    assert result["global_severity"] == "critical"
    alert_types = [a["type"] for a in result["alerts"]]
    assert "eclipse" in alert_types
    assert "dos" in alert_types
