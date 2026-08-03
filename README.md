# Laboratorio 2: receptor de control de errores

## Integrantes

- Nina Nájera Marakovits - 231088
- Diego Ramirez - 23601

El repositorio contiene el emisor en Python y un receptor de consola en Java. El
receptor procesa una única línea y selecciona el algoritmo indicado por esa línea.
No modifica el emisor.

## Algoritmos admitidos

- `HAMMING`: usa paridad par y posiciones contadas desde la izquierda. Corrige un
  solo error de bit y después extrae los bits de información.
- `FLETCHER8`, `FLETCHER16` y `FLETCHER32`: verifican el checksum como `SUMA2`
  seguida de `SUMA1`. Detectan errores, pero no los corrigen; si el checksum no
  coincide, descartan la trama.

Hamming no usa paridad global. Por ello, frente a dos o más alteraciones puede
obtener un síndrome engañoso y no garantiza una detección o corrección confiable.

## Formato de entrada

```text
ALGORITMO|TRAMA|LONGITUD_ORIGINAL|PADDING|TIPO
```

- `ALGORITMO`: `HAMMING`, `FLETCHER8`, `FLETCHER16` o `FLETCHER32`.
- `TRAMA`: bits recibidos; se conserva como texto para mantener ceros iniciales.
- `LONGITUD_ORIGINAL`: longitud del mensaje sin paridad ni padding.
- `PADDING`: para Fletcher son ceros agregados a la derecha antes del checksum;
  para Hamming debe ser `0`.
- `TIPO`: `BINARIO` o `ASCII`.

En pruebas manuales, altere solamente un bit del campo `TRAMA`. No cambie el
algoritmo, la longitud original, el padding ni el tipo.

## Requisitos y compilación

Se requiere Java 8 o superior. No se usan Maven, Gradle ni dependencias externas.

Desde la raíz del repositorio, en PowerShell:

```powershell
$mainSources = Get-ChildItem src/main/java -Filter *.java | ForEach-Object FullName
javac -encoding UTF-8 -d out $mainSources
```

## Ejecución

El receptor lee una línea de la entrada estándar:

```powershell
"HAMMING|0110111|4|0|BINARIO" | java -cp out ReceptorFletcher
```

El ejemplo anterior informa síndrome `5`, corrige la trama a `0110011` y recupera
`1011`.

Ejemplo Fletcher válido:

```powershell
"FLETCHER16|010000010100000101000001|8|0|ASCII" | java -cp out ReceptorFletcher
```

Ejemplo Fletcher con error, que será descartado sin corrección:

```powershell
"FLETCHER16|010000010100000100000010|8|0|ASCII" | java -cp out ReceptorFletcher
```

## Pruebas

Compile producción y pruebas, y ejecute la clase de pruebas:

```powershell
$mainSources = Get-ChildItem src/main/java -Filter *.java | ForEach-Object FullName
$testSources = Get-ChildItem src/test/java -Filter *.java | ForEach-Object FullName
javac -encoding UTF-8 -d out $mainSources $testSources
java -cp out ReceptorFletcherTest
```

La suite cubre Hamming válido, corrección de un bit, ASCII, entradas inválidas,
síndrome fuera de rango y la limitación ante múltiples errores; también mantiene
las regresiones de Fletcher-8, Fletcher-16 y Fletcher-32.
