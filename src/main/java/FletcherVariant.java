/** Configuración inmutable de las variantes admitidas de Fletcher. */
enum FletcherVariant {
    FLETCHER8("FLETCHER8", 4, 8, 15),
    FLETCHER16("FLETCHER16", 8, 16, 255),
    FLETCHER32("FLETCHER32", 16, 32, 65535);

    private final String algorithm;
    private final int wordBits;
    private final int checksumBits;
    private final long modulo;

    FletcherVariant(String algorithm, int wordBits, int checksumBits, long modulo) {
        this.algorithm = algorithm;
        this.wordBits = wordBits;
        this.checksumBits = checksumBits;
        this.modulo = modulo;
    }

    static FletcherVariant fromAlgorithm(String algorithm) {
        for (FletcherVariant variant : values()) {
            if (variant.algorithm.equals(algorithm)) {
                return variant;
            }
        }
        return null;
    }

    String getAlgorithm() { return algorithm; }
    int getWordBits() { return wordBits; }
    int getChecksumBits() { return checksumBits; }
    long getModulo() { return modulo; }
}
