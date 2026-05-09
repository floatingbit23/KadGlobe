import pytest
import statistics
from backend.ids_engine import KadIDSEngine

def test_sniffing_triage_detection():
    """
    Escenario A: Detectar un pico de nodos en una subred /24 (Z-Score).
    """
    ids = KadIDSEngine()
    ids.cycle_count = 10 # Bypass warm-up
    
    # 1. Creamos un historial estable (5 ciclos con 1-2 nodos por subred)
    for _ in range(5):
        past_stats = {"overhead": 1000}
        past_subnets = {"192.168.1": 2, "10.0.0": 1, "8.8.8": 1}
        ids._update_history(past_stats, {0: 10}) # Bucket_counts irrelevante aquí
        # Forzamos la inyección de subredes en el historial (simulando analyze)
        ids.history[-1]["subnet_counts"] = past_subnets

    # 2. Ciclo actual: Pico masivo en una subred (15 nodos)
    udp_nodes = []
    for i in range(15):
        udp_nodes.append({
            "ip": f"172.16.0.{i}",
            "lat": 40.4167,
            "lng": -3.7033,
            "rtt": 50 + i # RTT variable para no disparar Deep Scan aún
        })
    
    alerts = ids._detect_sniffing(udp_nodes)
    
    # Debe haber al menos una alerta de triage
    triage_alerts = [a for a in alerts if a["type"] == "sniffing_triage"]
    assert len(triage_alerts) > 0
    assert triage_alerts[0]["severity"] == "warning"
    assert "172.16.0" in triage_alerts[0]["indicator"]["subnet"]

def test_sniffing_farm_critical_detection():
    """
    Escenario B: Detectar una granja profesional (Coordenadas idénticas + RTT estable).
    """
    ids = KadIDSEngine()
    ids.cycle_count = 10 # Forzamos Deep Scan (Warm-up superado)
    
    # 1. Historial estable
    for _ in range(5):
        ids.history.append({"subnet_counts": {"1.1.1": 1}})

    # 2. Cluster de 6 nodos en la misma ubicación con RTT casi idéntico
    udp_nodes = []
    for i in range(6):
        udp_nodes.append({
            "ip": f"200.200.200.{i}",
            "lat": 48.8566,
            "lng": 2.3522,
            "rtt": 40 # RTT fijo = σ = 0
        })
    
    alerts = ids._detect_sniffing(udp_nodes)
    
    # Debe haber una alerta de granja crítica (>5 nodos + σ < 5ms)
    farm_alerts = [a for a in alerts if a["type"] == "sniffing_farm"]
    assert len(farm_alerts) > 0
    assert farm_alerts[0]["severity"] == "critical"
    assert farm_alerts[0]["indicator"]["count"] == 6
    assert farm_alerts[0]["indicator"]["rtt_std"] < 5

def test_sniffing_performance_impact():
    """
    Verificar que el análisis no sea excesivamente lento con muchos nodos.
    """
    import time
    ids = KadIDSEngine()
    ids.cycle_count = 10 # Bypass warm-up
    
    # 1000 nodos simulados
    big_nodes = []
    for i in range(1000):
        big_nodes.append({
            "ip": f"192.168.{i//254}.{i%254}",
            "lat": 40.0 + (i/1000),
            "lng": -3.0 - (i/1000),
            "rtt": 50
        })
        
    start = time.time()
    ids._detect_sniffing(big_nodes)
    duration = (time.time() - start) * 1000
    
    # El triaje + clustering para 1000 nodos debería ser < 50ms
    assert duration < 100
