// Referencias a los elementos del DOM (HTML)
const elStatus = document.getElementById('kadStatus');
const elContacts = document.getElementById('kadContacts');
const elContactsDiff = document.getElementById('kadContactsDiff');
const elSearches = document.getElementById('kadSearches');
const elMappedNodes = document.getElementById('kadMappedNodes');
const elCountryList = document.getElementById('countryList');
const elXorNeighborsPanel = document.getElementById('xorNeighborsPanel');
const elXorNeighborsList = document.getElementById('xorNeighborsList');

// Nuevas referencias para estadísticas avanzadas
const elIdRow = document.getElementById('kadIdRow');
const elId = document.getElementById('kadId');
const elOverheadRow = document.getElementById('kadOverheadRow');
const elOverhead = document.getElementById('kadOverhead');
const elFirewallRow = document.getElementById('kadFirewallRow');
const elFwUdp = document.getElementById('kadFwUdp');
const elFwTcp = document.getElementById('kadFwTcp');
const elSources = document.getElementById('kadSources');
const elSourcesRow = document.getElementById('kadSourcesRow');

/**
 * Generador de números aleatorios criptográficamente seguro (CSPRNG).
 * Reemplaza a Math.random() para cumplir con auditorías de seguridad (SonarQube).
 * @returns {number} Un número decimal entre 0 y 1.
 */
function secureRandom() {
    const array = new Uint32Array(1);
    globalThis.crypto.getRandomValues(array);
    return array[0] / (0xffffffff + 1);
}

// --- DICCIONARIO i18n ---
let currentLang = 'es';

const i18n = {
    es: {
        "net_status": "Estado de la Red Kad:",
        "loading": "Cargando...",
        "contacts": "Contactos Kad:",
        "mapped": "Nodos Geolocalizados:",
        "ranking_title": "Nodos por país",
        "xor_neighbors_title": "Top 10 Vecindario XOR",
        "heatmap_btn": "Nodos Activos",
        "heatmap_tool_title": "Salud de Red Kad (UDP)",
        "heatmap_tool_desc": `Mide la latencia real mediante ráfagas nativas Kademlia (UDP Ping). Colorea los nodos según su tiempo de respuesta:
🟢: < 150ms (Excelente)
🟡: < 500ms (Aceptable)
🔴: > 500ms (Lento)
⚪: Sin respuesta (Filtrado/Offline)`,
        "modal_title": "Información del Nodo",
        "modal_xor": "● Proyectando Vecindario Kad (XOR)",
        "modal_loc": "Ubicación:",
        "unknown": "Desconocido",
        "unknown_f": "Desconocida",
        "status_connected": "Conectado",
        "status_disconnected": "Desconectado",
        "status_firewalled": "Tras cortafuegos",
        "status_open": "Abierto (Open)",
        "id_status": "Estado de la ID:",
        "searches": "Búsquedas Activas:",
        "overhead": "Tráfico Kad (sesión):",
        "firewalled": "Tras cortafuegos (UDP/TCP):",
        "kad_sources": "Fuentes vía Kad:",
        "buckets_title": "Distribución K-Buckets",
        "self_node_label": "ESTE ERES TÚ (eMule)",
        "ids_title": "KadGlobe IDS",
        "ids_ok": "Sin amenazas",
        "ids_warning": "ADVERTENCIA",
        "ids_critical": "CRÍTICO",
        "ids_last_update": "Última actualización:",
        "ids_no_alerts": "No hay amenazas detectadas en este momento.",
        "ids_reco_title": "Recomendación:"
    },
    en: {
        "net_status": "Kademlia Network Status:",
        "loading": "Loading...",
        "contacts": "Kad Contacts:",
        "mapped": "Georeferenced Nodes:",
        "ranking_title": "Nodes by country",
        "xor_neighbors_title": "Top 10 XOR Neighborhood",
        "heatmap_btn": "Active Nodes",
        "heatmap_tool_title": "Kad Network Health (UDP)",
        "heatmap_tool_desc": `Measures real latency using native Kademlia bursts (UDP Ping). Colors nodes based on response time:
🟢: < 150ms (Excellent)
🟡: < 500ms (Acceptable)
🔴: > 500ms (Slow)
⚪: No response (Filtered/Offline)`,
        "modal_title": "Node Information",
        "modal_xor": "● Projecting Kad Neighborhood (XOR)",
        "modal_loc": "Location:",
        "unknown": "Unknown",
        "unknown_f": "Unknown",
        "status_connected": "Connected",
        "status_disconnected": "Disconnected",
        "status_firewalled": "Firewalled",
        "status_open": "Open",
        "id_status": "ID Status:",
        "searches": "Active Searches:",
        "overhead": "Kad Traffic (session):",
        "firewalled": "Firewalled (UDP/TCP):",
        "kad_sources": "Sources via Kad:",
        "buckets_title": "K-Buckets Distribution",
        "self_node_label": "THIS IS YOU (eMule)",
        "ids_title": "KadGlobe IDS",
        "ids_ok": "No threats",
        "ids_warning": "WARNING",
        "ids_critical": "CRITICAL",
        "ids_last_update": "Last update:",
        "ids_no_alerts": "No threats detected at this time.",
        "ids_reco_title": "Recommendation:"
    }
};

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (i18n[currentLang][key]) {
            el.textContent = i18n[currentLang][key];
        }
    });

    const btn = document.getElementById('langToggle');
    if (btn) btn.textContent = currentLang === 'es' ? 'EN' : 'ES';

    updateHeatmapButtonText();
}

