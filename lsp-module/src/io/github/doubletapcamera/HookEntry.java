package io.github.doubletapcamera;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.provider.Settings;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;

import java.io.File;
import java.io.FileInputStream;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

import io.github.libxposed.api.XposedInterface;
import io.github.libxposed.api.XposedModule;
import io.github.libxposed.api.XposedModuleInterface;

/**
 * 双击电源键 → 直接打开相机（替代 ColorOS 钱包 NFC 快捷入口）。
 *
 * 现代 Xposed API（libxposed / LSPosed 2.x）模块入口：
 *   - 入口类放在 META-INF/xposed/java_init.list
 *   - 模块信息放在 META-INF/xposed/module.prop（minApiVersion / targetApiVersion）
 *   - 作用域放在 META-INF/xposed/scope.list（system = system_server）
 *
 * 两种拦截：
 *   system_server 内：hook com.android.server.policy.OplusWalletController
 *       getWalletSwitchState() -> 强制返回 1（否则框架因 "switch close" 直接放弃）
 *       startWallet(boolean)   -> 改为拉起相机，并跳过原方法
 *   钱包进程内：hook android.app.Instrumentation.callActivityOnResume，
 *       命中钱包 Activity 时改跳相机并 finish 掉它（兜底）
 */
public class HookEntry extends XposedModule {

    /**
     * 相机快门触发计数（相机进程内）。
     * 用来自校准：音量键事件走完相机的原生处理后，如果这个计数没有增加，
     * 说明相机的原生「音量键=快门」在当前启动模式下是失效的（锁屏快捷启动模式），
     * 这时才由我们兜底去点快门按钮；否则（解锁态原生功能正常）不重复点击，避免连拍两张。
     */
    private static volatile int sShutterCount = 0;

    private static final String TAG = "DblTapCam";
    private static final String CFG = "doubletap_camera_mode";
    private static final String CFG_SECURE = "doubletap_camera_secure";
    /** 锁屏时用哪个相机入口：0=默认(secure 相机) 1=CapturePhotoActivity 直拍 2=普通相机 */
    private static final String CFG_LOCK_ACT = "doubletap_camera_lock_act";
    /**
     * 传给相机的启动来源标记（extra: android_camera_launch_type）。
     * 相机 CameraEntry.d(String) 会把它和下面这些常量比较：
     *   gimbal_launch_from_framework / quick_launch_from_framework /
     *   quick_launch_from_smart_button / watch_launch_from_framework /
     *   spruce_double_tap_launch_from_framework / action_button_launch_from_framework
     * 其中 spruce_double_tap_launch_from_framework 是 ColorOS「快捷手势双击拍照」用的，
     * 相机会把它当成 isSpruceOrActionLaunch（不是锁屏快捷启动模式）。
     */
    private static final String CFG_LAUNCH_TYPE = "doubletap_camera_launch_type";
    private static final String DEFAULT_LAUNCH_TYPE = "quick_launch_from_framework";
    /** Settings.System "doubletap_camera_volkey"：0=关 1=锁屏时音量键=快门（默认 1） */
    private static final String CFG_VOLKEY = "doubletap_camera_volkey";
    /** 相机「音量键功能」= 快门 时才接管 */
    private static final String VOLKEY_SHUTTER = "shutter";
    /** 相机设置里存「音量键功能」的 MMKV key */
    private static final String VOLKEY_PREF_KEY = "pref_volume_key_function_key";

    private static final String CAMERA_PKG = "com.oplus.camera";
    private static final String CAMERA_ACTION = "android.media.action.STILL_IMAGE_CAMERA";
    /** 厂商自己的「安全相机」入口：可在锁屏之上唤起（锁屏快拍） */
    private static final String CAMERA_SECURE_ACTION = "android.media.action.STILL_IMAGE_CAMERA_SECURE";
    private static final String CAMERA_SECURE_COMPONENT = "com.oplus.camera.Camera";
    /** 相机里 showWhenLocked + turnScreenOn 都为 true 的「直拍」页（AOSP IMAGE_CAPTURE 的落地页） */
    private static final String CAMERA_CAPTURE_COMPONENT = "com.oplus.camera.component.CapturePhotoActivity";

    /** 钱包里可能被「双击电源键」拉起的 Activity */
    private static final Set<String> WALLET_ACTIVITIES = new HashSet<>(Arrays.asList(
            "com.nearme.wallet.nfc.ui.NfcConsumeActivity",
            "com.nearme.wallet.component.DispatcherActivity",
            "com.nearme.common.router.RouterActivity",
            "com.nearme.wallet.bus.ui.SysGuideNfcIndexActivity",
            "com.nearme.pay.business.oppopay.PayGuideNfcIndexActivity"));

