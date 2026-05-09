import pytest
import statistics
from backend.ids_engine import KadIDSEngine

def test_churn_no_alert_stable():
    """
    Escenario A: Red estable con 800 contactos (CV muy bajo).
    """
    ids = KadIDSEngine()
    ids.cycle_count = 11 # Pasamos el filtro de arranque frío
    
    # 15 muestras estables (800 +- 5)
    for i in range(15):
        ids.history.append({"contacts": 800 + (i % 5)})
        
    alerts, cv = ids._detect_churn()
    
    assert len(alerts) == 0
    assert cv < 0.05

def test_churn_critical_attack():
    """
    Escenario B: Ataque de Churn detectado (CV > 0.50).
    """
    ids = KadIDSEngine()
    ids.cycle_count = 11
    
    # Oscilaciones violentas: 800 -> 100 -> 900 -> 50...
    contacts_attack = [800, 100, 900, 50, 850, 120, 950, 40, 800, 100, 900, 50, 850, 120, 950]
    for c in contacts_attack:
        ids.history.append({"contacts": c})
        
    alerts, cv = ids._detect_churn()
    
    churn_alerts = [a for a in alerts if a["type"] == "churn"]
    assert len(churn_alerts) > 0
    assert churn_alerts[0]["severity"] == "critical"
    assert cv > 0.50

def test_churn_violent_oscillation_warning():
    """
    Escenario C: Oscilación violenta (CV bajo pero rango amplio).
    """
    ids = KadIDSEngine()
    ids.cycle_count = 11
    
    # Mayoría estable pero un par de caídas fuertes que disparan el rango
    # Mean ~ 733, Max-Min = 400. 400/733 = 0.54 (Rango > 0.40)
    contacts = [800, 800, 800, 400, 800, 800, 800, 800, 800, 800, 800, 800, 800, 800, 800]
    for c in contacts:
        ids.history.append({"contacts": c})
        
    alerts, cv = ids._detect_churn()
    
    assert len(alerts) > 0
    assert alerts[0]["severity"] == "warning"
    assert "Oscilación violenta" in alerts[0]["title_es"]

def test_churn_cold_start_filter():
    """
    Escenario D: Ignorar alertas durante los primeros 5 minutos.
    """
    ids = KadIDSEngine()
    ids.cycle_count = 5 # Estamos en el arranque frío
    
    # Datos inestables
    for i in range(15):
        ids.history.append({"contacts": 100 if i % 2 == 0 else 800})
        
    alerts, cv = ids._detect_churn()
    
    # No debe haber alertas a pesar de la inestabilidad
    assert len(alerts) == 0
    assert cv == 0.0
