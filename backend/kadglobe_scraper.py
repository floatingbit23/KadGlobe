"""
Este módulo actúa como un web scraper para la interfaz web por defecto de eMule.
Su objetivo principal es acceder al estado general de la red Kad.
"""

import requests
import re
import urllib.parse
import os
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Cargo las variables de nuestro archivo .env al os.environ para poder utilizarlas
load_dotenv()
 
class EMuleWebScraper:

    # Constructor de la clase
    def __init__(self, host="127.0.0.1", port=4711, password=""): # Inicializo el scraper con los valores por defecto
        self.host = host # Dirección IP de la máquina con eMule
        self.port = port # Puerto de la interfaz web de eMule
        self.password = password # Contraseña de la interfaz web de eMule
        self.base_url = f"http://{host}:{port}" # URL base de la interfaz web de eMule
        self.session_id = None # ID de sesión
        self.session = requests.Session() # Sesión de requests

    # Método para iniciar sesión en la interfaz web de eMule
    def login(self):
        """
        Me autentico en la interfaz web de eMule para obtener el Session ID.
        """

        print(f"\n[*] Iniciando sesión en la WebUI de eMule en {self.base_url}...")

        try:
            # En eMule.tmpl, el formulario de inicio de sesión envía 'p' (password) y 'w=password' 
            payload = {
                "w": "password",
                "p": self.password
            }

            # Envío la solicitud POST a la URL base de la interfaz web de eMule
            response = self.session.post(self.base_url + "/", data=payload, timeout=5)
            
            # eMule habitualmente responde con una etiqueta meta refresh que contiene el identificador de sesión:
            # <meta http-equiv="refresh" content="0;URL=/?ses=12345678">
            match = re.search(r'\?ses=([A-Za-z0-9_]+)', response.text)

            # Si he encontrado el Session ID, lo guardo y muestro un mensaje de éxito
            if match:
                self.session_id = match.group(1)
                print(f"[+] He iniciado sesión correctamente. El Session ID es: {self.session_id}")
                return True
            else:
                print("[!] He fallado al intentar iniciar sesión. No he encontrado el Session ID en la respuesta. Por favor, comprueba que la contraseña sea correcta o el estado de la WebUI.")
                return False
                
        except requests.exceptions.RequestException as e: # Si ha ocurrido un error de conexión durante el login
            print(f"[!] Ha ocurrido un error de conexión durante el login: {e}")
            return False

    # Método para extraer las estadísticas de Kad
    def fetch_kad_stats(self):

        """
        Navego hacia la página de Kad y extraigo el estado actual de la conexión Kad
        y sus estadísticas generales de uso.
        """

        if not self.session_id: # Si no tengo una sesión válida, no puedo proceder a extraer las estadísticas
            print("[!] No puedo proceder a extraer las estadísticas sin tener una sesión válida.")
            return None
            
        target_url = f"{self.base_url}/?ses={self.session_id}&w=kad" # URL de la página de Kad
        
        try: # Intento acceder a la página de Kad

            response = self.session.get(target_url, timeout=5) 
            soup = BeautifulSoup(response.text, 'html.parser') # Parseo el HTML de la página de Kad
            
            # El archivo eMule.tmpl utiliza la estructura <font face="Tahoma" style="font-size:9pt;"><b>[KADSTATUS]<br></b></font>
            # Puedo localizar el contexto de "KADSTATUS" examinando de forma iterativa las etiquetas td
            tds = soup.find_all('td')
            
            kad_status = "Desconocido"
            contacts = "0"
            current_searches = "0"
            
            for index, td in enumerate(tds): # Recorro todas las etiquetas td
                text = td.get_text(strip=True) # Obtengo el texto de la etiqueta td
                
                # En la WebUI estándar, el estado de Kad suele mostrarse posicionado junto a una etiqueta genérica STATUS
                if "STATUS" in text.upper():

                    # El estado real se suele encontrar guardado en la siguiente o la segunda siguiente etiqueta td
                    if index + 1 < len(tds):
                        possible_status = tds[index+1].get_text(strip=True) # Obtengo el texto de la siguiente etiqueta td

                        if possible_status: # Si he encontrado el estado de Kad, lo guardo
                            kad_status = possible_status
                            
                # Extraigo el número de contactos y búsquedas activas de la tabla de estadísticas
                if "CONTACTS" in text.upper() and "CURRENT SEARCHES" in text.upper():
                    if index + 1 < len(tds):
                        # Uso un separador para poder dividir los valores que vienen dentro de la misma celda separados por <br>
                        values_text = tds[index+1].get_text(separator='|', strip=True)
                        vals = [v.strip() for v in values_text.split('|')]
                        if len(vals) >= 1: contacts = vals[0]
                        if len(vals) >= 2: current_searches = vals[1]
            
            # Devuelvo un diccionario con la información estructurada que he extraído
            return {
                "status": kad_status,
                "contacts": contacts,
                "current_searches": current_searches,
                "raw_html": response.text
            }

        except requests.exceptions.RequestException as e:
            print(f"[!] He sufrido un problema de conexión al extraer información de la página Kad: {e}")
            return None

if __name__ == "__main__":

    # Realizo una pequeña prueba local a la WebUI usando la contraseña proveída a través del entorno
    print("\n--- Scraper de WebUI KadGlobe para eMule ---")
    
    admin_pass = os.getenv("ADMIN_PASS", "") # Obtengo la contraseña de la interfaz web de eMule
    ip_address = os.getenv("IP_ADDRESS", "") # Obtengo la dirección IP de la máquina con eMule

    if not admin_pass: # Si no tengo una contraseña válida, no puedo proceder a extraer las estadísticas
        print("[!] Advertencia: He detectado que ADMIN_PASS no está declarada ni en tu entorno ni en tu archivo .env.")
        
    scraper = EMuleWebScraper(host=ip_address, port=4711, password=admin_pass) # Inicializo el scraper con los valores por defecto

    if scraper.login(): # Si he iniciado sesión correctamente

        stats = scraper.fetch_kad_stats() # Extraigo las estadísticas de Kad

        if stats: # Si he extraído las estadísticas de Kad
            print("\n[+] He extraído las estadísticas de Kad exitosamente.")
            print(f"    - Estado: {stats['status']}")
            print(f"    - Contactos: {stats['contacts']}")
            print(f"    - Búsquedas actuales: {stats['current_searches']}")
            

            # Preparo los datos filtrados para guardarlos en un archivo JSON
            json_data = {
                "contacts": stats["contacts"],
                "current_searches": stats["current_searches"],
                "status": stats["status"]
            }
            
            # Guardo la información en kad_stats.json en la subcarpeta jsons/
            try:
                # Nos aseguramos de que el directorio exista (por si acaso se borra)
                output_path = "../jsons/kad_stats.json"
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f: # Abro el archivo kad_stats.json en modo escritura (write)
                    json.dump(json_data, f, indent=4, ensure_ascii=False) # Escribo los datos en el archivo JSON con una indentación de 4 espacios y sin caracteres especiales

                print(f"[+] He guardado los datos en '{output_path}'.")

            except Exception as e: # Si ha ocurrido un error al intentar guardar el archivo JSON
                print(f"[!] Error al intentar guardar el archivo JSON: {e}")