let activeNodesCount = 0;
function updateHeatmapButtonText() {
    const btn = document.getElementById('heatMapToggle');
    if (btn) {
        const baseText = i18n[currentLang].heatmap_btn;
        btn.textContent = activeNodesCount > 0 ? `${baseText} (${activeNodesCount})` : baseText;
    }
}

const langToggle = document.getElementById('langToggle');
if (langToggle) {
    langToggle.addEventListener('click', () => {
        currentLang = currentLang === 'es' ? 'en' : 'es';
        applyTranslations();
        updateKadStats();
        updateKadNodes();
    });
}

// --- FASE 6: LÓGICA IDS ---

// Referencias DOM IDS (Globales)
let elIdsGlobalStatus, elIdsGlobalIcon, elIdsAlertList, elIdsUpdateTime;
let elIdsFloating, elIdsClose;

// Estado global de alertas para overlays
globalThis.activeIDSAlerts = [];

async function updateIDSAlerts() {
    try {
        const response = await fetch('/jsons/ids_alerts.json?t=' + Date.now());
        if (!response.ok) return;

        const data = await response.json();
        globalThis.activeIDSAlerts = data.alerts || [];

        renderIDSAlerts(data);
        updateIDSBadge(data.global_severity || 'ok');
        updateIDSOverlays();

        if (elIdsUpdateTime) elIdsUpdateTime.textContent = new Date().toLocaleTimeString();
    } catch (e) {
        console.warn('[!] Error obteniendo ids_alerts.json:', e);
    }
}

function renderIDSAlerts(data) {
    if (!elIdsAlertList) return;
    elIdsAlertList.innerHTML = '';

    const alerts = data.alerts || [];

    if (alerts.length === 0) {
        elIdsAlertList.innerHTML = `<li style="color:rgba(255,255,255,0.4); font-size:12px; text-align:center;">
            ${i18n[currentLang].ids_no_alerts}
        </li>`;
        return;
    }

    alerts.forEach(alert => {
        const li = document.createElement('li');
        li.className = 'ids-alert-item';

        let icon = '🛡️';
        if (alert.type === 'eclipse' || alert.type === 'sybil') icon = '⚠️';
        if (alert.type === 'dos') icon = '💀';
        if (alert.type === 'poisoning') icon = '🧪';
        if (alert.type === 'sniffing') icon = '👁️';
        if (alert.type === 'churn') icon = '🔄';

        const title = currentLang === 'es' ? alert.title_es : alert.title_en;
        const detail = currentLang === 'es' ? alert.detail_es : alert.detail_en;
        const reco = currentLang === 'es' ? alert.recommendation_es : alert.recommendation_en;

        li.innerHTML = `
            <div class="alert-title">
                <span>${icon} ${title}</span>
                <span class="ids-badge severity-${alert.severity}">${alert.severity.toUpperCase()}</span>
            </div>
            <div class="alert-detail">${detail}</div>
            <div class="alert-recommendation"><b>${i18n[currentLang].ids_reco_title}</b> ${reco}</div>
        `;
        elIdsAlertList.appendChild(li);
    });
}

function updateIDSBadge(severity) {
    if (!elIdsGlobalStatus) return;

    elIdsGlobalStatus.className = `ids-badge severity-${severity}`;
    elIdsGlobalStatus.textContent = severity === 'ok' ?
        i18n[currentLang].ids_ok :
        i18n[currentLang][`ids_${severity}`];

    if (severity === 'critical') elIdsGlobalIcon.textContent = '🚨';
    else if (severity === 'warning') elIdsGlobalIcon.textContent = '⚠️';
    else elIdsGlobalIcon.textContent = '🛡️';
}

function initIDS() {
    elIdsGlobalStatus = document.getElementById('idsGlobalStatus');
    elIdsGlobalIcon = document.getElementById('idsGlobalIcon');
    elIdsAlertList = document.getElementById('idsAlertList');
    elIdsUpdateTime = document.getElementById('idsUpdateTime');
    elIdsFloating = document.getElementById('idsFloatingPanel');
    elIdsClose = document.getElementById('closeIdsModal');
    const elIdsHeader = document.getElementById('idsHeaderToggle');

    if (elIdsHeader) {
        elIdsHeader.addEventListener('click', () => {
            elIdsFloating.classList.remove('modal-hidden');
        });
    }

    if (elIdsClose) {
        elIdsClose.addEventListener('click', () => {
            elIdsFloating.classList.add('modal-hidden');
        });
    }

    const elIdsFloatingHeader = document.getElementById('idsFloatingHeader');
    if (elIdsFloating && elIdsFloatingHeader) {
        makeDraggable(elIdsFloating, elIdsFloatingHeader);
    }

    setInterval(updateIDSAlerts, 15000);
    updateIDSAlerts();
}

