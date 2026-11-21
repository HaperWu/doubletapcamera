package io.github.libxposed.api;

import android.app.AppComponentFactory;
import android.content.pm.ApplicationInfo;

/** 编译期桩：模块生命周期回调接口。 */
public interface XposedModuleInterface {

    void onModuleLoaded(ModuleLoadedParam param);

    void onPackageLoaded(PackageLoadedParam param);

    void onPackageReady(PackageReadyParam param);

    void onSystemServerStarting(SystemServerStartingParam param);

    boolean onHotReloading(HotReloadingParam param);

    void onHotReloaded(HotReloadedParam param);

    interface ModuleLoadedParam {
        String getProcessName();

        boolean isSystemServer();
    }

    interface PackageLoadedParam {
        String getPackageName();

        ClassLoader getDefaultClassLoader();

        ApplicationInfo getApplicationInfo();

        boolean isFirstPackage();
    }

    interface PackageReadyParam {
        ClassLoader getClassLoader();

        AppComponentFactory getAppComponentFactory();
    }

    interface SystemServerStartingParam {
        ClassLoader getClassLoader();
    }

    interface HotReloadingParam {
        Object getSavedInstanceState();

        void setSavedInstanceState(Object savedInstanceState);

        android.os.Bundle getExtras();
    }

    interface HotReloadedParam {
        Object getSavedInstanceState();

        java.util.List getOldHookHandles();

        android.os.Bundle getExtras();
    }
}
