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
3.  **Environment Variables**: Configure the `.env` file (you can copy `.env.windows.example` or `.env.linux.example` depending on your OS) with your local paths:
    *   `ADMIN_PASS`: Your eMule WebUI password.
    *   `EMULE_NODES_DAT_PATH`: Full path to your `nodes.dat` file.
    *   `EMULE_KEY_INDEX_PATH`: Path to your `key_index.dat` file.
    *   `IP2LOCATION_DB_PATH`: Path to the IP2Location `.BIN` database file.

![alt text](images/files.png)
![alt text](images/database.png)

### 5. _Disclaimer: Data Latency and Persistence_

_It is important to note that the node information visualized in KadGlobe is retrieved by binary parsing of the `nodes.dat` file, retrieved from the user's local storage._

_In the Kademlia protocol, the **active routing table** (the _buckets_) is managed directly in the system memory (RAM) of the eMule process to ensure maximum speed. eMule flushes this data to the hard disk (`nodes.dat`) only periodically or during a controlled shutdown to maintain persistence between sessions._

_Therefore, while the traffic statistics and UDP status are captured in real-time via the eMule's WebUI scraper, the geographic positions and XOR distances represent a "recent snapshot" of your Kad neighborhood rather than a millisecond-accurate live stream. This design choice was made to provide a non-invasive way to audit the network state without the stability risks associated with direct memory hooking or process injection._

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


> [!IMPORTANT]
> **Linux Network Permissions**: On Linux, to use the "Heat Map" (ICMP Ping), you must grant Python permissions to open _Raw Sockets_:
> ```bash
> sudo setcap cap_net_raw+ep $(readlink -f $(which python3))
> ```
