import com.ibm.as400.access.AS400;

public class VirtualThreadsTest {
    public static void main(String[] args) throws Exception {
        AS400 system = new AS400();

        MethodPair pair = findVirtualThreadMethods(AS400.class);
        if (pair == null) {
            throw new AssertionError("Expected virtual thread getter/setter on AS400");
        }

        boolean defaultValue = (boolean) pair.getter.invoke(system);
        if (defaultValue) {
            throw new AssertionError("Expected virtual threads to be disabled by default");
        }

        pair.setter.invoke(system, Boolean.TRUE);
        boolean enabled = (boolean) pair.getter.invoke(system);
        if (!enabled) {
            throw new AssertionError("Expected virtual threads to be enabled after setting");
        }

        pair.setter.invoke(system, Boolean.FALSE);
        boolean disabled = (boolean) pair.getter.invoke(system);
        if (disabled) {
            throw new AssertionError("Expected virtual threads to be disabled after resetting");
        }

        System.out.println("OK");
    }

    private static MethodPair findVirtualThreadMethods(Class<?> clazz) {
        java.lang.reflect.Method setter = null;
        java.lang.reflect.Method getter = null;
        for (java.lang.reflect.Method method : clazz.getMethods()) {
            String name = method.getName().toLowerCase();
            if (name.contains("virtual") && name.contains("thread")) {
                if (method.getParameterCount() == 1 && method.getParameterTypes()[0] == boolean.class) {
                    setter = method;
                } else if (method.getParameterCount() == 0 && method.getReturnType() == boolean.class) {
                    getter = method;
                }
            }
        }
        if (setter == null || getter == null) {
            return null;
        }
        return new MethodPair(getter, setter);
    }

    private static class MethodPair {
        final java.lang.reflect.Method getter;
        final java.lang.reflect.Method setter;

        MethodPair(java.lang.reflect.Method getter, java.lang.reflect.Method setter) {
            this.getter = getter;
            this.setter = setter;
        }
    }
}