const countriesToggle = document.getElementById('countriesToggle');
if (countriesToggle) {
    countriesToggle.addEventListener('click', () => {
        const panel = document.getElementById('countriesPanel');
        panel.classList.toggle('panel-collapsed');
    });
}

// --- LOGICA DE RENDER TÉRMICO ---
let heatMapMode = false;
let latestUdpLatencies = {};

function getPointColor(node) {
    if (node.is_self) return '#000000'; // Negro profundo para nosotros (tu cliente)

    // RESALTADO IDS: Si el nodo está implicado en una alerta crítica/warning
    const idsAlert = globalThis.activeIDSAlerts.find(a => a.target_ip === node.ip || a.target_id === node.id);
    if (idsAlert) {
        return '#9d00ff'; // VIOLETA IDS
    }

    if (!heatMapMode) {
        return '#00f2fe'; // Azul brillante estático (Clásico)
    }

    // MODO TÉRMICO (Semáforo UDP Kad RTT)
    const ms = latestUdpLatencies[node.ip];
    if (ms === undefined) {
        return 'rgba(255, 255, 255, 0.9)'; // Sin respuesta
    }

    if (ms < 150) return '#00ff00';      // Excelente
    if (ms < 500) return '#ffcc00';      // Aceptable
    return '#ff3333';                    // Lento
}

function getPointAltitude(d) {
    if (d.is_self) return 0.05; // El pilar más alto para nosotros

    // RESALTADO IDS: Los nodos sospechosos se elevan para ser visibles
    const idsAlert = globalThis.activeIDSAlerts.find(a => a.target_ip === d.ip || a.target_id === d.id);
    if (idsAlert) {
        return idsAlert.severity === 'critical' ? 0.08 : 0.05;
    }

    if (heatMapMode) {
        // En modo "Nodos Activos", destacamos los que tienen latencia medida o son frescos
        if (d.isFresh || latestUdpLatencies[d.ip] !== undefined) {
            return 0.03; // Pilar para nodos activos (reducido a la mitad)
        }
    }
    return d.size || 0.01; // Tamaño normal (base)
}

const heatMapToggle = document.getElementById('heatMapToggle');
if (heatMapToggle) {
    heatMapToggle.addEventListener('click', () => {
        heatMapMode = !heatMapMode;
        if (heatMapMode) {
            heatMapToggle.style.background = 'rgba(255, 204, 0, 0.4)';
            heatMapToggle.style.borderColor = '#ffcc00';
            heatMapToggle.style.color = '#ffcc00';
            heatMapToggle.style.boxShadow = '0 0 10px rgba(255, 204, 0, 0.5)';
        } else {
            heatMapToggle.style.background = '';
            heatMapToggle.style.borderColor = '';
            heatMapToggle.style.color = '';
            heatMapToggle.style.boxShadow = '';
        }

        if (renderGlobe !== undefined) {
            renderGlobe.pointColor(getPointColor);
            renderGlobe.pointAltitude(getPointAltitude); // Actualizamos también la altura
            if (heatMapMode) {
                renderGlobe.arcsData([]).ringsData([]);
            }
            renderGlobe.pointsData([...globalNodesArray]);
        }
    });
}
// ------------------------

// 1. Configuración de Globe.gl y Three.js
const renderGlobe = Globe()
    (document.getElementById('globeViz'))
    .globeImageUrl('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg') // Textura HD
    .bumpImageUrl('https://unpkg.com/three-globe/example/img/earth-topology.png')    // Relieve topográfico
    .backgroundImageUrl('https://unpkg.com/three-globe/example/img/night-sky.png')   // Fondo estelar

    // Configuración para los puntos y pilares de los Nodos Kad (Nodos Conocidos)
    // HE QUITADO pointsMerge(true) para que Globe.gl envíe los eventos de Click y el ratón reconozca los pilares individuales.
    .pointLat('lat')
    .pointLng('lng')
    .pointAltitude(getPointAltitude) // Evaluación dinámica del tamaño (crece en modo Activos)
    .pointRadius(0.2)                // Ancho del radio del pilar
    .pointColor(getPointColor)       // Color atado la evaluación dinámica en caliente


    // Tarjeta emergente (Tooltip) que aparece al pasar el ratón por los nodos
    .pointLabel(d => {
        let title = i18n[currentLang].unknown_f;
        if (d.is_self) {
            title = i18n[currentLang].self_node_label;
        } else if (d.city !== "-" && d.city !== "Unknown") {
            title = d.city;
        }

        let countryLabel = i18n[currentLang].unknown;
        if (d.country !== "-" && d.country !== "Unknown") {
            countryLabel = d.country;
        }

        return `
            <div style="background: rgba(10, 15, 30, 0.9); padding: 10px; border-radius: 8px; border: 1px solid #4facfe; color: white; font-family: Inter, sans-serif;">
                <b style="font-size: 14px;">${title}</b><br/>
                <i style="color: #ccc;">${countryLabel}</i><br/>
                <small style="color: #666; margin-top: 4px; display: block;">ID: ${d.id.substring(0, 8)}...</small>
            </div>
        `;
    })
    // Al hacer click en el punto geográfico, llamamos a la función para invocar el Modal
    .onPointClick(point => openNodeModal(point));