    public HookEntry() {
        super();
    }

    @Override
    public void onModuleLoaded(XposedModuleInterface.ModuleLoadedParam param) {
        log("module loaded: process=" + param.getProcessName()
                + " isSystemServer=" + param.isSystemServer()
                + " api=" + getApiVersion());
    }

    /* ---------------- system_server：改写钱包启动 ---------------- */

    @Override
    public void onSystemServerStarting(XposedModuleInterface.SystemServerStartingParam param) {
        log("onSystemServerStarting");
        ClassLoader cl = param.getClassLoader();
        final Class<?> ctrl = findClass(cl, "com.android.server.policy.OplusWalletController");
        if (ctrl == null) {
            log("OplusWalletController not found");
            return;
        }
        // 1) 强制「钱包开关」为打开，否则 sendCheckWalletMessage 会因 switch close 直接返回
        try {
            final Method m = ctrl.getDeclaredMethod("getWalletSwitchState");
            m.setAccessible(true);
            hook(m).intercept(chain -> {
                if (!systemMode()) {
                    return chain.proceed();
                }
                log("getWalletSwitchState -> force 1");
                return Integer.valueOf(1);
            });
        } catch (Throwable t) {
            log("hook getWalletSwitchState failed: " + t);
        }
        // 2) startWallet(boolean) 改为拉起相机
        try {
            final Method m = ctrl.getDeclaredMethod("startWallet", boolean.class);
            m.setAccessible(true);
            hook(m).intercept(chain -> {
                if (!systemMode()) {
                    return chain.proceed();
                }
                try {
                    Context ctx = systemContext();
                    log("startWallet intercepted -> camera (ctx=" + (ctx != null) + ")");
                    if (ctx != null) {
                        startCamera(ctx);
                    }
                } catch (Throwable t) {
                    log("startWallet hook error: " + t);
                }
                return null;   // 不再执行原方法（不拉起钱包）
            });
        } catch (Throwable t) {
            log("hook startWallet failed: " + t);
        }
    }

    /* ---------------- 钱包进程：把钱包 Activity 改跳相机 ---------------- */

    @Override
    public void onPackageLoaded(XposedModuleInterface.PackageLoadedParam param) {
        String pkg = param.getPackageName();
        if (CAMERA_PKG.equals(pkg)) {
            hookCameraShutterCounter(param.getDefaultClassLoader());
            hookCameraVolumeKey(param.getDefaultClassLoader());
            return;
        }
        if (!"com.heytap.tas".equals(pkg)) {
            return;
        }
        log("onPackageLoaded " + pkg);
        final Class<?> instr = findClass(param.getDefaultClassLoader(), "android.app.Instrumentation");
        if (instr == null) {
            log("Instrumentation not found");
            return;
        }
        try {
            final Method m = instr.getDeclaredMethod("callActivityOnResume", Activity.class);
            m.setAccessible(true);
            hook(m).intercept(chain -> {
                Object a = chain.getArg(0);
                Object ret = chain.proceed();
                if (!(a instanceof Activity)) {
                    return ret;
                }
                Activity act = (Activity) a;
                if (!WALLET_ACTIVITIES.contains(act.getClass().getName())) {
                    return ret;
                }
                if (!walletMode(act)) {
                    return ret;
                }
                log("wallet activity " + act.getClass().getName() + " -> redirect to camera");
                try {
                    startCamera(act);
                    act.finish();
                } catch (Throwable t) {
                    log("redirect failed: " + t);
                }
                return ret;
            });
        } catch (Throwable t) {
            log("hook callActivityOnResume failed: " + t);
        }
    }

    /* ---------------- 公共工具 ---------------- */

    /* ---------------- 相机进程：锁屏快捷启动模式下补回「音量键=快门」 ---------------- */

