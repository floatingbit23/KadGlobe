# AGENTS.md - KadGlobe Automation Guide 🌍

This document provides the necessary technical context for AI agents to autonomously and safely install, configure, and operate the **KadGlobe** ecosystem.

## 1. Project Goal

**KadGlobe** is an advanced 3D visualization tool for the Kademlia network in eMule/aMule. It combines binary analysis of the local routing table with real-time telemetry extracted from the eMule WebUI to geolocate nodes and map the logical topology (XOR distance).

## 2. Environment and Capabilities
- **Languages**: Python 3.x (Backend), Vanilla JavaScript (Frontend with Three.js).
- **External Services**: eMule/aMule Web Interface (Administrator password must be enabled).
- **Operating System**: Compatible with Windows and Linux via native scripts (`.bat` / `.sh`).
- **Geolocation**: Uses IP2Location `.BIN` files (LITE-DB5).

## 3. Architecture and Data Flow
The project uses a **scraping and JSON persistence** architecture:
1.  **Backend (Python)**: The `server.py` and `server_aMule.py` scripts fetch data from eMule and write static files into the `jsons/` folder.
2.  **Frontend (Web)**: A static application in `frontend/` uses `fetch` to consume those JSON files and render the interactive globe.
3.  **Persistence**:
    - `nodes.dat`: Binary source for the Kad network (routing table).
    - `jsons/*.json`: Telemetry (traffic, nodes, pings) for the frontend.

## 4. Provisioning and Setup
To initialize the environment, an agent must follow this flow:

### A. Python Dependencies
Install critical packages: `requests`, `beautifulsoup4`, `IP2Location`, `scapy`, `ping3`, `python-dotenv`, `pytest`.
```bash
python -m pip install -r requirements.txt
```

### B. Environment Configuration (`.env`)
Copy the corresponding example and configure absolute paths:
- **Windows**: `copy .env.windows.example .env`
- **Linux**: `cp .env.linux.example .env`

**Critical Keys**:
- `ADMIN_PASS`: Password for the eMule Web Interface.
- `EMULE_NODES_DAT_PATH`: Path to the `nodes.dat` file.
- `WEBUI_PORT`: Port for the eMule WebUI (default: `4711`).
- `IP2LOCATION_DB_PATH`: Path to `data/IP2LOCATION-LITE-DB5.BIN`.

### C. Geolocation Database
Requires `IP2LOCATION-LITE-DB5.BIN` in the `data/` folder. The `setup.bat` and `setup.sh` scripts include a wizard to download it using an IP2Location token.

## 5. Operational Procedures
To run the full system, use the orchestrators:

- **Windows**: Run `Script.bat` (Launches the backend and opens the frontend).
- **Linux**: Run `./launcher.sh` (**NEVER** as root/sudo to avoid conflicts with aMule/X11).

### A. Automated Testing
To ensure system stability, run the categorized test suites:

```bash
# 1. Core Logic & Parsers
python -m pytest tests/test_kad_logic.py     # XOR distance and bucket math
python -m pytest tests/test_nodes_parser.py  # Binary nodes.dat parsing
python -m pytest tests/test_geolocator.py    # IP to Geo mapping

# 2. IDS Security Engine
python -m pytest tests/test_ids_eclipse.py   # Sybil/Eclipse detection
python -m pytest tests/test_ids_poisoning.py # Bucket poisoning detection
python -m pytest tests/test_ids_dos.py       # Lookup DoS monitor

# 3. Scrapers & Telemetry
python -m pytest tests/test_scrapers.py      # eMule WebUI scraping
python -m pytest tests/test_amule_scraper_coverage.py # aMule specific coverage
python -m pytest tests/test_pinger.py        # UDP probing & RTT measurement
python -m pytest tests/test_smoke_server.py  # Orchestrator connectivity

# 4. Coverage & CLI
python -m pytest tests/test_cli.py           # Command line interface
python -m pytest tests/test_coverage_boost.py # Regression & Edge cases
```

> [!IMPORTANT]
> **Ping Privileges on Linux**: To use the heat map on Linux, Python needs access to `RAW SOCKETS`:
> ```bash
> sudo setcap cap_net_raw+ep $(readlink -f $(which python3))
> ```

## 6. Critical File Mapping for Agents
| File/Directory | Function for the Agent |
| :--- | :--- |
| `server.py` | Main orchestrator (scraper + parser). |
| `backend/` | Scraping and IP geolocation logic. |
| `backend/ids_engine.py` | Intrusion Detection System (IDS) core. |
| `backend/kad_utils.py` | Core Kademlia math (XOR/Buckets). |
| `tests/` | Unit testing suite (Logic + IDS Security). |
| `frontend/app.js` | Visualization logic (Three.js / Globe.gl). |
| `jsons/` | Storage for dynamic telemetry (Modify here to update the UI). |
| `data/` | Repository for binary databases (IP2Location). |

## 7. Constraints and Security
- Do not expose the `.env` file in commits.
- The frontend is static; it does not require an independent Node.js server. It can be served using `python -m http.server`.
- Respect UTF-8 encoding when scraping the WebUI to avoid special character parsing errors.