// Variables del Modal
const nodeModal = document.getElementById('nodeModal');
const modalIp = document.getElementById('modalIp');
const modalLocation = document.getElementById('modalLocation');
const modalId = document.getElementById('modalId');
const btnCloseModal = document.getElementById('closeModal');

// Función asíncrona y UI para abrir/cerrar el modal
function openNodeModal(node) {
    modalIp.textContent = node.ip || i18n[currentLang].unknown_f;
    const city = (node.city && node.city !== "-" && node.city !== "null") ? node.city : "?";
    const country = (node.country && node.country !== "-" && node.country !== "null") ? node.country : "?";
    modalLocation.textContent = `${city}, ${country}`;
    modalId.textContent = node.id || "Error";

    nodeModal.classList.remove('modal-hidden');

    // --- Motor Visual de Topología Kademlia (XOR) ---
    selectedNode = node;

    // 1. Pausar el ruido visual caótico temporalmente
    if (simulationInterval) clearInterval(simulationInterval);

    // 2. Calcular criptográficamente la distancia de Enrutamiento a cada nodo del planeta
    const neighbors = [];
    globalNodesArray.forEach(remoteNode => {
        if (remoteNode.id !== node.id) {
            neighbors.push({
                obj: remoteNode,
                dist: getKadDistance(node.id, remoteNode.id) // Distancia Hash (XOR 128 bit)
            });
        }
    });

    // 3. Ordenar BigInts de MENOR (Más cercano lógicamente) a MAYOR distancia
    neighbors.sort((a, b) => {
        if (a.dist < b.dist) return -1;
        if (a.dist > b.dist) return 1;
        return 0;
    });

    // Extraer los 15 Vecinos Lógicos Más Cercanos (independientemente del país en el que estén)
    const closest15 = neighbors.slice(0, 15);
    const closest10 = neighbors.slice(0, 10); // Para el Panel de Listado Kademlia

    // --- Panel XOR ---
    elXorNeighborsList.innerHTML = '';
    closest10.forEach((neighbor, index) => {
        const li = document.createElement('li');
        const city = neighbor.obj.city && neighbor.obj.city !== "-" ? neighbor.obj.city : "?";
        const country = neighbor.obj.country && neighbor.obj.country !== "-" ? neighbor.obj.country : "?";
        li.innerHTML = `<span>#${index + 1}</span> <span>${neighbor.obj.ip} (${city}, ${country})</span>`;
        elXorNeighborsList.appendChild(li);
    });

    elXorNeighborsPanel.classList.remove('modal-hidden');
    // -----------------

    // Dibujar tubos estáticos dorados
    const topologyArcs = closest15.map(neighbor => ({
        startLat: node.lat,
        startLng: node.lng,
        endLat: neighbor.obj.lat,
        endLng: neighbor.obj.lng,
        color: ['rgba(255, 204, 0, 1)', 'rgba(255, 204, 0, 0.1)'] // Gradiente Dorado extinguiéndose en el vecino
    }));

    renderGlobe
        .arcsData(topologyArcs)
        .arcColor('color')
        .arcDashLength(1) // Haz sólido (sin pulsos)
        .arcDashGap(0)
        .arcDashAnimateTime(0) // Flujo continuo congelado (Estático)
        .ringsData([]); // Destruir púlsares interactivos
}

document.getElementById('closeModal').addEventListener('click', () => {
    document.getElementById('nodeModal').classList.add('modal-hidden');
    elXorNeighborsPanel.classList.add('modal-hidden');
    selectedNode = null;

    // Al cerrar el modal borramos los arcos matemáticos estáticos
    renderGlobe.arcsData([]);
    // Y retomamos la simulación visual natural en background
    simulateKadActivity(globalNodesArray);
});

// Rotación automática suave del globo terráqueo como fondo inmersivo
// Evitamos llamar a controls() síncronamente antes de que el motor disponga el WebGL
setTimeout(() => {
    try {
        renderGlobe.controls().autoRotate = false;
        renderGlobe.controls().autoRotateSpeed = 0.5;
        // Ajustamos la cámara para empezar un poco más lejos y apreciar la rotación
        renderGlobe.pointOfView({ altitude: 2 }, 4000);
    } catch (e) {
        console.warn("Globe Controls Error:", e);
    }
}, 500);


// 2. Fetchers de Datos (La carga asíncrona de los archivos locales/JSON)

let previousContacts = null;

// A. Función que obtiene el estado general de Kad (Refactorizada para reducir complejidad)
async function updateKadStats() {
    try {
        const response = await fetch('/jsons/kad_stats.json?t=' + Date.now());
        if (!response.ok) {
            elStatus.textContent = `Error HTTP: ${response.status}`;
            return;
        }

        const data = await response.json();
        const statusFlags = updateStatusUI(data);

        updateHeatmapButton(statusFlags.isDisconnected, statusFlags.isFirewalled);
        updateContactsUI(data);
        updateExtendedStatsUI(data);

        if (data.local_id) {
            globalThis.localKadId = data.local_id;
        }
    } catch (e) {
        elStatus.textContent = `[JS Error] ${e.message}`;
        console.warn('[!] Error obteniendo kad_stats.json:', e);
    }
}


