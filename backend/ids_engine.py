import json
import os
from datetime import datetime
from . import kad_utils

class KadIDSEngine:
    """
    Motor Central del IDS (Intrusion Detection System) para la red Kademlia.
    Procesa telemetría en tiempo real para identificar anomalías estadísticas consistentes con ataques Sybil, Eclipse, DoS y Poisoning.
    """

    # Constructor que inicializa el motor IDS con las rutas de los archivos JSON
    def __init__(self, history_path="jsons/ids_history.json", alerts_path="jsons/ids_alerts.json"):
        """
        Inicializa el motor IDS.

        Args:
            history_path (str): Ruta al archivo JSON del historial.
            alerts_path (str): Ruta al archivo JSON de alertas.
        """

        # Telemetría
        self.history_path = history_path
       
       # Alertas
        self.alerts_path = alerts_path

        # Carga el historial de telemetría desde el archivo JSON
        self.history = self._load_history()
        
        # Parámetros de Ventana y Cooldown
        self.max_history_samples = 60  # Mantiene 30 min de datos (muestreo cada 30s)
        self.cooldown_cycles = 0       # Contador para evitar cambios bruscos en la UI
        self.last_severity = "ok"      # Estado de la última ejecución

    def _load_history(self):
        """
        Carga el historial persistente desde el disco para análisis de tendencias.

        Returns:
            list: Lista de registros históricos.
        """

        # Verifica si el archivo JSON existe
        if os.path.exists(self.history_path):
            try:
                # Intenta abrir y cargar el archivo JSON
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return [] # Retorna lista vacía si el archivo está corrupto o no existe

        return []


    def _save_history(self):
        """Guarda el historial acumulado en formato JSON."""

        try:
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)

            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=4)

        except IOError as e:
            print(f"Error guardando historial IDS: {e}")


    def _save_alerts(self, alerts_data):
        """
        Escritura Atómica de Alertas.
        
        Utiliza un archivo temporal y una operación de renombramiento para asegurar
        que el frontend (fetch) nunca lea un archivo JSON incompleto o corrupto.

        Args:
            alerts_data (dict): Datos de alertas a persistir.
        """

        try:
            os.makedirs(os.path.dirname(self.alerts_path), exist_ok=True)
            temp_path = self.alerts_path + ".tmp" # Archivo temporal para evitar corrupción

            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(alerts_data, f, indent=4)
            
            # Reemplazo seguro del archivo final
            if os.path.exists(self.alerts_path):
                os.remove(self.alerts_path)

            os.rename(temp_path, self.alerts_path)

        except IOError as e:
            print(f"Error crítico guardando alertas IDS: {e}")


    def _parse_overhead(self, overhead_str):
        """
        Normalizador de Tráfico.
        
        Convierte representaciones textuales de eMule (ej: '14.24 k', '1.2 M')
        en enteros (bytes) para permitir operaciones matemáticas en el motor.

        Args:
            overhead_str (str): Cadena de texto con el tráfico (ej. "150 k").

        Returns:
            int: Valor convertido a bytes.
        """

        # Si la cadena está vacía o no es una cadena, retorna 0
        if not overhead_str or not isinstance(overhead_str, str):
            return 0

        try:
            # Divide la cadena en partes separadas por espacios
            parts = overhead_str.lower().strip().split()
            
            # Si la cadena está vacía, retorna 0
            if not parts:
                return 0

            # Convierte la primera parte a float
            value = float(parts[0])

            if len(parts) > 1:

                unit = parts[1]

                if unit == 'k': # Kilobytes
                    value *= 1000
                elif unit == 'm': # Megabytes
                    value *= 1000000

            # Convierte el valor a entero y lo retorna
            return int(value)

        except (ValueError, IndexError):
            return 0


    def _update_history(self, stats):
        """
        Gestiona la serie temporal de datos con una ventana deslizante.

        Args:
            stats (dict): Estadísticas actuales del cliente.
        """

        entry = {
            "timestamp": datetime.now().isoformat(), # Marca temporal del registro
            "contacts": stats.get("contacts", 0), # Número de contactos
            "overhead": self._parse_overhead(stats.get("kad_overhead_session_pkts", "0")), # Overhead en bytes
            "active_searches": stats.get("active_searches", 0) # Número de búsquedas activas
        }
        self.history.append(entry)
        
        # Mantiene el historial bajo el límite definido (60 muestras)
        if len(self.history) > self.max_history_samples:
            self.history = self.history[-self.max_history_samples:]
        
        self._save_history()


    def _detect_eclipse(self, stats, nodes):

        """
        Detector de Ataques Sybil/Eclipse.
        
        Analiza la distribución de buckets y la proximidad de IDs para identificar
        intentos de aislamiento del nodo o inundación de identidades falsas.

        Args:
            stats (dict): Estadísticas del cliente (debe contener 'local_id').
            nodes (list): Lista de nodos geolocalizados.

        Returns:
            tuple: (list de alertas, float p_value_placeholder)
        """

        # KadID local
        local_id = stats.get("local_id")

        if not local_id or not nodes:
            return [], 1.0

        total_nodes = len(nodes) # Total de nodos 

        observed = {} # Diccionario para contar nodos observados en cada bucket
        proximity_buckets = [117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127] # Zona de riesgo (ahora en índices altos)
        proximity_count = 0 # Contador de nodos en buckets cercanos

        subnet_groups = {} # Diccionario para agrupar nodos por subred
        
        # 1. Clasificación de nodos por bucket y subred
        for node in nodes:

            node_id = node.get("id")
            node_ip = node.get("ip", "")
            
            if not node_id:
                continue
            
            # Calcula el bucket al que pertenece el nodo
            bucket = kad_utils.get_kad_bucket(local_id, node_id)

            # Cuenta cuántos nodos hay en cada bucket
            observed[bucket] = observed.get(bucket, 0) + 1
            
            # Conteo de proximidad a la zona de riesgo
            if bucket in proximity_buckets:
                proximity_count += 1
                
            # Agrupación por subred /24 en buckets cercanos (B117-B127)
            if bucket >= 117 and node_ip:

                """
                La subred /24 es la "huella dactilar" de una ubicación física o un servidor específico. 
                Si vemos una concentración de nodos ahí, es casi seguro que se trata de un ataque desde una granja de servidores o una infraestructura controlada.
                """

                # Por ejemplo: "200.74.56.12" se convierte en "200.74.56"
                subnet = ".".join(node_ip.split(".")[:3])
                
                # Si el bucket no existe, se crea
                if bucket not in subnet_groups:
                    subnet_groups[bucket] = {}

                # Cuenta cuántos nodos hay en cada subred
                subnet_groups[bucket][subnet] = subnet_groups[bucket].get(subnet, 0) + 1

        # 2. Cálculo de distribución esperada P(bucket_i) = 1/2^(i+1)
        expected = {}

        """
        Probabilidad de que un nodo caiga en cada bucket:
        B0 (lejano) = 0.5 (50% de los nodos estarán en el bucket B0)
        B1 (medio) = 0.25 (25% de los nodos estarán en el bucket B1)
        B2 (medio-lejano) = 0.125 (12.5% de los nodos estarán en el bucket B2)
        B3 (medio-lejano) = 0.0625 (6.25% de los nodos estarán en el bucket B3)
        ...
        ...
        B127 (cercano) ~ 0 (0% de los nodos estarán en el bucket B127)
        """

        # Recorre los 128 buckets y calcula la probabilidad de que cada uno tenga un nodo
        for i in range(128):
            prob = 1.0 / (2**(i+1)) # Probabilidad teórica de que un nodo caiga en el bucket i
            expected[i] = total_nodes * prob # Número esperado de nodos en el bucket i

        # 3. Test Chi-cuadrado

        chi_sq = kad_utils.chi_squared_buckets(observed, expected)
        
        alerts = []
        
        """
        Como tenemos 128 buckets, los grados de libertad (GL) son 127.
        Un $p < 0.01$ significa que hay menos de un 1% de probabilidad de que la diferencia que estamos viendo sea por pura suerte o azar.

        Umbral de Chi-cuadrado para 127 GL -> p < 0.01 es ~168.9
        - Cualquier valor > 168.9 es sospechoso.
        - Nota: Usamos un umbral conservador (250.0) ya que KadGlobe es muy sensible a los cambios naturales en la red. 
            Sigue siendo extremadamente sensible para detectar un ataque real, pero nos da un colchón de seguridad mucho mayor contra los falsos positivos.
        """

        if chi_sq > 250.0:

            alerts.append({
                "type": "eclipse",
                "severity": "info",
                "title_es": "Distribución anómala de buckets",
                "title_en": "Anomalous bucket distribution",
                "detail_es": f"Test Chi-cuadrado: {chi_sq:.2f}. Los IDs no siguen una distribución aleatoria.",
                "detail_en": f"Chi-squared test: {chi_sq:.2f}. IDs do not follow a random distribution.",
                "indicator": {"chi_sq": chi_sq},
                "recommendation_es": "Monitorea la tabla de rutas; un atacante podría estar preparando un ataque de aislamiento (Eclipse).",
                "recommendation_en": "Monitor the routing table; an attacker might be preparing an isolation attack (Eclipse)."
            })

        # 4. Alerta de Proximidad Crítica

        if proximity_count > 5:

            alerts.append({
                "type": "eclipse",
                "severity": "critical",
                "title_es": "Ataque Eclipse Detectado",
                "title_en": "Eclipse Attack Detected",
                "detail_es": f"Se han detectado {proximity_count} nodos en buckets de proximidad crítica (B117-B127).",
                "detail_en": f"Detected {proximity_count} nodes in critical proximity buckets (B117-B127).",
                "indicator": {"proximity_count": proximity_count},
                "recommendation_es": "¡Peligro! Tu nodo está rodeado. Considera reiniciar la red Kad.",
                "recommendation_en": "Danger! Your node is surrounded. Consider restarting the Kad network."
            })

        elif proximity_count > 3:

            alerts.append({
                "type": "eclipse",
                "severity": "warning",
                "title_es": "Concentración sospechosa de IDs",
                "title_en": "Suspicious ID concentration",
                "detail_es": f"{proximity_count} nodos detectados inusualmente cerca de tu ID.",
                "detail_en": f"{proximity_count} nodes detected unusually close to your ID.",
                "indicator": {"proximity_count": proximity_count},
            })


        # 5. Detección de Sybil (Concentración por Subred /24)

        for bucket, subnets in subnet_groups.items():
            for subnet, count in subnets.items():
                if count > 3:
                    alerts.append({
                        "type": "sybil",
                        "severity": "warning",
                        "title_es": "Nodos Sybil detectados",
                        "title_en": "Sybil nodes detected",
                        "detail_es": f"Concentración de {count} nodos de la misma subred {subnet}.x en el bucket {bucket}.",
                        "detail_en": f"Concentration of {count} nodes from same {subnet}.x subnet in bucket {bucket}.",
                        "indicator": {"subnet": subnet, "bucket": bucket, "count": count},
                        "recommendation_es": "Posible ataque Sybil. Considera purgar la tabla de rutas y reconectarte.",
                        "recommendation_en": "Possible Sybil attack. Consider purging the routing table and reconnecting."
                    })

        # Retornamos p-value simplificado (0.001 si chi_cuadrado (chi_sq) es muy alto)
        p_val = 0.001 if chi_sq > 168 else 1.0

        return alerts, p_val


    # Función principal
    def analyze(self, stats, nodes, udp_nodes):

        """
        Punto de entrada principal para el análisis periódico.
        
        Calcula alertas y gestiona la severidad global aplicando una lógica de 
        'hysteresis' para evitar falsos negativos intermitentes en la interfaz.

        Args:
            stats (dict): Estadísticas del cliente eMule
            nodes (list): Lista de nodos geolocalizados
            udp_nodes (list): Lista de nodos UDP responsive

        Returns:
            dict: Diccionario con las alertas y estadísticas actualizadas
        """

        # Actualiza el historial con las estadísticas actuales
        self._update_history(stats)
        
        alerts = []
        
        # --- Fase 1: Detector Sybil/Eclipse ---

        # Realizamos el análisis de Sybil/Eclipse
        eclipse_alerts, chi_p = self._detect_eclipse(stats, nodes)  # chi_p es el p-value simplificado


        alerts.extend(eclipse_alerts) # Agregamos las alertas de Sybil/Eclipse
        
        # Lógica de Severidad Global con Cooldown de 3 ciclos (90 segundos)
        current_max_severity = "ok"

        # Obtenemos las severidades de las alertas generadas
        severities = [alert["severity"] for alert in alerts]

        # Determinamos la severidad global
        if "critical" in severities:
            current_max_severity = "critical"
        elif "warning" in severities:
            current_max_severity = "warning"
        elif "info" in severities:
            current_max_severity = "info"

        # Mecanismo de persistencia de alerta (cooldown de 3 ciclos)

        # Si la amenaza desaparece, mantenemos el estado de alerta ('warning') un tiempo prudencial
        if current_max_severity == "ok" and self.last_severity != "ok":

            if self.cooldown_cycles < 3:
                current_max_severity = "warning" # Degradamos suavemente
                self.cooldown_cycles += 1
            else:
                self.cooldown_cycles = 0

        # Si hay amenaza real, reiniciamos el contador de cooldown
        elif current_max_severity != "ok":
            self.cooldown_cycles = 0 

        self.last_severity = current_max_severity

        # Empaquetado para el frontend (consumido por app.js)
        alerts_data = {
            "timestamp": datetime.now().isoformat(),
            "global_severity": current_max_severity,
            "alerts": alerts,
            "stats": {
                "chi_squared_p_value": chi_p,
                "contacts_cv": 0.0,
                "overhead_rate": 0.0
            }
        }
        
        # Guardamos las alertas
        self._save_alerts(alerts_data)

        return alerts_data
