/** Recupera datos solo después de una comprobación Fletcher satisfactoria. */
final class MessageRecovery {
    private MessageRecovery() { }

    static String recoverBinary(ReceivedFrame received, VerificationResult verification) {
        if (received.isHamming()) {
            return extractHammingInformation(verification.getRecoverableFrame(),
                    received.getOriginalLength());
        }
        String dataWithPadding = verification.getDataWithPadding();
        int end = dataWithPadding.length() - received.getPadding();
        return dataWithPadding.substring(0, end).substring(0, received.getOriginalLength());
    }

    private static String extractHammingInformation(String frame, int originalLength) {
        StringBuilder information = new StringBuilder();
        for (int position = 1; position <= frame.length(); position++) {
            if (!HammingVerifier.isPowerOfTwo(position)) {
                information.append(frame.charAt(position - 1));
            }
        }
        return information.substring(0, originalLength);
    }

    static String decodeAscii(String binaryMessage) {
        StringBuilder message = new StringBuilder(binaryMessage.length() / 8);
        for (int start = 0; start < binaryMessage.length(); start += 8) {
            int character = Integer.parseInt(binaryMessage.substring(start, start + 8), 2);
            message.append((char) character);
        }
        return message.toString();
    }
}
