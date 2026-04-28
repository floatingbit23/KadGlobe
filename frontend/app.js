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
const elSourcesRow = document.getElementById('kadSourcesRow');
const elSources = document.getElementById('kadSources');

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
        "self_node_label": "ESTE ERES TÚ (eMule)"
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
        "self_node_label": "THIS IS YOU (eMule)"
    }
};

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
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

        if (typeof renderGlobe !== 'undefined') {
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
    .globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg') // Textura HD
    .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')    // Relieve topográfico
    .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')   // Fondo estelar

    // Configuración para los puntos y pilares de los Nodos Kad (Nodos Conocidos)
    // HE QUITADO pointsMerge(true) para que Globe.gl envíe los eventos de Click y el ratón reconozca los pilares individuales.
    .pointLat('lat')
    .pointLng('lng')
    .pointAltitude(getPointAltitude) // Evaluación dinámica del tamaño (crece en modo Activos)
    .pointRadius(0.2)                // Ancho del radio del pilar
    .pointColor(getPointColor)       // Color atado la evaluación dinámica en caliente


    // Tarjeta emergente (Tooltip) que aparece al pasar el ratón por los nodos
    .pointLabel(d => `
        <div style="background: rgba(10, 15, 30, 0.9); padding: 10px; border-radius: 8px; border: 1px solid #4facfe; color: white; font-family: Inter, sans-serif;">
            <b style="font-size: 14px;">${d.is_self ? i18n[currentLang].self_node_label : (d.city !== "-" && d.city !== "Unknown" ? d.city : i18n[currentLang].unknown_f)}</b><br/>
            <i style="color: #ccc;">${d.country !== "-" && d.country !== "Unknown" ? d.country : i18n[currentLang].unknown}</i><br/>
            <small style="color: #666; margin-top: 4px; display: block;">ID: ${d.id.substring(0, 8)}...</small>
        </div>
    `)
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
    neighbors.sort((a, b) => (a.dist < b.dist ? -1 : (a.dist > b.dist ? 1 : 0)));

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

// A. Función que obtiene el estado general de Kad
async function updateKadStats() {
    try {
        // Añadimos cache-buster (?t=) para garantizar que el navegador descarga de Python y no usa memoria caché local
        const response = await fetch('/jsons/kad_stats.json?t=' + Date.now());

        if (response.ok) {
            const data = await response.json();

            // Re-traducción del estado en crudo del eMule WebUI
            let displayStatus = data.status || i18n[currentLang].unknown;
            elStatus.classList.remove('status-connected', 'status-disconnected', 'status-firewalled');

            let isDisconnected = false;
            let isFirewalled = false;
            if (data.status) {
                const statusLower = data.status.toLowerCase();
                // Importante: Chequear 'disconnect' ANTES que 'connect' porque 'disconnected' contiene ambos
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

            // Bloquear botón "Nodos Activos" si Kad está desconectado
            const btnHeatMap = document.getElementById('heatMapToggle');
            if (btnHeatMap) {
                if (isDisconnected) {
                    btnHeatMap.disabled = true;
                    btnHeatMap.style.opacity = '0.3';
                    btnHeatMap.style.filter = 'grayscale(1)';
                    btnHeatMap.style.cursor = 'not-allowed';
                    btnHeatMap.title = currentLang === 'es' ? ' ❌ Función deshabilitada: Kad desconectado!' : ' ❌ Function disabled: Kad is not connected!';

                    // Si el modo térmico estaba activo, lo apagamos forzosamente para evitar confusión
                    if (heatMapMode) {
                        heatMapMode = false;
                        btnHeatMap.style.background = '';
                        btnHeatMap.style.borderColor = '';
                        btnHeatMap.style.color = '';
                        btnHeatMap.style.boxShadow = '';
                        if (typeof renderGlobe !== 'undefined') {
                            renderGlobe.pointColor(getPointColor);
                            renderGlobe.pointAltitude(getPointAltitude);
                            renderGlobe.pointsData([...globalNodesArray]);
                        }
                    }
                } else if (isFirewalled) {
                    // Si está Firewalled, permitimos el uso pero avisamos
                    btnHeatMap.disabled = false;
                    btnHeatMap.style.opacity = '1';
                    btnHeatMap.style.filter = 'none';
                    btnHeatMap.style.cursor = 'pointer';
                    btnHeatMap.title = currentLang === 'es' ?
                        '⚠️ ¡Atención! Estás Tras Cortafuegos (Firewalled). La visibilidad de red puede ser limitada.' :
                        '⚠️ Warning! You are Firewalled. Network visibility might be limited.';
                    btnHeatMap.style.boxShadow = '0 0 10px rgba(255, 204, 0, 0.4)'; // Brillo amarillo de advertencia
                } else {
                    // Estado óptimo: Conectado / Abierto
                    btnHeatMap.disabled = false;
                    btnHeatMap.style.opacity = '1';
                    btnHeatMap.style.filter = 'none';
                    btnHeatMap.style.cursor = 'pointer';
                    btnHeatMap.style.boxShadow = '';
                    btnHeatMap.title = '';
                }
            }

            // Lógica de historial de contactos para inyectar diferencias (+N / -N)
            const currentContacts = parseInt(data.contacts || '0', 10);
            elContacts.textContent = currentContacts;

            if (previousContacts !== null && elContactsDiff) {
                const diff = currentContacts - previousContacts;
                if (diff > 0) {
                    elContactsDiff.textContent = `(+${diff})`;
                    elContactsDiff.style.color = '#00e676'; // Verde matrix
                } else if (diff < 0) {
                    elContactsDiff.textContent = `(${diff})`; // El '-' ya va incluido en diff
                    elContactsDiff.style.color = '#ff4d4d'; // Rojo alerta
                } else {
                    elContactsDiff.textContent = ''; // Lo ocultamos si no han entrado nuevos
                }
            }
            previousContacts = currentContacts; // Actualizamos la memoria

            elSearches.textContent = data.active_searches || '0'; // Default numeric fallback

            // Inyectamos las nuevas estadísticas enriquecidas (Phase 13+14)
            if (data.kad_status) {
                const ksLower = data.kad_status.toLowerCase();
                let displayKadStatus = data.kad_status;

                // Traducción dinámica para evitar el mix de idiomas (Phase 15 fix)
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

            // Guardamos el local_id para los cálculos de buckets
            if (data.local_id) {
                window.localKadId = data.local_id;
            }
        } else {
            elStatus.textContent = `Error HTTP: ${response.status}`;
        }
    } catch (e) {
        elStatus.textContent = `[JS Error] ${e.message}`;
        console.warn('[!] Error obteniendo kad_stats.json:', e);
    }
}

// Variables Globales de control Topológico
let globalNodesArray = [];
let selectedNode = null;
let simulationInterval = null;

// Función matemática base del artículo Kademlia P2P (Restamos 128-bits usando BigInt nativo de ES6)
function getKadDistance(hex1, hex2) {
    if (!hex1 || !hex1.match(/^[0-9a-fA-F]+$/) || !hex2 || !hex2.match(/^[0-9a-fA-F]+$/)) return BigInt(0);
    try {
        return BigInt('0x' + hex1) ^ BigInt('0x' + hex2);
    } catch (e) {
        return BigInt(0);
    }
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

                        // Si el nodo fresco NO está en la lista base (nodes.dat), lo inyectamos dinámicamente
                        const exists = mergedNodes.some(n => n.ip === rn.ip);
                        if (!exists) {
                            mergedNodes.push({
                                ...rn,
                                size: 0.01, // Por defecto mismo tamaño que los base
                                isFresh: true
                            });
                        } else {
                            // Si existe, nos aseguramos de que tenga las propiedades de 'rn' (como is_self)
                            const idx = mergedNodes.findIndex(n => n.ip === rn.ip);
                            mergedNodes[idx] = { ...mergedNodes[idx], ...rn };
                        }
                    });

                    updateHeatmapButtonText();
                }
            } catch (e) { }

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
            if (window.localKadId && window.localKadId !== "Unknown") {
                updateKBucketsChart(mergedNodes, window.localKadId);
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

        // El bucket es la posición del bit más significativo (log2)
        // En JS con BigInt: toString(2).length - 1
        const bucketIndex = dist.toString(2).length - 1;
        if (bucketIndex >= 0 && bucketIndex <= 128) {
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

    for (let i = 0; i <= 128; i++) {
        if (bucketCounts[i] > 0) {
            // Calcular la probabilidad matemática de caer en esta cubeta (1 / 2^(128-i))
            const probPct = (1 / Math.pow(2, 128 - i)) * 100;
            const probStr = probPct >= 1 ? `${Math.round(probPct)}%` :
                (probPct >= 0.01 ? `${probPct.toFixed(2)}%` : `<0.01%`);

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

    if (!bucketsChart) {
        bucketsChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Nodos',
                    data: dataValues,
                    backgroundColor: 'rgba(79, 172, 254, 0.6)',
                    borderColor: '#4facfe',
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
    } else {
        bucketsChart.data.labels = labels;
        bucketsChart.data.datasets[0].data = dataValues;
        bucketsChart.update();
    }
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

        // Simulo un máximo de 5-10 consultas concurrentes en la red
        const numQueries = Math.floor(Math.random() * 5) + 5;

        for (let i = 0; i < numQueries; i++) {
            // Elige un nodo origen y un destino al azar simulando el enrutamiento Kademlia
            const source = nodes[Math.floor(Math.random() * nodes.length)];
            const target = nodes[Math.floor(Math.random() * nodes.length)];

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
                    maxR: Math.random() * 3 + 2,
                    propagationSpeed: Math.random() * 2 + 1,
                    repeatPeriod: 600 + Math.random() * 800
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
            .ringColor(() => '#00e676') // Color verde esmeralda brillante para la respuesta exitosa
            .ringMaxRadius('maxR')
            .ringPropagationSpeed('propagationSpeed')
            .ringRepeatPeriod('repeatPeriod');

    }, 2000); // Se actualizan las ráfagas de paquetes cada 2 segundos
}

// 4. Ejecución inicial y Polling cíclico
// Ejecuto ambas extracciones inmediatamente al cargar la página
applyTranslations();
updateKadStats();
updateKadNodes();

// Repito la extracción de ambos archivos locales cada 10 segundos
// Así "simulo" reactividad cuando mi script Python los sobreescriba
setInterval(() => {
    updateKadStats();
    updateKadNodes();
}, 10000);
