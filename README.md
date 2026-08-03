# Laboratorio 2

## Integrantes

- Nina Nájera Marakovits - 231088
- Diego Ramirez - 23601

## Descripción

En este laboratorio se desarrollaron dos programas para simular la detección y corrección de errores durante el envío de información.

El emisor fue realizado en Python y el receptor en Java. Por el momento, la salida del emisor se copia y se pega manualmente en el receptor.

## Algoritmos utilizados

### Código de Hamming

Se utiliza para corregir errores. Agrega bits de paridad a la información y permite encontrar y corregir un bit incorrecto.

### Fletcher Checksum

Se utiliza para detectar errores. Calcula un valor de verificación que se envía junto con el mensaje. El receptor vuelve a calcularlo y compara los resultados.

Se incluyen las variantes:

- Fletcher-8
- Fletcher-16
- Fletcher-32

## Funcionamiento

1. El emisor recibe un mensaje binario o un texto.
2. Convierte el mensaje a binario cuando es necesario.
3. Aplica Hamming o Fletcher.
4. Genera una trama con la información y los bits adicionales.
5. La trama se copia y se ingresa en el receptor.
6. El receptor verifica si existen errores.
7. Hamming intenta corregir el error y Fletcher indica si la trama fue modificada.

## Lenguajes utilizados

- Emisor: Python
- Receptor: Java
