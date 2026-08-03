/** Datos ya validados de una línea recibida del emisor. */
final class ReceivedFrame {
    private final String algorithm;
    private final FletcherVariant variant;
    private final String frame;
    private final int originalLength;
    private final int padding;
    private final String type;

    ReceivedFrame(String algorithm, FletcherVariant variant, String frame, int originalLength,
            int padding, String type) {
        this.algorithm = algorithm;
        this.variant = variant;
        this.frame = frame;
        this.originalLength = originalLength;
        this.padding = padding;
        this.type = type;
    }

    String getAlgorithm() { return algorithm; }
    boolean isHamming() { return "HAMMING".equals(algorithm); }
    FletcherVariant getVariant() { return variant; }
    String getFrame() { return frame; }
    int getOriginalLength() { return originalLength; }
    int getPadding() { return padding; }
    String getType() { return type; }
}