    /**
     * 锁屏（含密码）时双击电源键拉起相机，ColorOS 相机会进入「锁屏快捷启动」模式
     * （日志：OCAM_EventMessageUIContainerContext: setLockScreenStart: true）。
     * 该模式下相机自己的音量键功能被禁用：音量键事件送到了相机
     * （OCAM_OplusCamera: Key down has been intercepted），但快门/变焦监听没有生效。
     *
     * 兜底：锁屏 + 音量键 -> 直接点相机的快门按钮（com.oplus.camera.control.ShutterButton）。
     * 只在相机设置里「音量键功能 = 快门」时接管。
     */
    /**
     * hook 相机的快门处理方法（com.oplus.camera.ui.control.CameraControlUI$f.d(ShutterButton, int)，
     * 它会打印 "onShutterButtonClick, ShutterButton.id: ..."），用于自校准：
     * 音量键事件走完相机的原生处理后，如果计数没有增加，说明原生音量键功能在当前模式下失效。
     */
    private void hookCameraShutterCounter(ClassLoader cl) {
        Class<?> c = findClass(cl, "com.oplus.camera.ui.control.CameraControlUI$f");
        if (c == null) {
            log("camera shutter handler class not found");
            return;
        }
        try {
            for (Method m : c.getDeclaredMethods()) {
                if (!"d".equals(m.getName()) || m.getParameterTypes().length != 2) {
                    continue;
                }
                m.setAccessible(true);
                hook(m).intercept(chain -> {
                    Object r = chain.proceed();
                    sShutterCount++;
                    return r;
                });
                log("camera shutter handler hooked: " + m);
            }
        } catch (Throwable t) {
            log("hook camera shutter handler failed: " + t);
        }
    }

    private void hookCameraVolumeKey(ClassLoader cl) {
        Class<?> cam = findClass(cl, CAMERA_PKG + ".Camera");
        if (cam == null) {
            log("camera class not found: " + CAMERA_PKG + ".Camera");
            return;
        }
        try {
            final Method m = cam.getDeclaredMethod("onKeyDown", int.class, KeyEvent.class);
            m.setAccessible(true);
            hook(m).intercept(chain -> {
                int keyCode = (Integer) chain.getArg(0);
                int shutterBefore = sShutterCount;
                Object ret = chain.proceed();
                try {
                    if (keyCode != KeyEvent.KEYCODE_VOLUME_UP && keyCode != KeyEvent.KEYCODE_VOLUME_DOWN) {
                        return ret;
                    }
                    Object self = chain.getThisObject();
                    if (!(self instanceof Activity)) {
                        return ret;
                    }
                    Activity act = (Activity) self;
                    if (volKeyEnabled(act) == 0) {
                        return ret;
                    }
                    String fn = readVolKeyFunction(act);
                    if (fn != null && !VOLKEY_SHUTTER.equals(fn)) {
                        log("volume key function=" + fn + " (not shutter) -> skip");
                        return ret;
                    }
                    if (sShutterCount != shutterBefore) {
                        // 相机的原生音量键处理已经触发了快门（解锁态），不要重复点击
                        log("volume key handled natively (shutter " + shutterBefore + " -> " + sShutterCount + ")");
                        return ret;
                    }
                    // 原生处理没有触发快门（锁屏快捷启动模式下相机会禁用音量键功能）→ 兜底点快门
                    View v = findShutterView(act.getWindow() != null ? act.getWindow().getDecorView() : null);
                    if (v != null) {
                        log("volume key fallback -> shutter click (" + v.getClass().getName() + ")");
                        v.performClick();
                    } else {
                        log("volume key fallback -> shutter view not found");
                    }
                } catch (Throwable t) {
                    log("volume key fallback error: " + t);
                }
                return ret;
            });
            log("camera onKeyDown hooked");
        } catch (Throwable t) {
            log("hook camera onKeyDown failed: " + t);
        }
    }

    /** Settings.System "doubletap_camera_volkey"：0=关 1=锁屏时音量键=快门（默认 1） */
    private static int volKeyEnabled(Context ctx) {
        if (ctx == null) {
            return 1;
        }
        try {
            return Settings.System.getInt(ctx.getContentResolver(), CFG_VOLKEY, 1);
        } catch (Throwable t) {
            return 1;
        }
    }

