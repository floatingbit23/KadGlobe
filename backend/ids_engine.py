import json
import os
from datetime import datetime
import statistics
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

        # Estado para detección de sniffing
        self.cycle_count = 0
        self.deep_scan_interval = 10   # Ejecutar clustering pesado cada 10 ciclos (5 min)

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

        Ejemplo: "150 k" (kilobytes) -> 150000 (bytes)

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


    def _update_history(self, stats, bucket_counts=None):
        """
        Gestiona la serie temporal de datos con una ventana deslizante.

        Args:
            stats (dict): Estadísticas actuales del cliente.
            bucket_counts (dict, optional): Distribución actual de nodos por bucket.
        """

        entry = {
            "timestamp": datetime.now().isoformat(), # Marca temporal del registro
            "contacts": stats.get("contacts", 0), # Número de contactos
            "overhead": self._parse_overhead(stats.get("kad_overhead_session_pkts", "0")), # Overhead (en bytes), es decir, tráfico de control de la red Kad
            "active_searches": stats.get("active_searches", 0), # Número de búsquedas activas
            "bucket_counts": bucket_counts or {} # Distribución de buckets (para detección de Poisoning)
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
            tuple: (list de alertas, float p_value_placeholder, dict bucket_counts)
        """

        # KadID local
        local_id = stats.get("local_id")

        if not local_id or not nodes:
            return [], 1.0, {}

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

        return alerts, p_val, observed


    def _detect_poisoning(self, stats, bucket_counts):

        """
        Detector de Routing Table Poisoning.
        
        Identifica buckets con una población inusualmente alta comparándolos con el resto 
        de la tabla actual (Local) y con su propio historial (Temporal).
        
        Args:
            stats (dict): Estadísticas actuales -> Estructura: {'local_id': '...','contacts': 100...}.
            bucket_counts (dict): Conteo de nodos por bucket -> Estructura: {bucket_index: node_count}.
            
        Returns:
            list: Lista de alertas de Poisoning encontradas.
        """
        
        alerts = []

        if not bucket_counts:
            return []

        # 1. Análisis Local
        # Compara el número de nodos en cada bucket contra la media y desviación del conjunto actual
        
        counts = list(bucket_counts.values())

        # Si hay al menos dos buckets
        if len(counts) > 1:

            # Calculamos la media y la desviación estándar de los nodos en los buckets
            local_mean = statistics.mean(counts)
            local_std = statistics.stdev(counts) if len(counts) > 1 else 0
            
            # Recorremos los buckets
            for bucket_idx, count in bucket_counts.items():

                # Filtro de población mínima en el bucket
                if count < 5: 
                    continue
                    
                # Z-score local
                z_local = kad_utils.z_score(count, local_mean, local_std)

                # 2. Análisis Temporal
                # Compara el número de nodos en este bucket contra su propio historial

                historical_counts = []

                for entry in self.history:

                    # Notar que las claves en JSON son strings
                    b_hist = entry.get("bucket_counts", {})

                    # Obtenemos el conteo del bucket histórico
                    historical_counts.append(b_hist.get(str(bucket_idx), b_hist.get(bucket_idx, 0)))
                
                z_temporal = 0

                # Si hay al menos 8 muestras históricas para calcular la desviación
                if len(historical_counts) > 8: 
                    
                    # Media y desviación estándar de la historia del bucket
                    temp_mean = statistics.mean(historical_counts)

                    # Usamos un floor de 0.5 para evitar el bloqueo por estabilidad perfecta
                    temp_std = max(statistics.stdev(historical_counts), 0.5) if len(historical_counts) > 1 else 0.5
                    
                    # Z-score temporal
                    z_temporal = kad_utils.z_score(count, temp_mean, temp_std)
                
                # 3. Evaluación de Severidad

                # Tomamos el máximo Z-score entre local y temporal
                max_z = max(z_local, z_temporal)
                
                # Evaluamos si hay anomalía
                if max_z > 2.0:
                    # Definimos la severidad
                    severity = "critical" if max_z > 4.0 else "warning"
                    
                    # Añadimos la alerta
                    alerts.append({
                        "type": "poisoning",
                        "severity": severity,
                        "title_es": "Envenenamiento de Bucket detectado" if severity == "critical" else "Población anómala en bucket",
                        "title_en": "Bucket Poisoning detected" if severity == "critical" else "Anomalous bucket population",
                        "detail_es": f"Bucket {bucket_idx} tiene {count} nodos (Z-Score: {max_z:.2f}).",
                        "detail_en": f"Bucket {bucket_idx} has {count} nodes (Z-Score: {max_z:.2f}).",
                        "indicator": {"bucket": bucket_idx, "count": count, "z_score": max_z},
                        "recommendation_es": "Alerta de envenenamiento masivo. El tráfico de búsqueda hacia estos IDs podría estar siendo interceptado.",
                    })
        
        return alerts


    def _detect_sniffing(self, udp_nodes):

        """
        Detector de Granjas de Sniffing.
        
        Arquitectura Híbrida:
        1. Triage (Se ejecuta cada 1 ciclo): Cálculo de Z-Score sobre subredes /24 para detectar picos repentinos de nodos.
        2. Deep Scan (Se ejecuta cada 10 ciclos): Clustering geoespacial (si está disponible) y de RTT para confirmar granjas.

        (1 ciclo = 30 segundos)
        
        Args:
            udp_nodes (list): Nodos frescos con datos de RTT y geolocalización.
            
        Returns:
            list: Alertas de sniffing detectadas.
        """

        alerts = []
        
        if not udp_nodes:
            return alerts

        # Incrementamos contador de ciclos
        self.cycle_count += 1
        
        # 1. TRIAJE (Análisis por Subred /24)

        current_subnets = {}

        # Agregamos los nodos a su respectiva subred
        for node in udp_nodes:

            # Dividimos la IP por puntos
            ip_parts = node['ip'].split('.')

            if len(ip_parts) == 4:
                s24 = ".".join(ip_parts[:3]) # ej: 91.189.160.x -> 91.189.160
                current_subnets[s24] = current_subnets.get(s24, 0) + 1 # ej: {"91.189.160": 100, "8.8.8.8": 50, ...}

        # Análisis de Z-Score histórico por subred
        suspicious_subnets = []

        # Historial de al menos 5 ciclos
        if len(self.history) >= 5:
            # Consolidar estadísticas históricas de subredes
            all_past_counts = []

            # Recorremos el historial (excluyendo el último registro que es el actual)
            for h in self.history[:-1]:
                sc = h.get("subnet_counts", {})
                all_past_counts.extend(sc.values())
            
            # Si hay datos históricos
            if all_past_counts:
                # Calculamos media (mean) y desviación estándar (std) de la población histórica (population)
                mean_pop = statistics.mean(all_past_counts)
                std_pop = statistics.stdev(all_past_counts) if len(all_past_counts) > 1 else 1
                
                # Comparamos cada subred con la media histórica
                for s24, count in current_subnets.items():

                    # Calculamos el Z-Score de la población de esta subred frente a la media global
                    z = (count - mean_pop) / max(1, std_pop)

                    # Umbral de Triage: 3 desviaciones estándar
                    # (es decir, el 99.7% de los nodos deberian estar dentro de z <= 3 stddevs)
                    if z > 3.0: 
                        # Guardamos la subred sospechosa
                        suspicious_subnets.append(s24)
                        
                        # Alerta preliminar (Ola 1: el "Sniffing Triage")
                        alerts.append({
                            "type": "sniffing_triage",
                            "severity": "warning",
                            "title_es": "Actividad sospechosa en subred",
                            "title_en": "Suspicious subnet activity",
                            "detail_es": f"Pico de nodos en subred {s24}.x (Z-Score: {z:.1f}).",
                            "detail_en": f"Node spike in subnet {s24}.x (Z-Score: {z:.1f}).",
                            "indicator": {"subnet": s24, "count": count, "z_score": z}
                        })

        """
        Si el triaje ya nos dio suficientes sospechosos, nos saltamos el deep scan (ahorro de cómputo).
        O si no hemos llegado al intervalo de deep scan (ej: es el ciclo 1, 2, etc.)
        """    

        # 2. DEEP SCAN (Clustering Pesado)

        # Se ejecuta cada 10 ciclos O si el Sniffing Triage ha encontrado algo muy sospechoso
        if self.cycle_count % self.deep_scan_interval == 0 or suspicious_subnets:

            # Agrupamos nodos por Coordenadas (Heurística de Datacenter/Granja)
            geo_clusters = {}

            for node in udp_nodes:

                # Redondeamos coordenadas para capturar nodos en el mismo edificio/rack
                # 3 decimales = ~110 metros de precisión
                coords = (round(node.get('lat', 0), 3), round(node.get('lng', 0), 3))

                # Si no existe la clave con esas coordenadas, creamos una lista vacía
                if coords not in geo_clusters:
                    geo_clusters[coords] = []

                geo_clusters[coords].append(node)


            # Iteramos sobre los clústeres encontrados
            for coords, cluster_nodes in geo_clusters.items():

                # Una granja suele tener al menos 3 nodos coordinados
                if len(cluster_nodes) < 3:
                    continue
                
                # Analizamos consistencia de RTT en el cluster
                rtts = [n.get('rtt', 0) for n in cluster_nodes if n.get('rtt') is not None]

                """
                RRT (Round Trip Time) es la métrica que mide el tiempo que tarda un paquete en ir y volver a un servidor.
                En un ataque de sniffing, todos los nodos estarían en la misma red, por lo que
                el RTT de todos los nodos sería muy similar.
                """

                # Nos aseguramos de tener al menos 3 mediciones válidas
                if len(rtts) >= 3:
                    rtt_std = statistics.stdev(rtts)
                    rtt_avg = statistics.mean(rtts)
                    
                    # Heurística definitiva: Coordenadas idénticas + RTT extremadamente estable:

                    # Si la desviación es menor a 5ms, es muy probable que sea una granja/cluster de nodos automatizado
                    if rtt_std < 5:

                        # Graduación de Severidad
                        # Si hay muchos nodos (>5) o están en una subred de Triage (sospechosa) -> Severidad nivel 'Critical' (Datacenter/Professional)
                        is_critical = len(cluster_nodes) > 5 or any(".".join(n['ip'].split('.')[:3]) in suspicious_subnets for n in cluster_nodes)
                        
                        # Asignamos el nivel de severidad
                        severity = "critical" if is_critical else "warning"
                        
                        # Agregamos la alerta a la lista
                        alerts.append({
                            "type": "sniffing_farm",
                            "severity": severity,
                            "title_es": "Granja de Sniffing Detectada" if is_critical else "Cluster de nodos sospechoso",
                            "title_en": "Sniffing Farm Detected" if is_critical else "Suspicious node cluster",
                            "detail_es": f"Detectados {len(cluster_nodes)} nodos coordinados en {coords} (RTT={int(rtt_avg)}ms, σ={rtt_std:.1f}).",
                            "detail_en": f"Detected {len(cluster_nodes)} coordinated nodes at {coords} (RTT={int(rtt_avg)}ms, σ={rtt_std:.1f}).",
                            "indicator": {"coords": coords, "count": len(cluster_nodes), "rtt_std": rtt_std},
                            "recommendation_es": "Posible monitorización masiva. Estos nodos podrían estar recolectando metadatos de tus búsquedas.",
                            "recommendation_en": "Possible mass monitoring. These nodes might be collecting metadata from your searches."
                        })
        
        return alerts


    def _detect_dos(self):

        """
        Detector de Lookup DoS e inundación de tráfico.
        Analiza la tasa de cambio del Overhead (tráfico de control de la red Kad) y la compara con la media histórica para detectar anomalías de volumen.
        
        Returns:
            list: Lista de alertas de DoS encontradas.
        """
        
        alerts = []
        
        if len(self.history) < 3:
            return []

        # 1. Cálculo de deltas (tasas de cambio)
        # Necesitamos calcular el salto de overhead entre muestras consecutivas
        rates = []

        for i in range(1, len(self.history)):
            
            prev = self.history[i-1].get("overhead", 0)
            curr = self.history[i].get("overhead", 0)
            
            delta = curr - prev
            
            # Si el delta es negativo, asumimos reinicio de eMule y usamos 0
            rates.append(max(delta, 0))

        if not rates:
            return []

        tasa_actual = rates[-1]
        active_searches = self.history[-1].get("active_searches", 0)

        # 2. Análisis de Tendencia (Media de las últimas 20 muestras)
        # Tomamos las últimas 20 tasas (sin contar la actual) para la referencia
        ref_rates = rates[-21:-1] if len(rates) > 1 else []
        
        if len(ref_rates) >= 5: # Necesitamos un mínimo de datos para que la media sea fiable

            ref_mean = statistics.mean(ref_rates)
            
            # Suelo de 100 bytes para evitar alertas por ruidos mínimos en redes muy inactivas
            ref_mean = max(ref_mean, 100) 
            
            ratio = tasa_actual / ref_mean

            # Solo alertamos si NO hay búsquedas activas significativas que justifiquen el tráfico
            if active_searches < 3:

                if ratio > 10.0:
                    severity = "critical"
                elif ratio > 3.0:
                    severity = "warning"
                else:
                    severity = None

                if severity:
                    alerts.append({
                        "type": "dos",
                        "severity": severity,
                        "title_es": "Ataque DoS Detectado" if severity == "critical" else "Tráfico de control anómalo",
                        "title_en": "DoS Attack Detected" if severity == "critical" else "Anomalous control traffic",
                        "detail_es": f"El overhead está creciendo a una tasa de {tasa_actual} bytes ({ratio:.1f}x la media).",
                        "detail_en": f"Overhead is growing at a rate of {tasa_actual} bytes ({ratio:.1f}x mean).",
                        "indicator": {"rate": tasa_actual, "ratio": ratio, "searches": active_searches},
                        "recommendation_es": "Se ha detectado una inundación de peticiones Kad. El nodo podría estar bajo un ataque de denegación de servicio.",
                        "recommendation_en": "A flood of Kad requests has been detected. The node might be under a denial of service attack."
                    })

        # 3. Detector de Crecimiento Exponencial (Sostenido por 2 saltos consecutivos)
        # Si la tasa se dobla en cada ciclo: Muestra_N > 2*Muestra_N-1 > 4*Muestra_N-2
        if len(rates) >= 3 and active_searches < 3:

            m1 = rates[-3]
            m2 = rates[-2]
            m3 = rates[-1]

            # Solo analizamos si el tráfico es significativo (> 500 bytes de delta)
            if m1 > 500 and m2 / m1 > 2.0 and m3 / m2 > 2.0:

                # Si ya hay una alerta de DoS por ratio, no duplicamos, pero subimos severidad
                existing_dos = [a for a in alerts if a["type"] == "dos"]
                
                if not existing_dos:
                    alerts.append({
                        "type": "dos",
                        "severity": "critical",
                        "title_es": "Crecimiento Exponencial de Tráfico",
                        "title_en": "Exponential Traffic Growth",
                        "detail_es": "El tráfico Kad está escalando de forma exponencial sin búsquedas activas.",
                        "detail_en": "Kad traffic is scaling exponentially without active searches.",
                        "indicator": {"m1": m1, "m2": m2, "m3": m3},
                        "recommendation_es": "Alerta crítica: El volumen de paquetes Kad está explotando. Posible inundación masiva.",
                        "recommendation_en": "Critical alert: Kad packet volume is exploding. Possible massive flood."
                    })
                else:
                    # Si ya existe, nos aseguramos que sea critical
                    existing_dos[0]["severity"] = "critical"
                    existing_dos[0]["detail_es"] += " Detectado crecimiento exponencial."

        return alerts


    def _detect_churn(self):

        """
        Monitor de Churn (Inestabilidad).
        Analiza la estabilidad del nº de contactos Kad para detectar oscilaciones violentas o inestabilidad crónica.
        
        Returns:
            tuple: (list de alertas, float cv_actual)
        """

        alerts = []
        cv = 0.0 # Coeficiente de variación (CV)

        """
        El CV es la desviación estándar dividida por la media. 
        Esta métrica nos indica el grado de dispersión de los datos en relación a su valor promedio.
        Un CV de 0.50, por ejemplo, indica que la desviación estándar es el 50% de la media.
        En redes estables, el CV suele estar por debajo de 0.20 (20%).
        """

        # Filtro de Arranque Frío (Cold Start al conectarme a la red Kad): 
        # Ignoramos alertas en los primeros 5 minutos (10 ciclos)
        if self.cycle_count < 10:
            return alerts, cv

        # Necesitamos una ventana mínima (al menos 5 ciclos o 2.5 minutos) para que el análisis sea estadísticamente relevante
        if len(self.history) < 5:
            return alerts, cv

        # Ventana de Análisis: últimas 15 muestras (15 ciclos o ~7.5 minutos)
        window = self.history[-15:]

        # Obtenemos el número de contactos en cada ciclo
        contacts = [h.get("contacts", 0) for h in window]
        
        # Si no hay suficientes datos para el análisis, retornamos
        if not contacts or len(contacts) < 2:
            return alerts, cv

        # Cálculos estadísticos

        # Media
        mean_c = statistics.mean(contacts)

        # Si la media es 0, no hay contactos
        if mean_c <= 0:
            return alerts, cv

        # Desviación estándar
        std_c = statistics.stdev(contacts)

        # CV (desviación estándar / media)
        cv = std_c / mean_c
        
        # Rango de oscilación -> (max - min) / media
        c_min = min(contacts)
        c_max = max(contacts)
        oscillation_range = (c_max - c_min) / mean_c

        # 1. Alerta por Churn Crítico (CV > 0.50)
        if cv > 0.50:

            alerts.append({
                "type": "churn",
                "severity": "critical",
                "title_es": "Ataque de Churn detectado",
                "title_en": "Churn Attack detected",
                "detail_es": f"Inestabilidad extrema en los contactos (CV: {cv:.2f}).",
                "detail_en": f"Extreme contact instability (CV: {cv:.2f}).",
                "indicator": {"cv": cv, "mean": int(mean_c), "range": f"{c_min}-{c_max}"},
                "recommendation_es": "Red altamente inestable. Si persiste, podría ser un ataque de Churn dirigido.",
                "recommendation_en": "Highly unstable network. If it persists, it could be a targeted Churn attack."
            })

        # 2. Alerta por Inestabilidad o Oscilación Violenta
        elif cv > 0.30 or oscillation_range > 0.40:

            severity = "warning"

            alerts.append({
                "type": "churn",
                "severity": severity,
                "title_es": "Red Inestable (Churn)" if cv > 0.30 else "Oscilación violenta de contactos",
                "title_en": "Unstable Network (Churn)" if cv > 0.30 else "Violent contact oscillation",
                "detail_es": f"Variación significativa en el número de contactos (CV: {cv:.2f}, Rango: {oscillation_range:.2%}).",
                "detail_en": f"Significant contact variation (CV: {cv:.2f}, Range: {oscillation_range:.2%}).",
                "indicator": {"cv": cv, "range": f"{c_min}-{c_max}"},
                "recommendation_es": "Comprueba tu conexión o cortafuegos inmediatamente.",
                "recommendation_en": "Check your connection or firewall immediately."
            })

        return alerts, cv


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

        # Fase 1: Análisis de Sybil/Eclipse
        eclipse_alerts, chi_p, bucket_counts = self._detect_eclipse(stats, nodes)

        alerts = []

        # Fase 1: Alertas de Sybil/Eclipse
        alerts.extend(eclipse_alerts)

        # Fase 2: Alertas de Poisoning
        poisoning_alerts = self._detect_poisoning(stats, bucket_counts)
        alerts.extend(poisoning_alerts)

        # Fase 3: Monitor de Lookup DoS
        dos_alerts = self._detect_dos()
        alerts.extend(dos_alerts)

        # Fase 4: Detector de Sniffing Farms
        sniff_alerts = self._detect_sniffing(udp_nodes)
        alerts.extend(sniff_alerts)

        # Fase 5: Monitor de Churn (Inestabilidad)
        churn_alerts, current_cv = self._detect_churn()
        alerts.extend(churn_alerts)

        # Pre-procesamiento de subredes para el historial
        current_subnets = {}

        # Analizamos las UDP nodes
        for node in udp_nodes:

            # Obtenemos la IP del nodo UDP (ej. 'xx.xx.xx.xx') y la separamos por octetos
            ip_parts = node['ip'].split('.')

            # Si es una IP válida (tiene 4 octetos)
            if len(ip_parts) == 4:
                # Obtenemos la subred /24
                s24 = ".".join(ip_parts[:3])
                # Contamos los nodos por subred
                current_subnets[s24] = current_subnets.get(s24, 0) + 1

        # Actualizamos las estadísticas
        stats["subnet_counts"] = current_subnets

        # Actualiza el historial con las estadísticas actuales y la distribución de buckets
        self._update_history(stats, bucket_counts)
        
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
                "contacts_cv": current_cv,
                "overhead_rate": self.history[-1].get("overhead", 0) - self.history[-2].get("overhead", 0) if len(self.history) > 1 else 0.0
            }
        }
        
        # Guardamos las alertas
        self._save_alerts(alerts_data)

        return alerts_data
