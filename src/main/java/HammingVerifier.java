/** Verifica Hamming con paridad par y posiciones contadas desde la izquierda. */
final class HammingVerifier implements ErrorControlVerifier {
    @Override
    public VerificationResult verify(ReceivedFrame received) {
        String frame = received.getFrame();
        int syndrome = calculateSyndrome(frame);
        if (syndrome == 0) {
            return VerificationResult.hamming(frame, ProcessingStatus.VALID, 0, -1, null);
        }
        if (syndrome > frame.length()) {
            return VerificationResult.hamming(frame, ProcessingStatus.UNCORRECTABLE,
                    syndrome, -1, null);
        }

        String corrected = flipBit(frame, syndrome);
        if (calculateSyndrome(corrected) != 0) {
            return VerificationResult.hamming(frame, ProcessingStatus.UNCORRECTABLE,
                    syndrome, syndrome, corrected);
        }
        return VerificationResult.hamming(corrected, ProcessingStatus.CORRECTED,
                syndrome, syndrome, corrected);
    }

    static boolean isPowerOfTwo(int position) {
        return position > 0 && (position & (position - 1)) == 0;
    }

    static int calculateSyndrome(String frame) {
        int syndrome = 0;
        for (int parityPosition = 1; parityPosition <= frame.length();) {
            int parity = 0;
            for (int position = 1; position <= frame.length(); position++) {
                if ((position & parityPosition) != 0 && frame.charAt(position - 1) == '1') {
                    parity ^= 1;
                }
            }
            if (parity != 0) {
                syndrome += parityPosition;
            }
            if (parityPosition > frame.length() / 2) {
                break;
            }
            parityPosition *= 2;
        }
        return syndrome;
    }

    private static String flipBit(String frame, int position) {
        StringBuilder corrected = new StringBuilder(frame);
        int index = position - 1;
        corrected.setCharAt(index, corrected.charAt(index) == '0' ? '1' : '0');
        return corrected.toString();
    }
}
