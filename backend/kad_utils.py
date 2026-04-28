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
    Calcula el K-Bucket (0-127) para una distancia dada.
    Corresponde a la posición del bit más significativo del XOR.
    """
    distance = get_kad_distance(id1_hex, id2_hex)
    if distance is None or distance == 0:
        return 0
    
    # En Python, bit_length() devuelve la posición del bit más alto (1-based)
    # El bucket 0 es distancia 1 (bit_length 1), el 127 es bit_length 128.
    return distance.bit_length() - 1
