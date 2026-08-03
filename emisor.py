import random


def es_binario(valor):
    return bool(valor) and all(bit in "01" for bit in valor)


def solicitar_opcion(mensaje, opciones_validas):
    while True:
        opcion = input(mensaje).strip()

        if opcion in opciones_validas:
            return opcion

        print("Opción inválida. Intente nuevamente.")


def solicitar_mensaje():
    print("\nTipo de mensaje:")
    print("1. Cadena binaria")
    print("2. Texto ASCII")

    opcion = solicitar_opcion(
        "Seleccione una opción: ",
        {"1", "2"}
    )

    if opcion == "1":
        while True:
            mensaje = input("Ingrese el mensaje binario: ").strip()

            if es_binario(mensaje):
                return mensaje, "BINARIO", mensaje

            print("El mensaje solo puede contener 0 y 1.")

    while True:
        texto = input("Ingrese el texto ASCII: ")

        if not texto:
            print("El mensaje no puede estar vacío.")
            continue

        try:
            datos_ascii = texto.encode("ascii")
        except UnicodeEncodeError:
            print(
                "Use caracteres ASCII sin tildes "
                "ni símbolos especiales."
            )
            continue

        mensaje_binario = "".join(
            f"{byte:08b}" for byte in datos_ascii
        )

        return mensaje_binario, "ASCII", texto


# ---------------------------------------------------------
# CÓDIGO DE HAMMING
# ---------------------------------------------------------

def calcular_bits_paridad(cantidad_datos):
    cantidad_paridad = 0

    while (
        2 ** cantidad_paridad
        < cantidad_datos + cantidad_paridad + 1
    ):
        cantidad_paridad += 1

    return cantidad_paridad


def codificar_hamming(datos):
    """
    Código de Hamming con paridad par.

    Convenciones:
    - Las posiciones se cuentan desde 1.
    - La posición 1 está al lado izquierdo.
    - Los bits de paridad están en 1, 2, 4, 8, 16...
    - Se utiliza paridad par.
    """

    cantidad_paridad = calcular_bits_paridad(len(datos))
    longitud_total = len(datos) + cantidad_paridad

    # Se deja vacía la posición 0 para trabajar desde la 1.
    trama = ["0"] * (longitud_total + 1)

    indice_dato = 0

    # Colocar los bits de información.
    for posicion in range(1, longitud_total + 1):
        es_posicion_paridad = (
            posicion & (posicion - 1)
        ) == 0

        if not es_posicion_paridad:
            trama[posicion] = datos[indice_dato]
            indice_dato += 1

    # Calcular los bits de paridad.
    for exponente in range(cantidad_paridad):
        posicion_paridad = 2 ** exponente
        valor_paridad = 0

        for posicion in range(1, longitud_total + 1):
            pertenece_al_grupo = (
                posicion & posicion_paridad
            ) != 0

            if (
                pertenece_al_grupo
                and posicion != posicion_paridad
            ):
                valor_paridad ^= int(trama[posicion])

        trama[posicion_paridad] = str(valor_paridad)

    trama_final = "".join(trama[1:])

    return trama_final, cantidad_paridad


# ---------------------------------------------------------
# FLETCHER CHECKSUM
# ---------------------------------------------------------

def codificar_fletcher(datos, variante):
    """
    Fletcher-8, Fletcher-16 o Fletcher-32.

    Convención acordada:
    - Fletcher-N procesa palabras de N/2 bits.
    - Fletcher-8 utiliza palabras de 4 bits.
    - Fletcher-16 utiliza palabras de 8 bits.
    - Fletcher-32 utiliza palabras de 16 bits.
    - El padding se agrega al lado derecho.
    - El checksum se concatena como SUM2 seguido de SUM1.
    """

    bits_por_palabra = variante // 2
    modulo = (1 << bits_por_palabra) - 1

    cantidad_padding = (
        -len(datos)
    ) % bits_por_palabra

    datos_con_padding = (
        datos + ("0" * cantidad_padding)
    )

    suma1 = 0
    suma2 = 0

    for inicio in range(
        0,
        len(datos_con_padding),
        bits_por_palabra
    ):
        palabra = datos_con_padding[
            inicio:inicio + bits_por_palabra
        ]

        valor_palabra = int(palabra, 2)

        suma1 = (
            suma1 + valor_palabra
        ) % modulo

        suma2 = (
            suma2 + suma1
        ) % modulo

    suma2_binaria = format(
        suma2,
        f"0{bits_por_palabra}b"
    )

    suma1_binaria = format(
        suma1,
        f"0{bits_por_palabra}b"
    )

    checksum = suma2_binaria + suma1_binaria

    trama_final = datos_con_padding + checksum

    return trama_final, cantidad_padding, checksum


# ---------------------------------------------------------
# RUIDO
# ---------------------------------------------------------

