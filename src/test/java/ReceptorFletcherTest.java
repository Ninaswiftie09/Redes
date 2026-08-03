/** Pruebas ejecutables sin dependencias para el receptor Fletcher. */
public final class ReceptorFletcherTest {
    private static int assertions;

    private ReceptorFletcherTest() { }

    public static void main(String[] args) {
        validFletcher8WithPadding();
        validFletcher16Ascii();
        invalidFletcher16Checksum();
        validFletcher32WithPadding();
        suppliedFletcherCases();
        malformedInputs();
        hammingRequiredCases();
        hammingCasesFromProvidedSet();
        malformedHammingInputs();
        alteredDataAndChecksum();
        leadingZerosArePreserved();
        System.out.println("Pruebas completadas: " + assertions + " verificaciones correctas.");
    }

    private static void validFletcher8WithPadding() {
        ProcessingResult result = ReceptorFletcher.process("FLETCHER8|101010101010|3|1|BINARIO");
        assertTrue(result.isValid(), "Fletcher-8 válido");
        assertEquals("101", result.getBinaryMessage(), "Recuperación Fletcher-8");
    }

    private static void validFletcher16Ascii() {
        ProcessingResult result = ReceptorFletcher.process("FLETCHER16|010000010100000101000001|8|0|ASCII");
        assertTrue(result.isValid(), "Fletcher-16 válido");
        assertEquals("01000001", result.getBinaryMessage(), "Bits ASCII A");
        assertEquals("A", result.getAsciiMessage(), "ASCII A");
    }

    private static void invalidFletcher16Checksum() {
        ProcessingResult result = ReceptorFletcher.process("FLETCHER16|010000010100000100000010|8|0|ASCII");
        assertFalse(result.isValid(), "Checksum Fletcher-16 alterado");
        assertFalse(result.isMalformed(), "Error de transmisión no es formato");
        assertEquals(null, result.getBinaryMessage(), "No se recupera ASCII inválido");
    }

    private static void validFletcher32WithPadding() {
        ProcessingResult result = ReceptorFletcher.process(
                "FLETCHER32|010000010000000001000001000000000100000100000000|8|8|ASCII");
        assertTrue(result.isValid(), "Fletcher-32 válido");
        assertEquals("01000001", result.getBinaryMessage(), "Padding Fletcher-32");
        assertEquals("A", result.getAsciiMessage(), "ASCII Fletcher-32");
    }

    private static void suppliedFletcherCases() {
        assertValidBinary("FLETCHER16|101100001011000010110000|4|4|BINARIO", "1011", "Prueba 4");
        assertValidBinary("FLETCHER16|110101101101011011010110|8|0|BINARIO", "11010110", "Prueba 5");
        ProcessingResult hola = ReceptorFletcher.process(
                "FLETCHER16|010010000110111101101100011000011010100110000101|32|0|ASCII");
        assertTrue(hola.isValid(), "Prueba 6 válida");
        assertEquals("Hola", hola.getAsciiMessage(), "Prueba 6 recupera Hola");

        assertTransmissionError("FLETCHER16|001100001011000010110000|4|4|BINARIO", "Prueba 10");
        assertTransmissionError("FLETCHER16|010101101101011011010110|8|0|BINARIO", "Prueba 11");
        assertTransmissionError(
                "FLETCHER16|110010000110111101101100011000011010100110000101|32|0|ASCII", "Prueba 12");
        assertTransmissionError("FLETCHER16|011100001011000010110000|4|4|BINARIO", "Prueba 16");
        assertTransmissionError("FLETCHER16|000101101101011011010110|8|0|BINARIO", "Prueba 17");
        assertTransmissionError(
                "FLETCHER16|100010000110111101101100011000011010100110000101|32|0|ASCII", "Prueba 18");
    }

    private static void malformedInputs() {
        assertMalformed("FLETCHER8|101010101010|3|1", "Menos de cinco campos");
        assertMalformed("FLETCHER8|101010101010|3|1|BINARIO|EXTRA", "Más de cinco campos");
        assertMalformed("OTRO|101010101010|3|1|BINARIO", "Algoritmo desconocido");
        assertMalformed("FLETCHER8|101010101010|3|1|TEXTO", "Tipo desconocido");
        assertMalformed("FLETCHER8|101A10101010|3|1|BINARIO", "Bit inválido");
        assertMalformed("FLETCHER16|01010101|0|0|BINARIO", "Trama corta");
        assertMalformed("FLETCHER16|10101010101010101|1|0|BINARIO", "Datos fuera de palabra");
        assertMalformed("FLETCHER8|101010101010|-1|1|BINARIO", "Longitud negativa");
        assertMalformed("FLETCHER8|101010101010|3|-1|BINARIO", "Padding negativo");
        assertMalformed("FLETCHER8|101010101010|0|5|BINARIO", "Padding mayor que datos");
        assertMalformed("FLETCHER8|101010101010|2|1|BINARIO", "Metadatos inconsistentes");
        assertMalformed("FLETCHER8|101010101010|3|1|ASCII", "ASCII no múltiplo de ocho");
    }

