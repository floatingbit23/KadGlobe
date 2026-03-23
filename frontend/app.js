// Referencias a los elementos del DOM (HTML)
const elStatus = document.getElementById('kadStatus');
const elContacts = document.getElementById('kadContacts');
const elContactsDiff = document.getElementById('kadContactsDiff');
const elSearches = document.getElementById('kadSearches');
const elMappedNodes = document.getElementById('kadMappedNodes');
const elCountryList = document.getElementById('countryList');
const elXorNeighborsPanel = document.getElementById('xorNeighborsPanel');
const elXorNeighborsList = document.getElementById('xorNeighborsList');

// --- DICCIONARIO i18n ---
let currentLang = 'es';

const i18n = {
    es: {
        "net_status": "Estado de Red:",
        "loading": "Cargando...",
        "contacts": "Contactos Kad:",
        "searches": "Búsquedas Activas:",
        "mapped": "Nodos Georreferenciados:",
        "ranking_title": "Nodos por país",
        "xor_neighbors_title": "Top 10 Vecindario XOR",
        "modal_title": "Información del Nodo",
        "modal_xor": "● Proyectando Vecindario Kad (XOR)",
        "modal_loc": "Ubicación:",
        "unknown": "Desconocido",
        "unknown_f": "Desconocida",
        "status_connected": "Conectado",
        "status_disconnected": "Desconectado",
        "status_firewalled": "Tras Cortafuego"
    },
    en: {
        "net_status": "Network Status:",
        "loading": "Loading...",
        "contacts": "Kad Contacts:",
        "searches": "Active Searches:",
        "mapped": "Georeferenced Nodes:",
        "ranking_title": "Nodes by country",
        "xor_neighbors_title": "Top 10 XOR Neighborhood",
        "modal_title": "Node Information",
        "modal_xor": "● Projecting Kad Neighborhood (XOR)",
        "modal_loc": "Location:",
        "unknown": "Unknown",
        "unknown_f": "Unknown",
        "status_connected": "Connected",
        "status_disconnected": "Disconnected",
        "status_firewalled": "Firewalled"
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
    .pointAltitude('size')      // Utilizamos el "size" extraído de la BD
    .pointRadius(0.2)           // Ancho del radio del pilar
    .pointColor(() => '#00f2fe') // Azul brillante estático blindado


    // Tarjeta emergente (Tooltip) que aparece al pasar el ratón por los nodos
    .pointLabel(d => `
        <div style="background: rgba(10, 15, 30, 0.9); padding: 10px; border-radius: 8px; border: 1px solid #4facfe; color: white; font-family: Inter, sans-serif;">
            <b style="font-size: 14px;">${d.city !== "-" && d.city !== "Unknown" ? d.city : 'Desconocida'}</b><br/>
            <i style="color: #ccc;">${d.country !== "-" && d.country !== "Unknown" ? d.country : 'Desconocido'}</i><br/>
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
    modalLocation.textContent = `${node.city !== "-" ? node.city : "?"}, ${node.country !== "-" ? node.country : "?"}`;
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
        li.innerHTML = `<span>#${index + 1}</span> <span>${neighbor.obj.ip}</span>`;
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

            if (data.status) {
                const statusLower = data.status.toLowerCase();
                // Importante: Chequear 'disconnect' ANTES que 'connect' porque 'disconnected' contiene ambos
                if (statusLower.includes('disconnect')) {
                    elStatus.classList.add('status-disconnected');
                    displayStatus = i18n[currentLang].status_disconnected;
                } else if (statusLower.includes('connect')) {
                    elStatus.classList.add('status-connected');
                    displayStatus = i18n[currentLang].status_connected;
                } else if (statusLower.includes('firewall')) {
                    elStatus.classList.add('status-firewalled');
                    displayStatus = i18n[currentLang].status_firewalled;
                }
            }

            elStatus.textContent = displayStatus;

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

            elSearches.textContent = data.current_searches || '0'; // Default numeric fallback

            // Gestión de estilos dinámicos según el estado (Connected, Disconnected, Firewalled)
            elStatus.classList.remove('status-connected', 'status-disconnected', 'status-firewalled');

            if (data.status) {
                const statusLower = data.status.toLowerCase();
                // Importante: Chequear 'disconnect' ANTES que 'connect' porque 'disconnected' contiene ambos
                if (statusLower.includes('disconnect')) {
                    elStatus.classList.add('status-disconnected');
                } else if (statusLower.includes('connect')) {
                    elStatus.classList.add('status-connected');
                } else if (statusLower.includes('firewall')) {
                    elStatus.classList.add('status-firewalled');
                }
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
    if (!hex1 || !hex2) return BigInt(0);
    return BigInt('0x' + hex1) ^ BigInt('0x' + hex2);
}

// B. Función que obtiene todas las ubicaciones y recrea los nodos en el globo
async function updateKadNodes() {
    try {
        const response = await fetch('/jsons/kad_nodes_geospatial.json?t=' + Date.now());

        if (response.ok) {
            const newNodesArray = await response.json();

            globalNodesArray = newNodesArray; // Volcamos al caché global para que actúe JS al hacer Click

            // Inyectamos todo el json de memoria plano al renderizador 3D como en la primera versión robusta
            renderGlobe.pointsData(newNodesArray);

            // Reflejamos los vivos en la UI
            elMappedNodes.textContent = newNodesArray.length;

            // ----------------------------------------------------------------------------------
            // A. Motor Map-Reduce de Top Países (Lista lateral en tiempo real)
            // ----------------------------------------------------------------------------------
            const countryData = {};
            newNodesArray.forEach(node => {
                const cname = (node.country && node.country !== "-" && node.country !== "Unknown") ? node.country : i18n[currentLang].unknown;
                if (!countryData[cname]) {
                    countryData[cname] = { count: 0, code: node.country_code || 'unknown' };
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
                simulateKadActivity(newNodesArray);
            }
        } else {
            elMappedNodes.textContent = `HTTP ${response.status}`;
        }
    } catch (e) {
        elMappedNodes.textContent = `[JS Fallo] ${e.message}`;
        console.warn('[!] Error obteniendo kad_nodes_geospatial.json:', e);
    }
}

// 3. Simulación visual de interactividad de red Kademlia (FIND_NODE y Respuestas)
function simulateKadActivity(nodes) {
    if (!nodes || nodes.length < 2) return;

    // Limpiamos la simulación anterior si existiera
    if (simulationInterval) clearInterval(simulationInterval);

    simulationInterval = setInterval(() => {
        // Validación obligatoria: Si la red Kad está desconectada, no hay tráfico que simular
        const currentStatus = elStatus.textContent.toLowerCase();
        if (currentStatus.includes('disconnect')) {
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
