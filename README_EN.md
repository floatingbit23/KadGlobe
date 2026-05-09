# KadGlobe 🌍

[Español](README.md) | [English](README_EN.md)

## 1. General Overview

**KadGlobe** is an advanced 3D visualization tool for the [Kademlia](https://en.wikipedia.org/wiki/Kademlia) network in [eMule](https://en.wikipedia.org/wiki/EMule). It serves as a visual "command post," connecting to the eMule WebUI to extract live statistics and analyzing local configuration files (`key_index.dat` and `nodes.dat`) to project your Kademlia neighborhood onto an interactive 3D globe. It aims to provide transparency on how decentralized routing works and the real-time health of your connections.

![alt text](images/presentationv2.png)
![alt text](images/terminal.png)

### 2. Technologies and Implementation
The project is built with a robust Python backend and a premium web-based frontend:

*   **Backend (Python)**:

    *   **Advanced Scraper**: Logs into the eMule WebUI to capture telemetry (traffic, searches, UDP status), and saves the data in a JSON file.

    ![alt text](images/json1.png)

    *   **Dynamic Identity**: Automatically detects your public IP and extracts your authentic 128-bit KadID directly from local eMule UDP traffic.

    *   **Geolocation**: Processes `nodes.dat` and uses IP2Location databases to place each contact on the map.
    
    ![alt text](images/json2.png)
    
    *   **Intelligent Kad UDP Probe**: Implements a 4-phase discovery engine:

        1. **Seed**: Retrieves initial contacts from local eMule.

        2. **RTT Selection**: Measures latency (RTT) and selects the **4 fastest nodes**.

        3. **1-hop Crawl**: Requests neighbors from those leaders to expand the map with high-quality, live nodes (up to a maximum of 100 new nodes).

        4. **Sweep**: Final RTT measurement and self-node identification (Black Pillar).

    ![alt text](images/json3.png)

*   **Frontend (Web)**:

    *   **3D Rendering**: Built on **Globe.gl** and **Three.js** for smooth visualization.

    *   **Bilingual UI**: Full support for Spanish and English via a dynamic toggle (ES/EN).

    *   **Real-time Counter**: The "Active Nodes" button displays the exact number of live responders detected in the current cycle.
    
    *   **Analytics**: Uses **Chart.js** to display the K-Buckets distribution.

### 3. Components and Features

*   **Intelligent Heat Map**: When active, the system performs a recursive performance-based discovery. Nodes are color-coded based on their UDP latency: 
> Green 🟢 (<150ms),

> Yellow 🟡 (<500ms), 

> Red 🔴 (>500ms) 

> White ⚪ (no response). 

> Violet 🟣 (IDS Alert Target / Detected Threat). These nodes are also visually elevated with higher pillars.

> Our own node is highlighted with a black pillar ⬛ on the globe.

![alt text](images/heatmap.png)
![alt text](images/self_node.png)

*   **Nodes by Country**: A sidebar that classifies and sorts your contacts by geographic location.

![alt text](images/ranking.png)

*   **K-Buckets Distribution**: A histogram showing how many contacts (nodes) you have in each routing "bucket" (XOR distance $0-127$). It is expected to see more contacts in far buckets ($B127$, $B126$, etc.) and very few in near ones ($B0$ to $B10$).

![alt text](images/kbuckets.png)

> Note: Keep in mind that the probability of a node falling into $B127$ is 50%, into $B126$ is 25%, into $B125$ is 12.5%, etc. Therefore, you will virtually never see nodes in the nearest buckets (the probability is infinitesimal). The formula is: 
$$P(Bi) = \frac{1}{2^{128-i}}$$

*   **Top 10 XOR Neighborhood**: Clicking a node calculates its 10 mathematically closest neighbors and traces golden connection arcs.

As an example, for a random node in London:
![alt text](images/node_info.png)
![alt text](images/xor_arcs.png)

*   **ID Status (Kad Status)**: Displays your status in the Kad network, using specific Kademlia terminology.

![alt text](images/status_connected.png)
![alt text](images/status_firewalled.png)
![alt text](images/status_disconnected.png)

### 4. Intrusion Detection System (IDS)
KadGlobe includes a specialized IDS engine (`backend/ids_engine.py`) that monitors Kad network anomalies to protect your node against common DHT network attacks:

*   **Sybil/Eclipse Detection**: Analyzes the statistical distribution of buckets using the $\chi^2$ test. It alerts if an unusual number of nodes concentrate in specific buckets trying to surround your ID.

*   **Poisoning Detection**: Uses a _Z-Score_ analysis normalized by Kademlia's theoretical distribution ($1/2^{128-i}$). It filters out natural noise in common distant buckets ($B127$, $B126$...) and prioritizes detecting suspicious clusters in the "XOR neighborhood" ($B0-B10$), where attacks are most critical.

*   **Lookup DoS Monitor**: Monitors control traffic (_overhead_). It detects packet floods by analyzing traffic ratios and exponential growth curves, filtering legitimate spikes during your own searches.

> [!TIP]
> IDS alerts are classified as `INFO`, `WARNING`, and `CRITICAL`. Alerts are displayed in the UI panel.

Some examples:
![alt text](images/ids_safe.png)
![alt text](images/ids_warning.png)
![alt text](images/ids_critical.png)

### 5. Requirements and Setup
To use KadGlobe, you must ensure the following requirements are met:

1.  **eMule WebUI**: The "Web Interface" must be enabled in eMule's options, and an administrator password must be set.

![alt text](images/webInterface.png)

2.  **Dependencies**: Install the required Python modules:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Environment Variables**: Configure the `.env` file (you can copy from `.env.windows.example` or `.env.linux.example` depending on your system) to customize behavior:
    *   `ADMIN_PASS`: The password you set in the eMule WebUI.
    *   `KADGLOBE_HTTP_PORT`: (Optional) The port where you will view the map (default `8000`).
    *   `WEBUI_PORT`: (Optional) The eMule/aMule WebUI port (default `4711` for eMule, `4712` for aMule).
    *   `EMULE_KAD_UDP_PORT`: (Optional) Your Kademlia network UDP port (default `16005`).
    *   `IP2LOCATION_DB_PATH`: Path to the IP2Location `.BIN` database for geolocation.
    *   `EMULE_NODES_DAT_PATH`: (Optional) Path to your `nodes.dat`. If left empty, it will attempt auto-detection.
    *   `EMULE_KEY_INDEX_PATH`: (Optional) Path to `key_index.dat`. Only needed to force your exact KadID in the UI (pinger auto-detects it via UDP).


![alt text](images/files.png)
![alt text](images/database.png)

### 6. _Disclaimer: Data Latency and Persistence_

_KadGlobe retrieves node information from two complementary sources:_

- _**Base nodes (offline)**: Obtained by binary parsing of eMule's `nodes.dat` file. These contacts represent a "snapshot" of the routing table from eMule's last shutdown, so the geographic positions and XOR distances on the base map may not reflect the current state of the network in real time._

- _**"Fresh" nodes (live)**: For the Heat Map, KadGlobe sends a `KADEMLIA2_BOOTSTRAP_REQ` directly to the local eMule process to obtain **verified, active contacts** from its in-memory routing table. This guarantees that the probed nodes are actually connected to the Kad network at that moment._

_Traffic statistics and connection status are captured in real time via the eMule WebUI scraper. Heat Map latencies are measured using native `KADEMLIA2_PING/PONG` protocol packets (via UDP), providing a true application-level measurement — not just a network-level (ICMP) one._

_This architecture enables non-invasive Kademlia network health monitoring without requiring direct memory hooking or process injection._

---

# Automation

### 1. First Time Setup (Recommended)
The project includes a **setup script** that automates the installation of dependencies, ensures the folder structure is correct, and helps you download the IP2Location database.

**Windows**: Double-click [setup.bat](https://github.com/floatingbit23/KadGlobe/blob/main/setup.bat).  
**Linux**: Run `./setup.sh` in your terminal.

```bash
# Give execution permissions (only first time)
chmod +x setup.sh

# Run the setup wizard
./setup.sh
```

### 2. Launching KadGlobe
Once configured, you can launch all components in a single step:

**Windows**: Run [Script.bat](https://github.com/floatingbit23/KadGlobe/blob/main/Script.bat).  
**Linux**: Run [launcher.sh](https://github.com/floatingbit23/KadGlobe/blob/main/launcher.sh).


> [!CAUTION]
> **DO NOT run `launcher.sh` with `sudo`.**  
> Running as root will cause "Permission Denied" errors in `/run/user/0` and "Display not found" errors because GUI applications like aMule must run within your normal user session.