// Helpers para updateKadStats (Reducción de Complejidad Cognitiva)
function updateStatusUI(data) {
    let displayStatus = data.status || i18n[currentLang].unknown;
    elStatus.classList.remove('status-connected', 'status-disconnected', 'status-firewalled');

    let isDisconnected = false;
    let isFirewalled = false;

    if (data.status) {
        const statusLower = data.status.toLowerCase();
        if (statusLower.includes('disconnect') || statusLower.includes('desconectado')) {
            elStatus.classList.add('status-disconnected');
            displayStatus = i18n[currentLang].status_disconnected;
            isDisconnected = true;
        } else if (statusLower.includes('firewall') || statusLower.includes('cortafuego')) {
            elStatus.classList.add('status-firewalled');
            displayStatus = i18n[currentLang].status_firewalled;
            isFirewalled = true;
        } else if (statusLower.includes('connect') || statusLower.includes('conectado')) {
            elStatus.classList.add('status-connected');
            displayStatus = i18n[currentLang].status_connected;
        }
    }

    elStatus.textContent = displayStatus;
    return { isDisconnected, isFirewalled };
}

function updateHeatmapButton(isDisconnected, isFirewalled) {
    const btnHeatMap = document.getElementById('heatMapToggle');
    if (!btnHeatMap) return;

    if (isDisconnected) {
        disableHeatmapButton(btnHeatMap);
    } else {
        enableHeatmapButton(btnHeatMap, isFirewalled);
    }
}

function disableHeatmapButton(btn) {
    btn.disabled = true;
    btn.style.opacity = '0.3';
    btn.style.filter = 'grayscale(1)';
    btn.style.cursor = 'not-allowed';
    btn.title = currentLang === 'es' ? ' ❌ Función deshabilitada: Kad desconectado!' : ' ❌ Function disabled: Kad is not connected!';

    if (heatMapMode) {
        resetHeatmapUI(btn);
    }
}

function resetHeatmapUI(btn) {
    heatMapMode = false;
    btn.style.background = '';
    btn.style.borderColor = '';
    btn.style.color = '';
    btn.style.boxShadow = '';
    if (renderGlobe !== undefined) {
        renderGlobe.pointColor(getPointColor);
        renderGlobe.pointAltitude(getPointAltitude);
        renderGlobe.pointsData([...globalNodesArray]);
    }
}

function enableHeatmapButton(btn, isFirewalled) {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.filter = 'none';
    btn.style.cursor = 'pointer';
    if (isFirewalled) {
        btn.title = currentLang === 'es' ?
            '⚠️ ¡Atención! Estás Tras Cortafuegos (Firewalled). La visibilidad de red puede ser limitada.' :
            '⚠️ Warning! You are Firewalled. Network visibility might be limited.';
        btn.style.boxShadow = '0 0 10px rgba(255, 204, 0, 0.4)';
    } else {
        btn.title = '';
        btn.style.boxShadow = '';
    }
}

function updateContactsUI(data) {
    const currentContacts = Number.parseInt(data.contacts || '0', 10);
    elContacts.textContent = currentContacts;

    if (previousContacts !== null && elContactsDiff) {
        const diff = currentContacts - previousContacts;
        if (diff > 0) {
            elContactsDiff.textContent = `(+${diff})`;
            elContactsDiff.style.color = '#00e676';
        } else if (diff < 0) {
            elContactsDiff.textContent = `(${diff})`;
            elContactsDiff.style.color = '#ff4d4d';
        } else {
            elContactsDiff.textContent = '';
        }
    }
    previousContacts = currentContacts;
    elSearches.textContent = data.active_searches || '0';
}

function updateExtendedStatsUI(data) {
    if (data.kad_status) {
        const ksLower = data.kad_status.toLowerCase();
        let displayKadStatus = data.kad_status;

        if (ksLower.includes('firewall')) {
            displayKadStatus = i18n[currentLang].status_firewalled;
        } else if (ksLower.includes('open') || ksLower.includes('abierto')) {
            displayKadStatus = i18n[currentLang].status_open;
        } else if (ksLower.includes('disconnect') || ksLower.includes('desconectado')) {
            displayKadStatus = i18n[currentLang].status_disconnected;
        }

        elId.textContent = displayKadStatus;
        elIdRow.style.display = 'flex';
    }
    if (data.kad_overhead_session_pkts !== undefined) {
        elOverhead.textContent = data.kad_overhead_session_pkts;
        elOverheadRow.style.display = 'flex';
    }
    if (data.kad_firewalled_udp_pct !== undefined) {
        elFwUdp.textContent = data.kad_firewalled_udp_pct;
        elFwTcp.textContent = data.kad_firewalled_tcp_pct;
        elFirewallRow.style.display = 'flex';
    }
    if (data.kad_sources_found !== undefined) {
        elSources.textContent = data.kad_sources_found;
        elSourcesRow.style.display = 'flex';
    }
}

// Variables Globales de control Topológico
let globalNodesArray = [];
let selectedNode = null;
let simulationInterval = null;