    private static void hammingRequiredCases() {
        ProcessingResult valid = ReceptorFletcher.process("HAMMING|0110011|4|0|BINARIO");
        assertEquals(ProcessingStatus.VALID, valid.getStatus(), "Hamming binario válido");
        assertEquals(0, valid.getVerification().getSyndrome(), "Síndrome Hamming válido");
        assertEquals("1011", valid.getBinaryMessage(), "Datos Hamming válidos");

        ProcessingResult errorAtFive = ReceptorFletcher.process("HAMMING|0110111|4|0|BINARIO");
        assertEquals(ProcessingStatus.CORRECTED, errorAtFive.getStatus(), "Hamming corrige posición 5");
        assertEquals(5, errorAtFive.getVerification().getSyndrome(), "Síndrome 5");
        assertEquals("0110011", errorAtFive.getVerification().getCorrectedFrame(), "Trama corregida posición 5");
        assertEquals("1011", errorAtFive.getBinaryMessage(), "Datos tras corrección posición 5");

        ProcessingResult parityError = ReceptorFletcher.process("HAMMING|1110011|4|0|BINARIO");
        assertEquals(ProcessingStatus.CORRECTED, parityError.getStatus(), "Hamming corrige paridad");
        assertEquals(1, parityError.getVerification().getSyndrome(), "Síndrome 1");
        assertEquals("0110011", parityError.getVerification().getCorrectedFrame(), "Paridad corregida");

        ProcessingResult ascii = ReceptorFletcher.process("HAMMING|100010010001|8|0|ASCII");
        assertEquals(ProcessingStatus.VALID, ascii.getStatus(), "Hamming ASCII válido");
        assertEquals("01000001", ascii.getBinaryMessage(), "Bits Hamming ASCII");
        assertEquals("A", ascii.getAsciiMessage(), "ASCII Hamming A");

        ProcessingResult asciiError = ReceptorFletcher.process("HAMMING|100010010101|8|0|ASCII");
        assertEquals(ProcessingStatus.CORRECTED, asciiError.getStatus(), "Hamming corrige posición 10");
        assertEquals(10, asciiError.getVerification().getSyndrome(), "Síndrome 10");
        assertEquals("100010010001", asciiError.getVerification().getCorrectedFrame(), "ASCII corregido");
        assertEquals("A", asciiError.getAsciiMessage(), "ASCII tras corrección");
    }

    private static void hammingCasesFromProvidedSet() {
        String[] oneErrorOrClean = {
            "HAMMING|0110011|4|0|BINARIO", "HAMMING|001010100110|8|0|BINARIO",
            "HAMMING|11001001100001110111101101100010100001|32|0|ASCII",
            "HAMMING|0111011|4|0|BINARIO", "HAMMING|001110100110|8|0|BINARIO",
            "HAMMING|11011001100001110111101101100010100001|32|0|ASCII"
        };
        for (String input : oneErrorOrClean) {
            assertTrue(ReceptorFletcher.process(input).isUsable(), "Caso Hamming recibido utilizable");
        }

        ProcessingResult multipleErrors = ReceptorFletcher.process("HAMMING|0100111|4|0|BINARIO");
        assertFalse(multipleErrors.isMalformed(), "Dos errores Hamming no provocan excepción");
        // Sin paridad global, una trama con dos errores puede producir un síndrome engañoso.
    }

    private static void malformedHammingInputs() {
        assertMalformed("HAMMING||0|0|BINARIO", "Trama Hamming vacía");
        assertMalformed("HAMMING|010A011|4|0|BINARIO", "Carácter Hamming inválido");
        assertMalformed("HAMMING|0110011|-1|0|BINARIO", "Longitud Hamming negativa");
        assertMalformed("HAMMING|0110011|4|1|BINARIO", "Padding Hamming distinto de cero");
        assertMalformed("HAMMING|0110011|5|0|BINARIO", "Información Hamming insuficiente");
        assertMalformed("HAMMING|0110011|4|0|TEXTO", "Tipo Hamming desconocido");
        assertMalformed("HAMMING|0110011|4|0|ASCII", "ASCII Hamming no múltiplo de ocho");
        assertMalformed("HAMMING|0110011|4|0|BINARIO|EXTRA", "Campo Hamming adicional");
        ProcessingResult outOfBounds = ReceptorFletcher.process("HAMMING|01010|0|0|BINARIO");
        assertEquals(ProcessingStatus.UNCORRECTABLE, outOfBounds.getStatus(), "Síndrome Hamming fuera de límites");
    }

    private static void alteredDataAndChecksum() {
        ProcessingResult dataError = ReceptorFletcher.process("FLETCHER16|110000010100000101000001|8|0|ASCII");
        assertFalse(dataError.isValid(), "Bit alterado en datos");
        ProcessingResult checksumError = ReceptorFletcher.process("FLETCHER16|010000010100000101000000|8|0|ASCII");
        assertFalse(checksumError.isValid(), "Bit alterado en checksum");
    }

    private static void leadingZerosArePreserved() {
        ProcessingResult result = ReceptorFletcher.process("FLETCHER8|000100010001|4|0|BINARIO");
        assertTrue(result.isValid(), "Trama con ceros iniciales válida");
        assertEquals("0001", result.getBinaryMessage(), "Ceros iniciales preservados");
    }

    private static void assertMalformed(String input, String description) {
        assertTrue(ReceptorFletcher.process(input).isMalformed(), description);
    }

    private static void assertValidBinary(String input, String expectedMessage, String description) {
        ProcessingResult result = ReceptorFletcher.process(input);
        assertTrue(result.isValid(), description + " válida");
        assertEquals(expectedMessage, result.getBinaryMessage(), description + " recupera el mensaje");
    }

    private static void assertTransmissionError(String input, String description) {
        ProcessingResult result = ReceptorFletcher.process(input);
        assertFalse(result.isValid(), description + " detecta error");
        assertFalse(result.isMalformed(), description + " es una trama, no un formato inválido");
        assertEquals(null, result.getBinaryMessage(), description + " no recupera mensaje");
    }

    private static void assertTrue(boolean condition, String description) {
        assertions++;
        if (!condition) {
            throw new AssertionError("Falló: " + description);
        }
    }

    private static void assertFalse(boolean condition, String description) { assertTrue(!condition, description); }

    private static void assertEquals(Object expected, Object actual, String description) {
        assertTrue(expected == null ? actual == null : expected.equals(actual), description);
    }
}
