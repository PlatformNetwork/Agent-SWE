import com.ibm.as400.access.AS400;

public class VirtualThreadFallbackTest {
    public static void main(String[] args) throws Exception {
        AS400 system = new AS400();

        // Ensure setting virtual threads to true is accepted.
        system.setVirtualThreadUsed(true);
        if (!system.isVirtualThreadUsed()) {
            throw new AssertionError("Expected virtual threads to be enabled");
        }

        // Force virtual threads to be unsupported and ensure fallback occurs.
        System.setProperty("com.ibm.as400.access.AS400.virtualThreadSupported", "false");
        system.setStayAlive(1);

        java.lang.reflect.Field field = AS400.class.getDeclaredField("stayAliveThread_");
        field.setAccessible(true);
        Thread stayAliveThread = (Thread) field.get(system);
        if (stayAliveThread == null) {
            throw new AssertionError("Expected stay-alive thread to be created");
        }

        if (AS400.isVirtualThread(stayAliveThread)) {
            throw new AssertionError("Expected fallback to platform thread when virtual threads are unsupported");
        }

        System.out.println("OK");
    }
}