// Función matemática base (XOR distance) del artículo Kademlia P2P (Restamos 128-bits usando BigInt nativo de ES6)
function getKadDistance(hex1, hex2) {
    // Si no son válidos, devolvemos distancia 0
    if (!hex1?.match(/^[0-9a-fA-F]+$/) || !hex2?.match(/^[0-9a-fA-F]+$/)) return BigInt(0);
    return BigInt('0x' + hex1) ^ BigInt('0x' + hex2); // ^ representa el operador XOR
}

// B. Función que obtiene todas las ubicaciones y recrea los nodos en el globo
async function updateKadNodes() {
    try {
        const response = await fetch('/jsons/kad_nodes_geospatial.json?t=' + Date.now());

        if (response.ok) {
            const newNodesArray = await response.json();

            let mergedNodes = [...newNodesArray];

            // Recoger latencias UDP asíncronas elaboradas por el backend (Kad UDP Probe)
            try {
                const latUdpRes = await fetch('/jsons/kad_udp_responsive_nodes.json?t=' + Date.now());
                if (latUdpRes.ok) {
                    const responsiveUdpArray = await latUdpRes.json();
                    latestUdpLatencies = {};
                    activeNodesCount = responsiveUdpArray.length;

                    responsiveUdpArray.forEach(rn => {
                        latestUdpLatencies[rn.ip] = rn.rtt;

                        const exists = mergedNodes.some(n => n.ip === rn.ip);
                        if (exists) {
                            // Si existe, nos aseguramos de que tenga las propiedades de 'rn' (como is_self)
                            const idx = mergedNodes.findIndex(n => n.ip === rn.ip);
                            mergedNodes[idx] = { ...mergedNodes[idx], ...rn };
                        } else {
                            // Si el nodo fresco NO está en la lista base (nodes.dat), lo inyectamos dinámicamente
                            mergedNodes.push({
                                ...rn,
                                size: 0.01, // Por defecto mismo tamaño que los base
                                isFresh: true
                            });
                        }
                    });

                    updateHeatmapButtonText();
                }
            } catch (e) {
                console.warn("UDP telemetry not available yet or error fetching:", e);
            }

            globalNodesArray = mergedNodes; // Volcamos al caché global para que actúe JS al hacer Click

            // Inyectamos todo el json de memoria plano al renderizador 3D como en la primera versión robusta
            renderGlobe.pointsData(mergedNodes);

            // Reflejamos los vivos en la UI
            elMappedNodes.textContent = mergedNodes.length;

            // ----------------------------------------------------------------------------------
            // A. Motor Map-Reduce de Top Países (Lista lateral en tiempo real)
            // ----------------------------------------------------------------------------------
            const countryData = {};
            mergedNodes.forEach(node => {
                const cname = (node.country && node.country !== "-" && node.country !== "Unknown") ? String(node.country) : i18n[currentLang].unknown;
                if (!countryData[cname]) {
                    countryData[cname] = { count: 0, code: (node.country_code ? String(node.country_code) : 'unknown') };
                }
                countryData[cname].count++;
            });

            // Convertir a Array y ordenar de mayor a menor (Ej. [ ["Spain", {count: 25, code: 'es'}], ... ])
            const sortedCountries = Object.entries(countryData).sort((a, b) => b[1].count - a[1].count);

            // Vaciamos visualmente la lista y la re-dibujamos
            elCountryList.innerHTML = '';
            sortedCountries.forEach(([countryName, data]) => {
                const li = document.createElement('li');
                li.className = 'country-item';

                // Petición visual por CDN del SVG de la bandera
                const flagHtml = (data.code !== 'unknown' && data.code !== '-')
                    ? `<img src="https://flagcdn.com/w20/${data.code}.png" alt="${data.code}" style="margin-right:8px; border-radius:2px;">`
                    : `<span style="display:inline-block; width:20px; margin-right:8px; text-align:center;">🌍</span>`;

                li.innerHTML = `
                    <div style="display:flex; align-items:center;">
                        ${flagHtml}
                        <span class="country-name">${countryName}</span>
                    </div>
                    <span class="country-count">${data.count}</span>
                `;
                elCountryList.appendChild(li);
            });
            // ----------------------------------------------------------------------------------

            // Simulador visual de la red (Omitido temporalmente si estamos estudiando estáticamente un nodo concreto)
            if (!selectedNode) {
                simulateKadActivity(mergedNodes);
            }

            // Actualizar el gráfico de K-Buckets si tenemos el ID local válido
            if (globalThis.localKadId && globalThis.localKadId !== "Unknown") {
                updateKBucketsChart(mergedNodes, globalThis.localKadId);
            }
        } else {
            elMappedNodes.textContent = `HTTP ${response.status}`;
        }
    } catch (e) {
        elMappedNodes.textContent = `[JS Fallo] ${e.message}`;
        console.warn('[!] Error obteniendo kad_nodes_geospatial.json:', e);
    }
}

// --- LÓGICA DE CHART.JS PARA K-BUCKETS ---
let bucketsChart = null;

