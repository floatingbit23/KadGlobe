import json
import os
from datetime import datetime

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

        # En la Fase 0 solo preparamos la estructura
        
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
            "stats": { # Placeholders para métricas calculadas en fases siguientes
                "chi_squared_p_value": 1.0,
                "contacts_cv": 0.0,
                "overhead_rate": 0.0
            }
        }
        
        # Guardamos las alertas
        self._save_alerts(alerts_data)

        return alerts_data