def solicitar_probabilidad_error():
    while True:
        valor = input(
            "Ingrese la probabilidad de error entre 0 y 1 "
            "(por ejemplo, 0.01): "
        ).strip()

        try:
            probabilidad = float(valor)
        except ValueError:
            print("Ingrese un número válido.")
            continue

        if 0 <= probabilidad <= 1:
            return probabilidad

        print(
            "La probabilidad debe estar entre 0 y 1."
        )


def aplicar_ruido(trama, probabilidad):
    """
    Cada bit puede invertirse según la probabilidad indicada.

    Las posiciones comienzan en 1 y se cuentan
    desde el lado izquierdo.
    """

    trama_con_ruido = []
    posiciones_modificadas = []

    for posicion, bit in enumerate(trama, start=1):
        debe_cambiar = (
            random.random() < probabilidad
        )

        if debe_cambiar:
            nuevo_bit = "1" if bit == "0" else "0"

            trama_con_ruido.append(nuevo_bit)
            posiciones_modificadas.append(posicion)
        else:
            trama_con_ruido.append(bit)

    return (
        "".join(trama_con_ruido),
        posiciones_modificadas
    )


# ---------------------------------------------------------
# SELECCIÓN DEL ALGORITMO
# ---------------------------------------------------------

def seleccionar_algoritmo(datos):
    print("\nAlgoritmo:")
    print("1. Hamming, corrección de un error")
    print("2. Fletcher checksum, detección de errores")

    opcion = solicitar_opcion(
        "Seleccione una opción: ",
        {"1", "2"}
    )

    if opcion == "1":
        trama, cantidad_paridad = codificar_hamming(
            datos
        )

        print(
            "\nBits de paridad agregados:",
            cantidad_paridad
        )

        return (
            "HAMMING",
            trama,
            0,
            "NO_APLICA"
        )

    print("\nVariante de Fletcher:")
    print("1. Fletcher-8")
    print("2. Fletcher-16")
    print("3. Fletcher-32")

    variante_opcion = solicitar_opcion(
        "Seleccione una opción: ",
        {"1", "2", "3"}
    )

    variantes = {
        "1": 8,
        "2": 16,
        "3": 32
    }

    variante = variantes[variante_opcion]

    trama, padding, checksum = codificar_fletcher(
        datos,
        variante
    )

    return (
        f"FLETCHER{variante}",
        trama,
        padding,
        checksum
    )


# ---------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------

def main():
    print("=" * 60)
    print("EMISOR - DETECCIÓN Y CORRECCIÓN DE ERRORES")
    print("=" * 60)

    datos, tipo_mensaje, mensaje_original = (
        solicitar_mensaje()
    )

    (
        algoritmo,
        trama_limpia,
        padding,
        checksum
    ) = seleccionar_algoritmo(datos)

    print("\nAplicación de ruido:")
    print(
        "1. No aplicar ruido y modificar "
        "los bits manualmente"
    )
    print(
        "2. Aplicar ruido automáticamente "
        "según una probabilidad"
    )

    opcion_ruido = solicitar_opcion(
        "Seleccione una opción: ",
        {"1", "2"}
    )

    if opcion_ruido == "2":
        probabilidad = solicitar_probabilidad_error()

        (
            trama_enviada,
            posiciones_modificadas
        ) = aplicar_ruido(
            trama_limpia,
            probabilidad
        )

    else:
        probabilidad = 0.0
        trama_enviada = trama_limpia
        posiciones_modificadas = []

    # Formato acordado con el receptor:
    #
    # ALGORITMO|TRAMA|LONGITUD_ORIGINAL|PADDING|TIPO
    #
    # Ejemplo:
    # HAMMING|0110011|4|0|BINARIO

    salida_receptor = (
        f"{algoritmo}|"
        f"{trama_enviada}|"
        f"{len(datos)}|"
        f"{padding}|"
        f"{tipo_mensaje}"
    )

    print("\n" + "=" * 60)
    print("RESULTADO DEL EMISOR")
    print("=" * 60)

    print(f"Mensaje original: {mensaje_original}")
    print(f"Datos binarios originales: {datos}")
    print(f"Tipo de mensaje: {tipo_mensaje}")
    print(f"Algoritmo: {algoritmo}")

    print(
        f"Longitud original en bits: {len(datos)}"
    )

    print(f"Padding agregado: {padding}")

    if algoritmo.startswith("FLETCHER"):
        print(f"Checksum: {checksum}")

    print(
        f"Trama antes del ruido: {trama_limpia}"
    )

    print(
        f"Probabilidad utilizada: {probabilidad}"
    )

    print(
        f"Trama que se enviará: {trama_enviada}"
    )

    if posiciones_modificadas:
        posiciones_texto = ", ".join(
            map(str, posiciones_modificadas)
        )

        print(
            "Bits modificados desde la izquierda: "
            + posiciones_texto
        )
    else:
        print(
            "Bits modificados por el ruido: ninguno"
        )

    print("\nCOPIAR Y ENVIAR AL RECEPTOR:")
    print(salida_receptor)

    print("=" * 60)


if __name__ == "__main__":
    main()