function updateKBucketsChart(nodes, localId) {
    const ctx = document.getElementById('bucketsChart').getContext('2d');

    // Inicializamos contadores para los buckets (0 a 128)
    const bucketCounts = new Array(129).fill(0);

    nodes.forEach(node => {
        const dist = getKadDistance(localId, node.id);
        if (dist === 0n) return; // Somos nosotros o misma ID

        // El bucket es (127 - log2(dist)) para que B0 sea el más lejano
        const bucketIndex = 127 - (dist.toString(2).length - 1);
        if (bucketIndex >= 0 && bucketIndex <= 127) {
            bucketCounts[bucketIndex]++;
        }
    });

    // Filtramos para mostrar solo buckets que tengan algún nodo o un rango interesante (ej. últimos 32)
    // Pero para eMule, los buckets importantes suelen ser los altos (lejanos)
    // Mostraremos un histograma de los buckets 0 a 128, pero quizás agrupados o podados si están vacíos.
    // Para simplificar, mostramos todos los buckets que tengan al menos 1 nodo.

    const labels = [];
    const dataValues = [];
    let validNodesCount = 0;

    for (let i = 0; i <= 127; i++) {
        if (bucketCounts[i] > 0) {
            // Probabilidad invertida: B0 = 50%, B1 = 25%...
            const probPct = (1 / Math.pow(2, i + 1)) * 100;
            let probStr = "<0.01%";
            if (probPct >= 1) {
                probStr = `${Math.round(probPct)}%`;
            } else if (probPct >= 0.01) {
                probStr = `${probPct.toFixed(2)}%`;
            }

            // Usamos un array para que Chart.js ponga el Bx en una línea y el % debajo
            labels.push([`B${i}`, probStr]);
            dataValues.push(bucketCounts[i]);
            validNodesCount += bucketCounts[i];
        }
    }

    const subtitleEl = document.getElementById('bucketsSubtitle');
    if (subtitleEl) {
        subtitleEl.textContent = `Total: ${validNodesCount} | XOR Distance`;
    }

    // Limpieza preventiva para evitar errores de reutilización de canvas en Chart.js
    const existingChart = Chart.getChart(ctx.canvas);
    if (existingChart) {
        existingChart.destroy();
    }

    bucketsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Nodos',
                data: dataValues,
                backgroundColor: context => {
                    const index = context.dataIndex;
                    const labelArr = context.chart.data.labels[index];
                    if (!labelArr) return 'rgba(79, 172, 254, 0.6)';

                    const bucketName = labelArr[0]; // "B4"
                    const bucketNum = parseInt(bucketName.substring(1));

                    // Si el IDS detecta envenenamiento en este bucket, pintar de ROJO
                    const isPoisoned = globalThis.activeIDSAlerts.some(a =>
                        a.type === 'poisoning' && parseInt(a.target_bucket) === bucketNum
                    );
                    return isPoisoned ? 'rgba(255, 23, 68, 0.8)' : 'rgba(79, 172, 254, 0.6)';
                },
                borderColor: context => {
                    const index = context.dataIndex;
                    const labelArr = context.chart.data.labels[index];
                    if (!labelArr) return '#4facfe';

                    const bucketName = labelArr[0];
                    const bucketNum = parseInt(bucketName.substring(1));

                    const isPoisoned = globalThis.activeIDSAlerts.some(a =>
                        a.type === 'poisoning' && parseInt(a.target_bucket) === bucketNum
                    );
                    return isPoisoned ? '#ff1744' : '#4facfe';
                },
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (context) => {
                            const item = context[0];
                            const labelArr = item.chart.data.labels[item.dataIndex];
                            return `Bucket ${labelArr[0]} (Prob: ${labelArr[1]})`;
                        },
                        label: (context) => ` Nodos: ${context.raw}`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 10 } },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                x: {
                    ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 9 } },
                    grid: { display: false }
                }
            }
        }
    });
}


