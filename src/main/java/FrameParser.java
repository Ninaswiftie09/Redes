import java.util.Locale;

/** Separa y valida el contrato de cinco campos del emisor. */
final class FrameParser {
    private FrameParser() { }

    static ReceivedFrame parse(String input) throws InputFormatException {
        if (input == null || input.trim().isEmpty()) {
            throw new InputFormatException("La línea de entrada no puede estar vacía.");
        }
        String[] parts = input.split("\\|", -1);
        if (parts.length != 5) {
            throw new InputFormatException("La entrada debe contener exactamente cinco campos separados por '|'.");
        }
        String algorithm = parts[0].trim().toUpperCase(Locale.ROOT);
        FletcherVariant variant = FletcherVariant.fromAlgorithm(algorithm);
        if (!"HAMMING".equals(algorithm) && variant == null) {
            throw new InputFormatException("Algoritmo no soportado: " + parts[0] + ".");
        }
        String frame = parts[1];
        if (frame.isEmpty()) {
            throw new InputFormatException("La trama no puede estar vacía.");
        }
        if (!frame.matches("[01]+")) {
            throw new InputFormatException("La trama solo puede contener los bits 0 y 1.");
        }
        int originalLength = parseNonNegativeInteger(parts[2], "LONGITUD_ORIGINAL");
        int padding = parseNonNegativeInteger(parts[3], "PADDING");
        String type = parts[4].trim().toUpperCase(Locale.ROOT);
        if (!"BINARIO".equals(type) && !"ASCII".equals(type)) {
            throw new InputFormatException("TIPO debe ser BINARIO o ASCII.");
        }
        if ("ASCII".equals(type) && originalLength % 8 != 0) {
            throw new InputFormatException("Para ASCII, LONGITUD_ORIGINAL debe ser múltiplo de 8.");
        }
        if ("HAMMING".equals(algorithm)) {
            validateHamming(frame, originalLength, padding);
            return new ReceivedFrame(algorithm, null, frame, originalLength, padding, type);
        }
        validateFletcher(frame, originalLength, padding, variant);
        return new ReceivedFrame(algorithm, variant, frame, originalLength, padding, type);
    }

    private static void validateFletcher(String frame, int originalLength, int padding,
            FletcherVariant variant) throws InputFormatException {
        if (frame.length() < variant.getChecksumBits()) {
            throw new InputFormatException("La trama es más corta que el checksum de " + variant.getChecksumBits() + " bits.");
        }
        int dataLength = frame.length() - variant.getChecksumBits();
        if (dataLength == 0) {
            throw new InputFormatException("Los datos con padding no pueden estar vacíos.");
        }
        if (dataLength % variant.getWordBits() != 0) {
            throw new InputFormatException("Los datos con padding deben tener una longitud múltiplo de " + variant.getWordBits() + ".");
        }
        if (padding > dataLength) {
            throw new InputFormatException("PADDING no puede ser mayor que la longitud de los datos.");
        }
        if ((long) originalLength + padding != dataLength) {
            throw new InputFormatException("LONGITUD_ORIGINAL + PADDING no coincide con los datos con padding.");
        }
    }

    private static void validateHamming(String frame, int originalLength, int padding)
            throws InputFormatException {
        if (padding != 0) {
            throw new InputFormatException("Para HAMMING, PADDING debe ser 0.");
        }
        int informationBits = 0;
        for (int position = 1; position <= frame.length(); position++) {
            if (!HammingVerifier.isPowerOfTwo(position)) {
                informationBits++;
            }
        }
        if (informationBits < originalLength) {
            throw new InputFormatException("La trama Hamming no contiene suficientes bits de información.");
        }
    }

    private static int parseNonNegativeInteger(String value, String field) throws InputFormatException {
        try {
            int parsed = Integer.parseInt(value.trim());
            if (parsed < 0) {
                throw new InputFormatException(field + " debe ser un entero no negativo.");
            }
            return parsed;
        } catch (NumberFormatException exception) {
            throw new InputFormatException(field + " debe ser un entero no negativo.");
        }
    }
}

final class InputFormatException extends Exception {
    InputFormatException(String message) { super(message); }
}
