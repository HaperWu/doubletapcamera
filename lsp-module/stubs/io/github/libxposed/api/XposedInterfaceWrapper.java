package io.github.libxposed.api;

import java.lang.reflect.Constructor;
import java.lang.reflect.Executable;
import java.lang.reflect.Method;

/** 编译期桩：真实类的 superclass 是 Object，并实现 XposedInterface。 */
public class XposedInterfaceWrapper implements XposedInterface {

    public void attachFramework(XposedInterface base, Runnable callback) {
    }

    public void detach() {
    }

    protected void ensureAttached() {
    }

    @Override
    public void log(int priority, String tag, String message) {
    }

    @Override
    public void log(int priority, String tag, String message, Throwable throwable) {
    }

    @Override
    public int getApiVersion() {
        return 0;
    }

    @Override
    public String getFrameworkName() {
        return null;
    }

    @Override
    public String getFrameworkVersion() {
        return null;
    }

    @Override
    public long getFrameworkVersionCode() {
        return 0L;
    }

    @Override
    public long getFrameworkProperties() {
        return 0L;
    }

    @Override
    public HookBuilder hook(Executable executable) {
        return null;
    }

    @Override
    public HookBuilder hookClassInitializer(Class<?> clazz) {
        return null;
    }

    @Override
    public Invoker<Method> getInvoker(Method method) {
        return null;
    }

    @Override
    public CtorInvoker getInvoker(Constructor<?> constructor) {
        return null;
    }
}
