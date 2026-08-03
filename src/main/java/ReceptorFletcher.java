import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

/** Punto de entrada del receptor de Hamming y Fletcher por consola. */
public final class ReceptorFletcher {
    private ReceptorFletcher() { }

    public static void main(String[] args) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            print(process(reader.readLine()));
        } catch (IOException exception) {
            System.out.println("Estado: ENTRADA MAL FORMADA");
            System.out.println("Error: No fue posible leer la entrada.");
        }
    }

    static ProcessingResult process(String input) {
        try {
            ReceivedFrame received = FrameParser.parse(input);
            ErrorControlVerifier verifier = received.isHamming()
                    ? new HammingVerifier() : new FletcherVerifier();
            VerificationResult verification = verifier.verify(received);
            if (!verification.isUsable()) {
                return ProcessingResult.notUsable(received, verification);
            }
            String binaryMessage = MessageRecovery.recoverBinary(received, verification);
            String asciiMessage = "ASCII".equals(received.getType())
                    ? MessageRecovery.decodeAscii(binaryMessage) : null;
            return ProcessingResult.usable(received, verification, binaryMessage, asciiMessage);
        } catch (InputFormatException exception) {
            return ProcessingResult.malformed(exception.getMessage());
        }
    }

    private static void print(ProcessingResult result) {
        if (result.isMalformed()) {
            System.out.println("Estado: ENTRADA MAL FORMADA");
            System.out.println("Error: " + result.getErrorMessage());
            return;
        }
        ReceivedFrame received = result.getReceived();
        VerificationResult verification = result.getVerification();
        System.out.println("Algoritmo recibido: " + received.getAlgorithm());
        System.out.println("Trama recibida: " + received.getFrame());
        System.out.println("Longitud original: " + received.getOriginalLength());
        System.out.println("Padding: " + received.getPadding());
        System.out.println("Tipo: " + received.getType());
        if (received.isHamming()) {
            printHammingResult(result, verification);
        } else {
            printFletcherResult(result, verification);
        }
    }

    private static void printHammingResult(ProcessingResult result, VerificationResult verification) {
        boolean detected = result.getStatus() != ProcessingStatus.VALID;
        System.out.println("¿Se detectaron errores?: " + (detected ? "Sí" : "No"));
        System.out.println("Síndrome: " + verification.getSyndrome());
        System.out.println("Posición del error: " + (verification.getErrorPosition() < 0
                ? "No aplica" : verification.getErrorPosition()));
        System.out.println("Trama corregida: " + (verification.getCorrectedFrame() == null
                ? "No aplica" : verification.getCorrectedFrame()));
        if (result.getStatus() == ProcessingStatus.VALID) {
            System.out.println("Estado: TRAMA VÁLIDA");
            System.out.println("Mensaje binario recuperado: " + result.getBinaryMessage());
        } else if (result.getStatus() == ProcessingStatus.CORRECTED) {
            System.out.println("Estado: ERROR CORREGIDO");
            System.out.println("Mensaje binario recuperado: " + result.getBinaryMessage());
        } else {
            System.out.println("Estado: ERROR NO CORREGIBLE");
            System.out.println("Mensaje binario recuperado: No disponible");
        }
        if (result.getAsciiMessage() != null) {
            System.out.println("Mensaje ASCII recuperado: " + result.getAsciiMessage());
        }
    }

    private static void printFletcherResult(ProcessingResult result, VerificationResult verification) {
        System.out.println("Checksum recibido: " + verification.getReceivedChecksum());
        System.out.println("Checksum calculado: " + verification.getCalculatedChecksum());
        System.out.println("¿Se detectaron errores?: " + (result.isValid() ? "No" : "Sí"));
        System.out.println("Posición del error: No aplica");
        System.out.println("Trama corregida: No aplica");
        if (result.isValid()) {
            System.out.println("Estado: TRAMA VÁLIDA");
            System.out.println("Mensaje binario recuperado: " + result.getBinaryMessage());
            if (result.getAsciiMessage() != null) {
                System.out.println("Mensaje ASCII recuperado: " + result.getAsciiMessage());
            }
        } else {
            System.out.println("Estado: ERROR DETECTADO");
            System.out.println("Mensaje binario recuperado: No disponible");
            System.out.println("Acción: trama descartada; Fletcher detecta errores, pero no los corrige.");
        }
    }
}

final class ProcessingResult {
    private final ReceivedFrame received;
    private final VerificationResult verification;
    private final ProcessingStatus status;
    private final String binaryMessage;
    private final String asciiMessage;
    private final String errorMessage;

    private ProcessingResult(ReceivedFrame received, VerificationResult verification,
            ProcessingStatus status, String binaryMessage, String asciiMessage, String errorMessage) {
        this.received = received;
        this.verification = verification;
        this.status = status;
        this.binaryMessage = binaryMessage;
        this.asciiMessage = asciiMessage;
        this.errorMessage = errorMessage;
    }

    static ProcessingResult usable(ReceivedFrame received, VerificationResult verification,
            String binaryMessage, String asciiMessage) {
        return new ProcessingResult(received, verification, verification.getStatus(),
                binaryMessage, asciiMessage, null);
    }

    static ProcessingResult notUsable(ReceivedFrame received, VerificationResult verification) {
        return new ProcessingResult(received, verification, verification.getStatus(), null, null, null);
    }

    static ProcessingResult malformed(String errorMessage) {
        return new ProcessingResult(null, null, ProcessingStatus.INVALID_INPUT, null, null, errorMessage);
    }

    ReceivedFrame getReceived() { return received; }
    VerificationResult getVerification() { return verification; }
    ProcessingStatus getStatus() { return status; }
    boolean isValid() { return status == ProcessingStatus.VALID; }
    boolean isUsable() { return status == ProcessingStatus.VALID || status == ProcessingStatus.CORRECTED; }
    boolean isMalformed() { return status == ProcessingStatus.INVALID_INPUT; }
    String getBinaryMessage() { return binaryMessage; }
    String getAsciiMessage() { return asciiMessage; }
    String getErrorMessage() { return errorMessage; }
}
