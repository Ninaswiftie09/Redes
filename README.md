# Laboratorio 3 - Algoritmos de Enrutamiento

## Integrantes
   - Nina Nájera - 231088
   - Eliazar Canastuj - 23384

## Implementacion

- Cinco routers 2811 con IOS 15.1, cuatro switches 2960 y seis PCs.
- Seis enlaces seriales /30 dentro de 10.0.0.0/24. DCE a 64000 bit/s.
- OSPF, proceso 1, area 0; EIGRP, AS 100. Interfaces de usuario pasivas.
- Router-on-a-stick: VLAN 10 y 30 en OSPF-1; VLAN 10 y 20 en EIGRP-1.
- OSPF: costo directo 20 y costo via CENTRAL 10+10. La LAN remota agrega 1 a ambos caminos (total 21).
- EIGRP: bandwidth 100000 kbps en seriales, delay directo 1000, acceso->CENTRAL 3219, CENTRAL->acceso 1. delay usa unidades de 10 microsegundos. Variance 4 y dos caminos instalados. Las metricas mantienen una relacion 1:3 y el camino secundario cumple factibilidad. La evidencia de configuracion solicitada esta disponible; no se requiere medir trafico real. El detalle de rutas del simulador muestra contadores traffic-share iguales, por lo que no se afirma un porcentaje efectivo medido.
- Para la LAN EIGRP remota: 284160 por el enlace directo y 852480 via CENTRAL; proporcion 3:1. Distancia reportada del camino secundario 28416 < 284160: cumple factibilidad.

## PCs

| PC | IP | Prefijo | Gateway |
|---|---|---|---|
| OSPF-1 datos | 192.168.1.10 | /26 | 192.168.1.1 |
| OSPF-1 admin | 192.168.1.70 | /28 | 192.168.1.65 |
| OSPF-2 LAN | 192.168.0.10 | /24 | 192.168.0.1 |
| EIGRP-1 datos | 172.16.0.140 | /26 | 172.16.0.129 |
| EIGRP-1 voz | 172.16.0.200 | /27 | 172.16.0.193 |
| EIGRP-2 LAN | 172.16.0.10 | /25 | 172.16.0.1 |


## Estado de la entrega

Se incluyen los documentos [PDF1](<Docs/Lab3 pdf1.pdf>) y [PDF2](Docs/PDF2.pdf), el archivo [Laboratorio3.pkt](PacketTracer/Laboratorio3.pkt), las configuraciones y las evidencias de verificacion. El resumen hacia OSPF utiliza una adaptacion estatica del simulador, descrita en el PDF2.
