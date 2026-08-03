/** Contrato común para los algoritmos de control de errores. */
interface ErrorControlVerifier {
    VerificationResult verify(ReceivedFrame received);
}

/** Calcula y compara Fletcher sin alterar los datos recibidos. */
final class FletcherVerifier implements ErrorControlVerifier {
    @Override
    public VerificationResult verify(ReceivedFrame received) {
        FletcherVariant variant = received.getVariant();
        String frame = received.getFrame();
        int checksumStart = frame.length() - variant.getChecksumBits();
        String dataWithPadding = frame.substring(0, checksumStart);
        String receivedChecksum = frame.substring(checksumStart);
        String calculatedChecksum = calculateChecksum(dataWithPadding, variant);
        return VerificationResult.fletcher(dataWithPadding, receivedChecksum, calculatedChecksum,
                receivedChecksum.equals(calculatedChecksum));
    }

    String calculateChecksum(String dataWithPadding, FletcherVariant variant) {
        long sum1 = 0;
        long sum2 = 0;
        for (int start = 0; start < dataWithPadding.length(); start += variant.getWordBits()) {
            String word = dataWithPadding.substring(start, start + variant.getWordBits());
            long value = Long.parseLong(word, 2);
            sum1 = (sum1 + value) % variant.getModulo();
            sum2 = (sum2 + sum1) % variant.getModulo();
        }
        return toFixedWidthBinary(sum2, variant.getWordBits())
                + toFixedWidthBinary(sum1, variant.getWordBits());
    }

    static String toFixedWidthBinary(long value, int width) {
        String binary = Long.toBinaryString(value);
        StringBuilder result = new StringBuilder(width);
        for (int index = binary.length(); index < width; index++) {
            result.append('0');
        }
        return result.append(binary).toString();
    }
}

final class VerificationResult {
    private final String recoverableFrame;
    private final String receivedChecksum;
    private final String calculatedChecksum;
    private final ProcessingStatus status;
    private final int syndrome;
    private final int errorPosition;
    private final String correctedFrame;

    private VerificationResult(String recoverableFrame, String receivedChecksum,
            String calculatedChecksum, ProcessingStatus status, int syndrome,
            int errorPosition, String correctedFrame) {
        this.recoverableFrame = recoverableFrame;
        this.receivedChecksum = receivedChecksum;
        this.calculatedChecksum = calculatedChecksum;
        this.status = status;
        this.syndrome = syndrome;
        this.errorPosition = errorPosition;
        this.correctedFrame = correctedFrame;
    }

    static VerificationResult fletcher(String dataWithPadding, String receivedChecksum,
            String calculatedChecksum, boolean valid) {
        return new VerificationResult(dataWithPadding, receivedChecksum, calculatedChecksum,
                valid ? ProcessingStatus.VALID : ProcessingStatus.DETECTED_ERROR, -1, -1, null);
    }

    static VerificationResult hamming(String recoverableFrame, ProcessingStatus status,
            int syndrome, int errorPosition, String correctedFrame) {
        return new VerificationResult(recoverableFrame, null, null, status, syndrome,
                errorPosition, correctedFrame);
    }

    String getRecoverableFrame() { return recoverableFrame; }
    String getDataWithPadding() { return recoverableFrame; }
    String getReceivedChecksum() { return receivedChecksum; }
    String getCalculatedChecksum() { return calculatedChecksum; }
    ProcessingStatus getStatus() { return status; }
    int getSyndrome() { return syndrome; }
    int getErrorPosition() { return errorPosition; }
    String getCorrectedFrame() { return correctedFrame; }
    boolean isUsable() { return status == ProcessingStatus.VALID || status == ProcessingStatus.CORRECTED; }
}

enum ProcessingStatus {
    VALID,
    CORRECTED,
    DETECTED_ERROR,
    UNCORRECTABLE,
    INVALID_INPUT
}