// 3. Simulación visual de interactividad de red Kademlia (FIND_NODE y Respuestas)
function simulateKadActivity(nodes) {
    if (!nodes || nodes.length < 2) return;

    // Limpiamos la simulación anterior si existiera
    if (simulationInterval) clearInterval(simulationInterval);

    simulationInterval = setInterval(() => {
        // 1. Si el Mapa Térmico está activo, desactivamos el tráfico simulado para no ensuciar la visualización RTT
        // 2. Si la red Kad está desconectada, tampoco hay tráfico
        if (heatMapMode || udpHeatMapMode || elStatus.classList.contains('status-disconnected')) {
            // Purgamos los arcos y anillos que pudieran quedar en pantalla
            renderGlobe.arcsData([]).ringsData([]);
            return;
        }

        const arcs = [];
        const rings = [];

        // --- INTEGRACIÓN IDS EN SIMULACIÓN ---
        const dangerAlerts = (globalThis.activeIDSAlerts || []).filter(a =>
            ['eclipse', 'sybil', 'dos', 'poisoning'].includes(a.type) || a.severity === 'critical'
        );

        dangerAlerts.forEach(alert => {
            const targetNode = nodes.find(n => n.ip === alert.target_ip || n.id === alert.target_id);
            if (targetNode) {
                rings.push({
                    lat: targetNode.lat,
                    lng: targetNode.lng,
                    maxR: alert.severity === 'critical' ? 8 : 5,
                    propagationSpeed: 2,
                    repeatPeriod: 1000,
                    isIDS: true // Flag para color
                });
            }
        });

        // Simulo un máximo de 5-10 consultas concurrentes en la red
        const numQueries = Math.floor(secureRandom() * 5) + 5;

        for (let i = 0; i < numQueries; i++) {
            // Elige un nodo origen y un destino al azar simulando el enrutamiento Kademlia
            const source = nodes[Math.floor(secureRandom() * nodes.length)];
            const target = nodes[Math.floor(secureRandom() * nodes.length)];

            if (source && target && source !== target) {
                // Arco de Luz Saliente (Consulta FIND_NODE)
                arcs.push({
                    startLat: source.lat,
                    startLng: source.lng,
                    endLat: target.lat,
                    endLng: target.lng,
                    color: ['rgba(0, 242, 254, 0.1)', 'rgba(79, 172, 254, 0.9)']
                });

                // Pulso de Color (Respuesta Recibida) en el destino
                rings.push({
                    lat: target.lat,
                    lng: target.lng,
                    maxR: secureRandom() * 3 + 2,
                    propagationSpeed: secureRandom() * 2 + 1,
                    repeatPeriod: 600 + secureRandom() * 800
                });
            }
        }

        // Inyectar animaciones al globo
        renderGlobe
            .arcsData(arcs)
            .arcColor('color')
            .arcDashLength(0.4)
            .arcDashGap(0.2)
            .arcDashAnimateTime(1500) // 1.5s para cruzar el planeta resolviendo la latencia
            .ringsData(rings)
            .ringColor(d => d.isIDS ? '#9d00ff' : '#00e676') // Violeta para IDS, Verde para normal
            .ringMaxRadius(d => d.maxR || 5)
            .ringPropagationSpeed(d => d.propagationSpeed || 1)
            .ringRepeatPeriod(d => d.repeatPeriod || 1000);

    }, 2000); // Se actualizan las ráfagas de paquetes cada 2 segundos
}

// 4. Función de actualización de Overlays IDS (Anillos Púrpuras)
function updateIDSOverlays() {
    if (!renderGlobe || !globalNodesArray.length) return;

    // Solo si hay alertas críticas o de tipo ataque dirigido
    const dangerAlerts = globalThis.activeIDSAlerts.filter(a =>
        ['eclipse', 'sybil', 'dos', 'poisoning'].includes(a.type) || a.severity === 'critical'
    );

    if (dangerAlerts.length === 0) return;

    const idsRings = [];
    dangerAlerts.forEach(alert => {
        // Buscar coordenadas del nodo objetivo
        const targetNode = globalNodesArray.find(n => n.ip === alert.target_ip || n.id === alert.target_id);
        if (targetNode) {
            idsRings.push({
                lat: targetNode.lat,
                lng: targetNode.lng,
                maxR: alert.severity === 'critical' ? 8 : 5,
                propagationSpeed: 2,
                repeatPeriod: 1000,
                color: '#9d00ff' // Violeta IDS
            });
        }
    });

    // Inyectamos rings IDS (esto sobreescribe los de simulación temporalmente en el siguiente ciclo)
    if (idsRings.length > 0) {
        renderGlobe.ringsData(idsRings)
            .ringColor(d => d.color || '#00e676');
    }
    // Forzar refresco de puntos para que cambien de color/altura si fueron marcados
    renderGlobe.pointColor(getPointColor)
        .pointAltitude(getPointAltitude);
}

// 5. Helper para hacer elementos arrastrables
function makeDraggable(el, handle) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    handle.onmousedown = dragMouseDown;
    handle.ontouchstart = dragMouseDown;

    function dragMouseDown(e) {
        e = e || window.event;
        const clientX = e.clientX || (e.touches && e.touches[0].clientX);
        const clientY = e.clientY || (e.touches && e.touches[0].clientY);
        
        const rect = el.getBoundingClientRect();
        const startX = clientX;
        const startY = clientY;
        const initialTop = rect.top;
        const initialLeft = rect.left;

        // Desactivar transformaciones para control total por top/left
        el.style.transform = 'none';
        el.style.margin = '0';
        el.style.top = initialTop + "px";
        el.style.left = initialLeft + "px";

        function onMouseMove(moveEvent) {
            moveEvent.preventDefault();
            const curX = moveEvent.clientX || (moveEvent.touches && moveEvent.touches[0].clientX);
            const curY = moveEvent.clientY || (moveEvent.touches && moveEvent.touches[0].clientY);
            
            const dx = curX - startX;
            const dy = curY - startY;
            
            el.style.top = (initialTop + dy) + "px";
            el.style.left = (initialLeft + dx) + "px";
        }

        function onMouseUp() {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            document.removeEventListener('touchmove', onMouseMove);
            document.removeEventListener('touchend', onMouseUp);
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.addEventListener('touchmove', onMouseMove, { passive: false });
        document.addEventListener('touchend', onMouseUp);
    }
}

// 4. Ejecución inicial y Polling cíclico
applyTranslations();

// Llamadas iniciales no bloqueantes (Sin await en el flujo principal)
updateKadStats().catch(e => console.warn("Initial stats fetch failed", e));
updateKadNodes().catch(e => console.warn("Initial nodes fetch failed", e));
initIDS();

// Polling de 10s para datos generales
setInterval(() => {
    updateKadStats();
    updateKadNodes();
}, 10000);
