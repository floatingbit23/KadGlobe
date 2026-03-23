
# Kadglobe 🌍 (English)

## 1. General Overview

**KadGlobe** is an advanced 3D visualization tool for the [Kademlia](https://en.wikipedia.org/wiki/Kademlia) network in [eMule](https://en.wikipedia.org/wiki/EMule). It serves as a visual "command post," connecting to the eMule WebUI to extract live statistics and analyzing local configuration files (`key_index.dat` and `nodes.dat`) to project your Kademlia neighborhood onto an interactive 3D globe. It aims to provide transparency on how decentralized routing works and the real-time health of your connections.

![alt text](images/presentationv2.png)

### 2. Technologies and Implementation
The project is built with a robust Python backend and a premium web-based frontend:

*   **Backend (Python)**:
    *   **Advanced Scraper**: Logs into the eMule WebUI to capture telemetry (traffic, searches, UDP status), and saves the data in a JSON file.

    ![alt text](images/json1.png)

    *   **Identity Extraction**: Reads the 128-bit Kad ID directly from `key_index.dat`.

    *   **Geolocation**: Processes `nodes.dat` and uses IP2Location databases to place each contact on the map, and saves the data in a JSON file.

    ![alt text](images/json2.png)

    *   **ICMP Pinger**: Performs multi-threaded ping sweeps (via OS ICMP) to measure real-world node latency (RTT), and saves the data in a JSON file.

    ![alt text](images/json3.png)

*   **Frontend (Web)**:
    *   **3D Rendering**: Built on **Globe.gl** and **Three.js** for a smooth planet visualization.
    *   **Glassmorphism UI**: Modern design featuring crystal and blur effects.
    *   **Analytics**: Uses **Chart.js** to display the K-Buckets distribution.

### 3. Components and Features

*   **Heat Map**: When active, the system performs real-time pings. Nodes are color-coded: Green (<150ms), Yellow (<500ms), or Red (>500ms), showing which parts of the world offer the best connectivity.

![alt text](images/heatmap.png)

*   **Nodes by Country**: A sidebar that classifies and sorts your contacts by geographic location.

![alt text](images/ranking.png)

*   **K-Buckets Distribution**: A histogram showing how many contacts you have in each routing "bucket" (XOR distance 0-128).

![alt text](images/kbuckets.png)


*   **Top 10 XOR Neighborhood**: Clicking a node calculates its 10 mathematically closest neighbors and traces golden connection arcs.

As an example, for a random node in London:
![alt text](images/node_info.png)
![alt text](images/xor_arcs.png)

*   **ID Status (Kad Status)**: Displays your status in the Kad network, using specific Kademlia terminology.

![alt text](images/status_opened.png)
![alt text](images/status_firewalled.png)
![alt text](images/status_disconnected.png)

### 4. Requirements and Setup
To use KadGlobe, you must ensure the following requirements are met:

1.  **eMule WebUI**: The "Web Interface" must be enabled in eMule's options, and an administrator password must be set.

![alt text](images/webInterface.png)

2.  **Dependencies**: Install the required Python modules:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Environment Variables**: Configure the `backend/.env` file with your local paths:
    *   `ADMIN_PASS`: Your eMule WebUI password.
    *   `EMULE_NODES_DAT_PATH`: Full path to your `nodes.dat` file.
    *   `EMULE_KEY_INDEX_PATH`: Path to your `key_index.dat` file.
    *   `IP2LOCATION_DB_PATH`: Path to the IP2Location `.BIN` database file.

![alt text](images/files.png)
![alt text](images/database.png)

-----

# KadGlobe 🌍 (Spanish)

**KadGlobe** es una herramienta de visualización avanzada en 3D para la red [Kademlia](https://es.wikipedia.org/wiki/Kademlia) en [eMule](https://es.wikipedia.org/wiki/EMule). Permite monitorizar en tiempo real la salud de la red, la distribución geográfica de los nodos y la topología lógica (distancia XOR) de tu tabla de enrutamiento.

![alt text](images/presentationv2.png)

### 1. Descripción General
KadGlobe actúa como un "puesto de mando" visual para eMule. Se conecta a la WebUI de eMule para extraer estadísticas en vivo y analiza archivos de configuración locales (`key_index.dat` y `nodes.dat`) para proyectar tu vecindario Kademlia sobre un globo terráqueo interactivo. Su objetivo es ofrecer transparencia sobre cómo funciona el enrutamiento descentralizado y cuál es el estado real de tus conexiones.

### 2. Tecnologías y Arquitectura
El proyecto se divide en un backend de orquestación y un frontend de visualización premium:

*   **Backend (Python)**:
    *   **Scraper Avanzado**: Inicia sesión en la WebUI de eMule para capturar telemetría (tráfico, búsquedas, estado UDP), y guarda los datos en un archivo JSON.
    
    ![alt text](images/json1.png)

    *   **Extracción de Identidad**: Lee directamente el Kad ID de 128 bits desde `key_index.dat`.
    *   **Geolocalización**: Procesa `nodes.dat` y utiliza una base de dato IP2Location para situar cada nodo de la red en el mapa, y guarda los datos en un archivo JSON.

    ![alt text](images/json2.png)
    
    *   **ICMP Pinger**: Realiza _ping sweeps_ (pasando por el SO) para medir la latencia real (RTT, _Round-Trip Time_) de los nodos, y guarda los datos en un archivo JSON.

    ![alt text](images/json3.png)
    

*   **Frontend (Web)**:
    *   **Visualización 3D**: Basado en **Globe.gl** y **Three.js** para un renderizado fluido del planeta.
    *   **Interfaz Glassmorphism**: Diseño moderno con efectos de cristal y desenfoque.
    *   **Gráficos**: Utiliza **Chart.js** para representar la distribución de K-Buckets.

### 3. Componentes y Funcionalidades

*   **Mapa Térmico (Heat Map)**: Al activarlo, el sistema realiza pings en tiempo real. Los nodos se colorean: Verde (<150ms), Amarillo (<500ms), Rojo (>500ms) o Blanco (sin respuesta), permitiendo ver qué nodos tienen mejor conectividad contigo a nivel global y en tiempo real.

![alt text](images/heatmap_es.png)

*   **Nodos por País**: Un panel lateral que clasifica y ordena los nodos por ubicación geográfica.

![alt text](images/ranking.png)

*   **Distribución K-Buckets**: Un histograma que muestra cuántos "contactos" (nodos) tienes en cada "cubo" de enrutamiento (distancia XOR 0-128). Es normal ver más nodos en los buckets lejanos (122-128) y muy pocos en los cercanos (<=121).

![alt text](images/kbuckets.png)

*   **Top 10 Vecindario XOR**: Al hacer clic en un nodo, se muestra una ventana con su IP, su ubicación y  su Kad ID. También se se calculan sus 10 vecinos más cercanos criptográficamente (distancia XOR) y se trazan arcos dorados de conexión.

Por ejemplo, para el nodo de Londres:
![alt text](images/node_info.png)
![alt text](images/xor_arcs.png)

*   **Estado de la ID (Kad Status)**: Diferencia entre estado "Abierto (Open)" y "Tras cortafuegos (Firewalled)" usando terminología específica de Kademlia.

![alt text](images/status_opened.png)
![alt text](images/status_firewalled.png)
![alt text](images/status_disconnected.png)

### 4. Requisitos y Configuración
Para que KadGlobe funcione correctamente, debes configurar los siguientes puntos:

1.  **eMule WebUI**: Debes tener activada la "Interfaz Web" en las opciones de eMule (Opciones -> Opciones Adicionales o Interfaz Web según versión) y establecer una contraseña de administrador.

![alt text](images/webInterface.png)

2.  **Dependencias**: Instala los módulos de Python necesarios:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Variables de Entorno**: Configura el archivo `backend/.env` con tus rutas locales:
    *   `ADMIN_PASS`: La contraseña que pusiste en la WebUI de eMule.
    *   `EMULE_NODES_DAT_PATH`: Ruta completa a tu archivo `nodes.dat` (ej: `C:\eMule\config\nodes.dat`).
    *   `EMULE_KEY_INDEX_PATH`: Ruta a tu archivo `key_index.dat`.
    *   `IP2LOCATION_DB_PATH`: Ruta a la base de datos `.BIN` de IP2Location para la geolocalización.

![alt text](images/files.png)
![alt text](images/database.png)

---

# Automation

[Script.bat](https://github.com/floatingbit23/KadGlobe/blob/main/Script.bat) is the project's all-in-one launcher. Its function is to automate three tasks in a single step:

1. Launch eMule: Starts the file-sharing program executable.
2. Start the Server: Launches the KadGlobe engine ([server.py](https://github.com/floatingbit23/KadGlobe/blob/main/server.py)) in the background and in a minimized window.
3. Open the Web UI: Automatically opens your default browser at the 3D map interface.

In short: it allows you to start monitoring your Kad network with a single click, without having to open each component manually.

--------
