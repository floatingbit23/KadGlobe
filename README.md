Una interfaz web para mostrar en 3D los nodos de la red Kademlia a los que estás conectado al descargar archivos usando el cliente P2P eMule.

Flujo teórico:

1. Backend (Bridge): Un script en Python que consulte el servidor web de eMule/aMule.

2. Procesamiento: El Bridge convierte esa lista de IDs de 128 bits en coordenadas cartesianas (x,y,z) usando la lógica matemática XOR (o un algoritmo de disposición de grafos).

3. Frontend (3D): Una página web simple con Three.js que reciba esos puntos y los pinte en el globo terráqueo.
