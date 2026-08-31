# Memoria de configuración del escenario Packet Tracer

En este ejercicio se construyó la topología con dos routers 1941, dos switches 2960 y
cinco PCs. Se configuró enrutamiento inter-VLAN mediante router-on-a-stick, DHCP en
los dos routers, rutas estáticas entre las sedes y acceso SSH a S1 desde PC1.

## 1. Plan de direccionamiento

| Dispositivo / interfaz | Dirección | Máscara | Uso |
|---|---:|---:|---|
| R1 G0/0.5 | 172.20.1.1 | 255.255.255.0 | Gateway VLAN 5, Cafetería |
| R1 G0/0.15 | 172.20.2.1 | 255.255.255.0 | Gateway VLAN 15, Pública |
| S1 VLAN 50 | 192.168.1.1 | 255.255.255.0 | Administración y SSH |
| PC1 | 192.168.1.10 | 255.255.255.0 | Administración, configuración estática |
| R1 G0/1 | 192.168.100.1 | 255.255.255.252 | Enlace R1–R2 |
| R2 G0/0 | 192.168.100.2 | 255.255.255.252 | Enlace R1–R2 |
| R2 G0/1.25 | 10.0.1.1 | 255.255.255.0 | Gateway VLAN 25, Privada |
| R2 G0/1.15 | 10.0.2.1 | 255.255.255.0 | Gateway VLAN 15, Personal |

Se reservaron las direcciones `.1` a `.10` de cada LAN. Como solamente hay un cliente en
cada pool, las direcciones asignadas por DHCP fueron:

- PC0: `172.20.1.11/24`, gateway `172.20.1.1`.
- PC2: `172.20.2.11/24`, gateway `172.20.2.1`.
- PC3: `10.0.1.11/24`, gateway `10.0.1.1`.
- PC4: `10.0.2.11/24`, gateway `10.0.2.1`.
- PC1: `192.168.1.10/24`, sin gateway. La VLAN 50 no se enruta.

Se configuraron **cuatro pools DHCP**, porque VLAN 15 existe en dos dominios de capa 2
distintos y utiliza una subred diferente en cada extremo.

## 2. Puertos utilizados

| Switch | Puerto | Conexión | Configuración |
|---|---|---|---|
| S1 | Fa0/1 | R1 G0/0 | Trunk, VLAN 5, 15 y 50 |
| S1 | Fa0/2 | PC0 | Access VLAN 5 |
| S1 | Fa0/3 | PC1 | Access VLAN 50 |
| S1 | Fa0/4 | PC2 | Access VLAN 15 |
| S2 | Fa0/1 | R2 G0/1 | Trunk, VLAN 15 y 25 |
| S2 | Fa0/2 | PC3 | Access VLAN 25 |
| S2 | Fa0/3 | PC4 | Access VLAN 15 |

## 3. Configuración de R1

```ios
enable
configure terminal
hostname R1
no ip domain-lookup
service password-encryption
enable secret EnableR1_2026
banner motd # ACCESO EXCLUSIVO PARA PERSONAL AUTORIZADO #

line console 0
 password ConsolaR1_2026
 login
 logging synchronous
 exec-timeout 5 0
exit

interface gigabitEthernet0/0
 description TRUNK_HACIA_S1
 no ip address
 no shutdown
exit

interface gigabitEthernet0/0.5
 description GW_VLAN5_CAFETERIA
 encapsulation dot1Q 5
 ip address 172.20.1.1 255.255.255.0
exit

interface gigabitEthernet0/0.15
 description GW_VLAN15_PUBLICA
 encapsulation dot1Q 15
 ip address 172.20.2.1 255.255.255.0
exit

interface gigabitEthernet0/1
 description ENLACE_A_R2
 ip address 192.168.100.1 255.255.255.252
 no shutdown
exit

ip dhcp excluded-address 172.20.1.1 172.20.1.10
ip dhcp excluded-address 172.20.2.1 172.20.2.10

ip dhcp pool VLAN5_CAFETERIA
 network 172.20.1.0 255.255.255.0
 default-router 172.20.1.1
 dns-server 8.8.8.8
exit

ip dhcp pool VLAN15_PUBLICA
 network 172.20.2.0 255.255.255.0
 default-router 172.20.2.1
 dns-server 8.8.8.8
exit

ip route 10.0.1.0 255.255.255.0 192.168.100.2
ip route 10.0.2.0 255.255.255.0 192.168.100.2

end
copy running-config startup-config
```

## 4. Configuración de R2

```ios
enable
configure terminal
hostname R2
no ip domain-lookup
service password-encryption
enable secret EnableR2_2026
banner motd # ACCESO EXCLUSIVO PARA PERSONAL AUTORIZADO #

line console 0
 password ConsolaR2_2026
 login
 logging synchronous
 exec-timeout 5 0
exit

interface gigabitEthernet0/1
 description TRUNK_HACIA_S2
 no ip address
 no shutdown
exit

interface gigabitEthernet0/1.25
 description GW_VLAN25_PRIVADA
 encapsulation dot1Q 25
 ip address 10.0.1.1 255.255.255.0
exit

interface gigabitEthernet0/1.15
 description GW_VLAN15_PERSONAL
 encapsulation dot1Q 15
 ip address 10.0.2.1 255.255.255.0
exit

interface gigabitEthernet0/0
 description ENLACE_A_R1
 ip address 192.168.100.2 255.255.255.252
 no shutdown
exit

ip dhcp excluded-address 10.0.1.1 10.0.1.10
ip dhcp excluded-address 10.0.2.1 10.0.2.10

ip dhcp pool VLAN25_PRIVADA
 network 10.0.1.0 255.255.255.0
 default-router 10.0.1.1
 dns-server 8.8.8.8
exit

ip dhcp pool VLAN15_PERSONAL
 network 10.0.2.0 255.255.255.0
 default-router 10.0.2.1
 dns-server 8.8.8.8
exit

ip route 172.20.1.0 255.255.255.0 192.168.100.1
ip route 172.20.2.0 255.255.255.0 192.168.100.1

end
copy running-config startup-config
```

