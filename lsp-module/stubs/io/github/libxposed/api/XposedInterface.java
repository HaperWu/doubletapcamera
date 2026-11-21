package io.github.libxposed.api;

import java.lang.reflect.Constructor;
import java.lang.reflect.Executable;
import java.lang.reflect.Method;
import java.util.List;

/**
 * 编译期桩（仅用于 javac/ECJ 编译；运行时由 LSPosed 注入的真实实现提供）。
 * 签名取自设备上 /data/adb/modules/zygisk_lsposed/framework.dex 的真实 proto。
 */
public interface XposedInterface {

    int PRIORITY_DEFAULT = 50;
    int PRIORITY_HIGHEST = 10000;
    int PRIORITY_LOWEST = -10000;

    void log(int priority, String tag, String message);

    void log(int priority, String tag, String message, Throwable throwable);

    int getApiVersion();

    String getFrameworkName();

    String getFrameworkVersion();

    long getFrameworkVersionCode();

    long getFrameworkProperties();

    HookBuilder hook(Executable executable);

    HookBuilder hookClassInitializer(Class<?> clazz);

    Invoker<Method> getInvoker(Method method);

    CtorInvoker getInvoker(Constructor<?> constructor);

    interface Hooker {
        Object intercept(Chain chain) throws Throwable;
    }

    interface Chain {
        Object getThisObject();

        List<Object> getArgs();

        Object getArg(int index);

        Executable getExecutable();

        Object proceed() throws Throwable;

        Object proceed(Object[] args) throws Throwable;

        Object proceedWith(Object thisObject) throws Throwable;

        Object proceedWith(Object thisObject, Object[] args) throws Throwable;
    }

    interface HookBuilder {
        HookBuilder setId(String id);

        HookBuilder setPriority(int priority);

        HookBuilder setExceptionMode(ExceptionMode mode);

        HookHandle intercept(Hooker hooker);
    }

    interface HookHandle {
        String getId();

        Executable getExecutable();

        HookHandle replaceHook(Hooker hooker);

        void unhook();
    }

    enum ExceptionMode {
        PROTECTIVE,
        PASSTHROUGH
    }

    interface Invoker<T> {
        Object invoke(T thisObject, Object[] args) throws Throwable;

        Object invokeSpecial(T thisObject, Object[] args) throws Throwable;

        Invoker<T> setType(Type type);

        interface Type {
            Object invoke(Object thisObject, Object[] args) throws Throwable;
        }
    }

    interface CtorInvoker {
        Object newInstance(Object[] args) throws Throwable;

        Object newInstanceSpecial(Class<?> cls, Object[] args) throws Throwable;
    }
}
