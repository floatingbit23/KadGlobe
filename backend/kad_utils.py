"""
Módulo de utilidades matemáticas y lógicas para la red Kademlia.
Extraído para facilitar el testing unitario.
"""

def get_kad_distance(id1_hex, id2_hex):
    """Calcula la distancia XOR entre dos IDs en formato hexadecimal."""
    try:
        if not id1_hex or not id2_hex:
            return None
        return int(id1_hex, 16) ^ int(id2_hex, 16)
    except (ValueError, TypeError):
        return None


def get_kad_bucket(id1_hex, id2_hex):
    """
    Calcula el K-Bucket (0-127) para una distancia dada. Corresponde a la posición del bit más significativo del XOR.
    """
    distance = get_kad_distance(id1_hex, id2_hex)
    if distance is None or distance == 0:
        return 0
    
    # En Python, bit_length() devuelve la posición del bit más alto (1-based)
    # El bucket 0 es distancia 1 (bit_length 1), el 127 es bit_length 128.
    return distance.bit_length() - 1


def chi_squared_buckets(observed, expected): 
    """
    Test de Bondad de Ajuste Chi-cuadrado (χ²).
    
    Compara la distribución de nodos en los 128 buckets de Kademlia 
    frente a la distribución teórica esperada. 
    
    Un valor χ² inusualmente alto indica que un atacante está concentrando 
    IDs en zonas específicas del espacio de claves (Ataque Eclipse).

    Args:
        observed: Número de nodos en cada bucket.
        expected: Número esperado de nodos en cada bucket.
    Ambos serán diccionarios con la siguiente estructura: { <Índice del Bucket (0-127)>: <Cantidad de Nodos (0-n)> }
    
    Returns:
        float: Estadístico Chi-cuadrado.
    """

    chi_sq = 0.0 # chi_sq es la variable que almacena el estadístico Chi-cuadrado
    
    # Se itera sobre los 128 buckets
    for i in range(128):

        obs = observed.get(i, 0) # ¿Cuántos nodos VEO en este bucket?
        exp = expected.get(i, 0) # ¿Cuántos nodos DEBERÍA ver en este bucket?

        if exp > 0: # Solo se calcula si hay nodos esperados
            # Fórmula: (O-E)² / E
            chi_sq += ((obs - exp) ** 2) / exp

    return chi_sq


def z_score(value, mean, stddev):

    """
    Cálculo de Z-Score para Detección de Anomalías.
    
    Determina a cuántas desviaciones estándar (stddev) se encuentra un valor (value) de la media (mean).
    Valores con Z > 3.0 suelen considerarse anomalías estadísticas (outliers),
    útil para detectar picos repentinos de tráfico o envenenamiento de buckets (poisoning).
    """

    # Si la desviación estándar es 0, no se puede calcular el Z-score
    if stddev == 0:
        return 0.0

    # Fórmula Z-Score: (Valor observado - Media) / Desviación Estándar
    z = (value - mean) / stddev

    return z