## 5. Configuración de S1

```ios
enable
configure terminal
hostname S1
no ip domain-lookup
service password-encryption
enable secret EnableS1_2026
banner motd # ACCESO EXCLUSIVO PARA PERSONAL AUTORIZADO #

vlan 5
 name CAFETERIA
exit
vlan 15
 name PUBLICA
exit
vlan 50
 name MGMT
exit

interface fastEthernet0/1
 description TRUNK_HACIA_R1
 switchport mode trunk
 switchport trunk allowed vlan 5,15,50
 no shutdown
exit

interface fastEthernet0/2
 description PC0_CAFETERIA
 switchport mode access
 switchport access vlan 5
 spanning-tree portfast
 no shutdown
exit

interface fastEthernet0/3
 description PC1_ADMINISTRACION
 switchport mode access
 switchport access vlan 50
 spanning-tree portfast
 no shutdown
exit

interface fastEthernet0/4
 description PC2_PUBLICA
 switchport mode access
 switchport access vlan 15
 spanning-tree portfast
 no shutdown
exit

interface vlan 50
 description ADMINISTRACION_S1
 ip address 192.168.1.1 255.255.255.0
 no shutdown
exit

username admin privilege 15 secret AdminS1_2026
ip domain-name redes.local
crypto key generate rsa
! Se ingresó 1024 cuando IOS solicitó el tamaño del módulo
ip ssh version 2

line console 0
 password ConsolaS1_2026
 login
 logging synchronous
 exec-timeout 5 0
exit

line vty 0 15
 login local
 transport input ssh
 exec-timeout 5 0
exit

interface range fastEthernet0/5-24,gigabitEthernet0/1-2
 description PUERTOS_NO_UTILIZADOS
 shutdown
exit

end
copy running-config startup-config
```

No se configuró `ip default-gateway` ni una subinterfaz de R1 para VLAN 50, porque la red
de administración no debe ser enrutada. PC1 y la SVI de S1 se comunican directamente
dentro de la misma VLAN.

## 6. Configuración de S2

```ios
enable
configure terminal
hostname S2
no ip domain-lookup
service password-encryption
enable secret EnableS2_2026
banner motd # ACCESO EXCLUSIVO PARA PERSONAL AUTORIZADO #

vlan 15
 name PERSONAL
exit
vlan 25
 name PRIVADA
exit

interface fastEthernet0/1
 description TRUNK_HACIA_R2
 switchport mode trunk
 switchport trunk allowed vlan 15,25
 no shutdown
exit

interface fastEthernet0/2
 description PC3_PRIVADA
 switchport mode access
 switchport access vlan 25
 spanning-tree portfast
 no shutdown
exit

interface fastEthernet0/3
 description PC4_PERSONAL
 switchport mode access
 switchport access vlan 15
 spanning-tree portfast
 no shutdown
exit

line console 0
 password ConsolaS2_2026
 login
 logging synchronous
 exec-timeout 5 0
exit

interface range fastEthernet0/4-24,gigabitEthernet0/1-2
 description PUERTOS_NO_UTILIZADOS
 shutdown
exit

end
copy running-config startup-config
```

Como buena práctica, se apagaron todos los puertos que quedaron sin utilizar. También
se configuraron contraseñas cifradas, banner de advertencia, descripción de interfaces,
PortFast en los puertos de usuarios y temporizadores de sesión.

## 7. Configuración de las PCs

1. Se configuraron PC0, PC2, PC3 y PC4 mediante **Desktop > IP Configuration > DHCP**.
2. Se configuró PC1 mediante **Desktop > IP Configuration > Static**:
   - IP Address: `192.168.1.10`
   - Subnet Mask: `255.255.255.0`
   - Default Gateway: `0.0.0.0`
   - DNS Server: `0.0.0.0`

## 8. Verificación

Se utilizaron los siguientes comandos para revisar la configuración:

```ios
show ip interface brief
show ip route
show ip dhcp binding
show ip dhcp pool
show vlan brief
show interfaces trunk
show ip ssh
show running-config
```

Resultados comprobados en el archivo final:

1. El enlace R1–R2 responde entre `192.168.100.1` y `192.168.100.2`.
2. Desde PC0 se obtuvo respuesta de PC2, PC3 y PC4.
3. Las cuatro redes de usuarios se alcanzan mediante las rutas estáticas.
4. Desde PC1 se obtuvo respuesta de `192.168.1.1`.
5. Desde PC1 se inició sesión con `ssh -l admin 192.168.1.1` y se comprobó que S1
   tiene SSH versión 2 habilitado.

PC1 no alcanza las otras redes, lo cual confirma que VLAN 50 permanece aislada y sin
enrutamiento.