    /** 在视图树里找相机的快门按钮 */
    private static View findShutterView(View root) {
        if (root == null) {
            return null;
        }
        String cn = root.getClass().getName();
        if (cn.contains("ShutterButton")) {
            return root;
        }
        if (root instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) root;
            for (int i = 0; i < g.getChildCount(); i++) {
                View v = findShutterView(g.getChildAt(i));
                if (v != null) {
                    return v;
                }
            }
        }
        return null;
    }

    /**
     * 读相机自己的「音量键功能」设置（MMKV: files/mmkv/com.oplus.camera_preferences）。
     * 文件里 key 的布局：[keyLen][key][valLen][valType][value...]，
     * 这里按字节扫描；取不到返回 null（调用方按「快门」处理）。
     */
    private static String readVolKeyFunction(Context ctx) {
        try {
            File f = new File(ctx.getFilesDir(), "mmkv/com.oplus.camera_preferences");
            if (!f.exists()) {
                return null;
            }
            byte[] data = readAll(f);
            byte[] key = VOLKEY_PREF_KEY.getBytes();
            for (int i = 0; i + key.length + 2 < data.length; i++) {
                boolean hit = true;
                for (int j = 0; j < key.length; j++) {
                    if (data[i + j] != key[j]) {
                        hit = false;
                        break;
                    }
                }
                if (!hit) {
                    continue;
                }
                int p = i + key.length;
                int valLen = data[p] & 0xff;
                if (valLen <= 1 || p + valLen >= data.length) {
                    continue;
                }
                return new String(data, p + 2, valLen - 1);
            }
        } catch (Throwable t) {
            // ignore
        }
        return null;
    }

    private static byte[] readAll(File f) throws Exception {
        byte[] buf = new byte[(int) f.length()];
        FileInputStream in = new FileInputStream(f);
        try {
            int off = 0;
            while (off < buf.length) {
                int n = in.read(buf, off, buf.length - off);
                if (n <= 0) {
                    break;
                }
                off += n;
            }
        } finally {
            try {
                in.close();
            } catch (Throwable ignore) {
                // ignore
            }
        }
        return buf;
    }

    private void hook(Method m, XposedInterface.Hooker h) {
        hook(m).setPriority(XposedInterface.PRIORITY_DEFAULT).intercept(h);
    }

    private static Class<?> findClass(ClassLoader cl, String name) {
        if (cl == null) {
            return null;
        }
        try {
            return Class.forName(name, false, cl);
        } catch (Throwable t) {
            try {
                return Class.forName(name);
            } catch (Throwable t2) {
                return null;
            }
        }
    }

    /** system_server 里拿 Context：ActivityThread.currentActivityThread().getSystemContext() */
    private static Context systemContext() {
        try {
            Class<?> at = Class.forName("android.app.ActivityThread");
            Method cur = at.getDeclaredMethod("currentActivityThread");
            cur.setAccessible(true);
            Object t = cur.invoke(null);
            if (t == null) {
                return null;
            }
            Method gsc = at.getDeclaredMethod("getSystemContext");
            gsc.setAccessible(true);
            return (Context) gsc.invoke(t);
        } catch (Throwable e) {
            return null;
        }
    }

    /**
     * 拉起相机。
     *
     * 锁屏（有 keyguard）时，普通 action 启动的相机会落在锁屏后面，用户必须先解锁才能看到。
     * ColorOS 自己启动相机用的是「secure camera」入口（反编译自
     * com.android.server.policy.PhoneWindowManagerExtImpl.startCamera）：
     *   action    = android.media.action.STILL_IMAGE_CAMERA_SECURE
     *   component = com.oplus.camera.Camera
     *   flags     = FLAG_ACTIVITY_NEW_TASK
     * 走这个入口相机才能盖在锁屏上（锁屏快拍）。
     *
     * 注意：厂商那段代码还带 mode=29 / lunch_type=2 两个 extra，但**不能照抄**——
     * 见下面 startCamera 里的注释（带上这两个 extra 会导致拍照管线异常、只能拍一张）。
     */
    private static void startCamera(Context ctx) {
        if (ctx == null) {
            return;
        }
        int secureMode = secureMode(ctx);          // 0=自动 1=强制 2=禁用
        boolean locked = isKeyguardLocked(ctx);
        if (secureMode == 1 || (secureMode == 0 && locked)) {
            // 锁屏：优先用「直拍」页（showWhenLocked + turnScreenOn），其次 secure 相机
            int lockAct = lockAct(ctx);
            if (lockAct == 1) {
                try {
                    Intent ci = new Intent("android.media.action.IMAGE_CAPTURE");
                    ci.setPackage(CAMERA_PKG);
                    ci.setComponent(new ComponentName(CAMERA_PKG, CAMERA_CAPTURE_COMPONENT));
                    ci.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    ci.putExtra("android_camera_launch_type", launchType(ctx));
                    ci.putExtra("extra_key_caller_package_name", "com.oplus.gesture");
                    ctx.startActivity(ci);
                    android.util.Log.i(TAG, "camera launched (capture/锁屏直拍, locked=" + locked + ")");
                    return;
                } catch (Throwable t) {
                    android.util.Log.i(TAG, "capture camera launch failed: " + t + " -> fallback");
                }
            }
            try {
                Intent si = new Intent();
                si.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                // 只带 caller_package；**不要**再带 mode=29 / lunch_type=2：
                // 这两个 extra 是厂商「安全相机」专用参数，一旦带上，ColorOS 相机会把
                // 拍照管线切到受限模式（capture 请求发出去但收不到回帧，
                // 日志 OCAM_g1_BaseMode: capture, failed to send request /
                // OCAM_AutoLogHelper: tryCatchCaptureFailedLog, reason: CF_FOREGROUND_CAPTURE），
                // 结果「按快门不出图、只能拍一张」。实测去掉后照片正常落盘。
                si.putExtra("caller_package", "android");
                si.setAction(CAMERA_SECURE_ACTION);
                si.setComponent(new ComponentName(CAMERA_PKG, CAMERA_SECURE_COMPONENT));
                // 相机（com.oplus.camera.CameraManager）靠这两个 extra 判断「是不是系统/手势服务的
                // 正规快捷启动」，从而决定锁屏时是否允许盖在 keyguard 之上：
                //   android_camera_launch_type  = quick_launch_from_framework
                //   extra_key_caller_package_name = com.oplus.gesture
                si.putExtra("android_camera_launch_type", launchType(ctx));
                si.putExtra("extra_key_caller_package_name", "com.oplus.gesture");
                ctx.startActivity(si);
                android.util.Log.i(TAG, "camera launched (secure/锁屏路径, locked=" + locked + ")");
                return;
            } catch (Throwable t) {
                android.util.Log.i(TAG, "secure camera launch failed: " + t + " -> fallback");
            }
        }
        Intent i = new Intent(CAMERA_ACTION);
        i.setPackage(CAMERA_PKG);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TOP
                | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        i.putExtra("need_screen_on", true);
        i.putExtra("android_camera_launch_type", launchType(ctx));
        i.putExtra("extra_key_caller_package_name", "com.oplus.gesture");
        ctx.startActivity(i);
        android.util.Log.i(TAG, "camera launched (normal, locked=" + locked + ")");
    }

    /** 当前是否处于锁屏（keyguard）状态 */
    private static boolean isKeyguardLocked(Context ctx) {
        try {
            KeyguardManager km = (KeyguardManager) ctx.getSystemService(Context.KEYGUARD_SERVICE);
            return km != null && km.isKeyguardLocked();
        } catch (Throwable t) {
            return false;
        }
    }

    /** Settings.System "doubletap_camera_secure"：0=自动(锁屏时用 secure 入口) 1=强制 2=禁用 */
    private static int secureMode(Context ctx) {
        if (ctx == null) {
            return 0;
        }
        try {
            return Settings.System.getInt(ctx.getContentResolver(), CFG_SECURE, 0);
        } catch (Throwable t) {
            return 0;
        }
    }

    /** Settings.System "doubletap_camera_launch_type"：传给相机的启动来源标记 */
    private static String launchType(Context ctx) {
        if (ctx == null) {
            return DEFAULT_LAUNCH_TYPE;
        }
        try {
            String v = Settings.System.getString(ctx.getContentResolver(), CFG_LAUNCH_TYPE);
            return (v == null || v.length() == 0) ? DEFAULT_LAUNCH_TYPE : v;
        } catch (Throwable t) {
            return DEFAULT_LAUNCH_TYPE;
        }
    }

    /** Settings.System "doubletap_camera_lock_act"：锁屏时用哪个入口 0=secure 相机 1=直拍页 2=普通相机 */
    private static int lockAct(Context ctx) {
        if (ctx == null) {
            return 0;
        }
        try {
            return Settings.System.getInt(ctx.getContentResolver(), CFG_LOCK_ACT, 0);
        } catch (Throwable t) {
            return 0;
        }
    }

    /**
     * 模式位（设置键：Settings.System "doubletap_camera_mode"）
     *   0 = 全关
     *   1 = 只在钱包进程里拦截（会把“正常打开钱包”也改跳相机，不推荐）
     *   2 = 只在 system_server 里拦截（默认，推荐：只改“双击电源键”这一条路径）
     *   3 = 两者都开
     */
    private static int mode(Context ctx) {
        if (ctx == null) {
            return 2;
        }
        try {
            return Settings.System.getInt(ctx.getContentResolver(), CFG, 2);
        } catch (Throwable t) {
            return 2;
        }
    }

    /** system_server 分支是否生效 */
    private static boolean systemMode() {
        return (mode(systemContext()) & 2) != 0;
    }

    /** 钱包进程分支是否生效 */
    private static boolean walletMode(Activity act) {
        return (mode(act) & 1) != 0;
    }

    private void log(String msg) {
        try {
            android.util.Log.i(TAG, msg);
        } catch (Throwable ignored) {
        }
        try {
            log(android.util.Log.INFO, TAG, msg);
        } catch (Throwable ignored) {
        }
    }
}
