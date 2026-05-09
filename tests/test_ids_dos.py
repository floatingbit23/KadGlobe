import pytest
from backend.ids_engine import KadIDSEngine
import json
import os

@pytest.fixture
def ids_engine(tmp_path):
    # Setup temporal para no ensuciar el historial real
    history_file = tmp_path / "ids_history.json"
    alerts_file = tmp_path / "ids_alerts.json"
    engine = KadIDSEngine(history_path=str(history_file), alerts_path=str(alerts_file))
    engine.cycle_count = 10 # Bypass warm-up for tests
    return engine

def test_dos_normal_traffic(ids_engine):
    """Prueba que el tráfico normal no dispare alertas."""
    # Llenamos historial con 20 muestras estables (2000 bytes de salto)
    for i in range(21):
        stats = {"kad_overhead_session_pkts": f"{i * 2000}"}
        ids_engine._update_history(stats)
    
    # Muestra actual con salto normal (2000 bytes)
    stats_now = {"kad_overhead_session_pkts": f"{21 * 2000 + 2000}", "active_searches": 0}
    ids_engine._update_history(stats_now)
    alerts = ids_engine._detect_dos() 
    
    dos_alerts = [a for a in alerts if a["type"] == "dos"]
    assert len(dos_alerts) == 0

def test_dos_warning_ratio(ids_engine):
    """Prueba detección de pico 4x (Warning)."""
    # 20 muestras estables (2000 bytes de delta)
    for i in range(21):
        stats = {"kad_overhead_session_pkts": f"{i * 2000}"}
        ids_engine._update_history(stats)
    
    # Salto brusco de 8000 bytes (4x la media de 2000)
    stats_now = {"kad_overhead_session_pkts": f"{21 * 2000 + 8000}", "active_searches": 0}
    ids_engine._update_history(stats_now)
    
    alerts = ids_engine._detect_dos()
    dos_alerts = [a for a in alerts if a["type"] == "dos" and a["severity"] == "warning"]
    assert len(dos_alerts) > 0
    assert "x la media" in dos_alerts[0]["detail_es"]

def test_dos_critical_ratio(ids_engine):
    """Prueba detección de pico 11x (Critical)."""
    for i in range(21):
        stats = {"kad_overhead_session_pkts": f"{i * 2000}"}
        ids_engine._update_history(stats)
    
    # Salto de 22000 bytes (11x la media de 2000)
    stats_now = {"kad_overhead_session_pkts": f"{21 * 2000 + 22000}", "active_searches": 0}
    ids_engine._update_history(stats_now)
    
    alerts = ids_engine._detect_dos()
    dos_alerts = [a for a in alerts if a["type"] == "dos" and a["severity"] == "critical"]
    assert len(dos_alerts) > 0

def test_dos_exponential_growth(ids_engine):
    """Prueba detección de crecimiento exponencial (M3/M2 > 2 AND M2/M1 > 2)."""
    # M1: 600 (pasa filtro >500), M2: 1800 (ratio 3), M3: 6000 (ratio 3.3)
    history_data = [
        {"overhead": 1000, "active_searches": 0}, # Base
        {"overhead": 1600, "active_searches": 0}, # Delta 600 (M1)
        {"overhead": 3400, "active_searches": 0}, # Delta 1800 (M2)
        {"overhead": 9400, "active_searches": 0}, # Delta 6000 (M3)
    ]
    ids_engine.history = history_data
    
    # Bypass warm-up for testing
    ids_engine.cycle_count = 10
    
    alerts = ids_engine._detect_dos()
    dos_alerts = [a for a in alerts if a["type"] == "dos" and a["severity"] == "critical"]
    assert len(dos_alerts) > 0
    assert "exponencial" in dos_alerts[0]["detail_es"].lower()

def test_dos_ignore_with_searches(ids_engine):
    """Prueba que ignore picos si hay búsquedas activas significativas."""
    for i in range(21):
        stats = {"kad_overhead_session_pkts": f"{i * 2000}"}
        ids_engine._update_history(stats)
    
    # Pico de 10x pero con 5 búsquedas
    stats_now = {"kad_overhead_session_pkts": f"{21 * 2000 + 20000}", "active_searches": 5}
    ids_engine._update_history(stats_now)
    
    alerts = ids_engine._detect_dos()
    dos_alerts = [a for a in alerts if a["type"] == "dos"]
    assert len(dos_alerts) == 0

def test_dos_counter_reset(ids_engine):
    """Prueba que el sistema no explote si el contador de eMule se reinicia."""
    # Historial alto
    ids_engine.history = [{"overhead": 50000, "active_searches": 0}]
    
    # Bypass warm-up for testing
    ids_engine.cycle_count = 10
    
    # Muestra nueva con valor bajo (reinicio)
    stats_now = {"kad_overhead_session_pkts": "100", "active_searches": 0}
    ids_engine._update_history(stats_now)
    
    # No debería haber alerta (delta = 0)
    alerts = ids_engine._detect_dos()
    assert len(alerts) == 0
