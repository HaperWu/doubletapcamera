# doubletapcamera

把 ColorOS / 一加（OnePlus）上 **「双击电源键」的默认目标从「钱包」改成「相机」** 的 LSPosed 模块，
外加一整套把这个现象查到底的**逆向取证过程与排查手册**。

> 实测机型：**一加 Ace 5 Pro（PKR110，ColorOS 16 / Android 16，SDK 36）**
> 现象：双击电源键 → 弹出「钱包 / NFC 刷卡页」，而不是相机。

**Releases**：<https://github.com/HaperWu/doubletapcamera/releases> （`doubletap-camera.apk` 为已签名可用包）
**包名**：`io.github.doubletapcamera`

---

## 1. 这个仓库解决什么问题

双击电源键打开钱包，**不是**设置错了、不是默认应用/角色问题、也不是无障碍服务或手势服务被改写。
根因是 ColorOS 厂商框架**主动去问钱包 App「你允许被双击唤起吗」**：

```
PhoneWindowManagerExtImpl.oplusInterceptPowerKeyUp        (system_server, oplus-services.jar)
  └─ OplusWalletController.isQuickLaunchSupport / sendCheckWalletMessage
        └─ content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG
              SUPPORT_QUICK_START = true , HAS_ACTIVE_CARD = true
        └─ OplusWalletController.startWallet(boolean)
              └─ startActivity → com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity
```

而**系统设置页写的是另一个键**：`设置 → 连按两次电源按钮` 写 AOSP 的
`Settings.Secure double_tap_power_button_gesture`（`0=相机 / 1=钱包`），
厂商框架在两个 vendor dex 里对它 **0 命中**；厂商自己的键
`Settings.Secure double_tap_power_button_value`（`0=相机/1=钱包/2=助手/3=快捷应用`）
在本 ROM 没有任何 UI 会写（ColorOS 的厂商设置页是死代码），
⇒ **「设置里明明是相机，双击却开钱包」由此而来。**

另外两条相机路径在本机都被封死：

| 路径 | 门禁 | 本机情况 |
|---|---|---|
| AOSP `com.android.server.GestureLauncherService` | ROM 资源 + Quick Access Wallet 特性 flag | 资源是开的（`config_cameraDoubleTapPowerGestureEnabled=true`），但 ROM **没有 QuickAccessWallet 服务**、`flag.map` 里没有该 flag、`cmd aconfig` 被裁 ⇒ **ROM 层关闭** |
| ColorOS `OplusQuickAppController`（快捷应用/相机分支） | `persist.vendor.fingerprint.sensor_type == 'side'` + AppFeature 表里的 `com.android.settings.double_tap_power_button_quickapp` | 本机是 **optical（光学指纹）** ⇒ 恒 false |

⇒ **本机唯一能跑通的目标就是钱包**，且它由钱包 App 自己的开关控制。
于是有了本仓库的方案：**hook 厂商那条「钱包分支」，把它最后启动的钱包换成相机。**

---

## 2. 模块做了什么

在 `system_server` 里 hook 两个方法（类 `com.android.server.policy.OplusWalletController`）：

1. `getWalletSwitchState()` → **恒返回 1**
   （否则 `sendCheckWalletMessage` 会因为 "switch close" 直接放弃，钱包分支根本不触发）
2. `startWallet(boolean)` → **不执行原方法**，改为

   ```java
   new Intent("android.media.action.STILL_IMAGE_CAMERA")
       .setPackage("com.oplus.camera")
       .addFlags(NEW_TASK | CLEAR_TOP | SINGLE_TOP)
       .putExtra("need_screen_on", true);
   ```

   —— 完全照抄厂商 `OplusQuickAppController.startCamera` 的做法。

可选的「钱包进程内兜底」hook（`Instrumentation.callActivityOnResume`）**默认关闭**，
以免把正常打开钱包（刷卡 / 通知 / QS 磁贴）也改跳相机。

模式开关：

```bash
adb shell settings put system doubletap_camera_mode <0|1|2|3>
# 0 = 全关        1 = 只在钱包进程拦截
# 2 = 只在 system_server 拦截（默认，推荐）
# 3 = 两者都开
```

---

## 3. 安装

### 3.1 前提

* 已安装 **LSPosed 2.x**（本机实测 2.2.1 / API 102）+ Zygisk + KernelSU/Magisk；
* **LSPosed 2.x 只认「现代 API」**：老格式模块（`assets/xposed_init` + manifest `xposedminversion`）
  会被判成 legacy 而**根本不加载**（表现：`lspctl hook-debug dump` → `No process to dump`，模块日志 0 条）。

### 3.2 步骤

```bash
git clone <this-repo> && cd doubletapcamera
cd lsp-module && ./build.sh            # 产物 build/out/doubletap-camera.apk
adb install -r build/out/doubletap-camera.apk
bash lspdb.sh                          # 启用模块 + 设置作用域 + 修正 apk_path
adb reboot                             # 必须重启：system_server 注入发生在开机阶段
```

`lspdb.sh` 直接改 LSPosed 配置库 `/data/adb/lspd/config/modules_config.db`
（表 `modules` / `modules_state` / `scope`），原因是本机 `lspctl` 只有 `status`/`stop`
（要先在 LSPosed 管理器「设置 → 调试 → **开发者模式**」打开，才有 `module`/`scope` 子命令），
而 `app_process` 直写这个 SQLite 会被杀（没有 binder fd → `Bad file descriptor`）。

> **注意**：每次重装 APK 后 `apk_path` 都会变，**必须重跑 `lspdb.sh`**，否则模块不会被加载。

也可以全程用 GUI：LSPosed 管理器 → 模块 → 勾选「启用模块」+ 作用域勾上
**系统框架(system) / 系统卡包(com.heytap.tas) / Android 系统(android)** → 重启。

### 3.3 验证

```bash
adb shell su -c '/data/adb/modules/zygisk_lsposed/lspctl module show io.github.doubletapcamera'
#   期望：API: min=100 target=102 / Type: modern / User 0: enabled

adb shell su -c 'cat /data/adb/lspd/log/modules_*.log' | tail
#   期望：DblTapCam: getWalletSwitchState -> force 1
#        DblTapCam: startWallet intercepted -> camera (ctx=true)

adb shell input keyevent 3            # 回桌面
adb shell "input keyevent 26 26"      # 双击电源键（必须同一个进程连发两次！）
sleep 3
adb shell "dumpsys activity activities | grep topResumedActivity"
#   期望：topResumedActivity=ActivityRecord{... com.oplus.camera/.Camera}

adb logcat -d | grep -E 'DblTapCam|start wallet|STILL_IMAGE_CAMERA'
#   期望：有 STILL_IMAGE_CAMERA 启动，且 **没有任何 'start wallet'**（钱包完全没被拉起）
```

### 3.4 回滚

```bash
adb shell settings put system doubletap_camera_mode 0        # 最快，无需重启
adb shell su -c '/data/adb/modules/zygisk_lsposed/lspctl module disable io.github.doubletapcamera'
adb reboot
adb uninstall io.github.doubletapcamera                        # 彻底卸载
```

回滚后回到原生行为：**双击电源键 → 钱包**（受钱包自身开关控制）；
想恢复「双击电源键刷卡」，在 *钱包 → 设置 → 双击电源键* 里重新打开「双击电源键唤起快捷服务」。

---

## 4. 仓库结构

```
lsp-module/                     LSPosed 模块（现代 API）
  src/io/github/doubletapcamera/HookEntry.java   入口类（extends XposedModule）
  stubs/                        编译期桩（io.github.libxposed.api.*、AppComponentFactory）
  META-INF/xposed/              java_init.list / module.prop / scope.list
  AndroidManifest.xml
  build.sh                      ECJ + D8 + aapt2 + apksigner 全离线构建脚本
docs/
  double-tap-power-wallet-hijack.md      ★ 排查手册（600+ 行，含全部实测数据与命令）
  coloros16-double-tap-power-research.md ColorOS 16 双击电源键的社区调研
tools/                           本次自写的 DEX / ARSC 逆向分析工具
scripts/                         设备侧复现与判定脚本
```

### 4.1 现代 API 打包要点

| 包内文件 | 内容 |
|---|---|
| `META-INF/xposed/java_init.list` | 入口类全名 `io.github.doubletapcamera.HookEntry` |
| `META-INF/xposed/module.prop` | `minApiVersion=100` / `targetApiVersion=102` / `staticScope=false` |
| `META-INF/xposed/scope.list` | `system`（=system_server）/ `com.heytap.tas` / `android` |
| `AndroidManifest.xml` | **不要** `xposedminversion`、**不要** `xposedscope` |

入口类必须 `extends io.github.libxposed.api.XposedModule`，
实现 `onSystemServerStarting(SystemServerStartingParam)` 与 `onPackageLoaded(PackageLoadedParam)`。

### 4.2 离线构建（宿主机只有 JRE、没有 Android SDK）

```bash
./tools/fetch-build-deps.sh     # 下载 ecj / android.jar / build-tools r34（之后全程离线）
cd lsp-module && ./build.sh     # 产物 build/out/doubletap-camera.apk
```

GitHub Actions 里已经内置同样的流程（`.github/workflows/build-apk.yml`）：
push 到 `main` 会自动构建并产出 APK artifact 与 release。
> CI 用临时 keystore 签名，**与 Releases 里手工发布的签名不同**，跨版本升级前请先卸载旧版。

* 编译器：`org.eclipse.jdt:ecj`（Maven Central 有 `.jar`，`java -jar` 直接跑）；
* D8：只能从 build-tools 里取（`build-tools_r34/lib/d8.jar`），
  **Maven Central 没有 `com.android.tools:r8`**（404）；
* `jar` 命令不可用（只有 JRE 没有 JDK）⇒ 用 python `zipfile` 造 jar / 合并 APK；
* `aapt2` / `apksigner` / `zipalign` 均来自 build-tools_r34；
* D8 **必须逐个传 `.class` 文件**（传目录报 `Unsupported source file type`）；
* 用的是 API16 老 `android.jar` ⇒ 没有 `Settings.Global`、没有 `android.app.AppComponentFactory`，
  需要自己补编译期桩（桩只进 `stubs.jar`，**不进 APK**）；
* `io.github.libxposed.api.*` 的真实签名可以从设备上 pull 的
  `/data/adb/modules/zygisk_lsposed/framework.dex` 里反出来（用 `tools/dexsig.py`）。

---

## 5. 排查手册摘要

完整版见 **[docs/double-tap-power-wallet-hijack.md](docs/double-tap-power-wallet-hijack.md)**，
含：结论摘要、触发链路全景、7 大排查方向的可复制命令、9 组可复现对照实验、
三套修复方案与回滚、相机为何拉不起来的第二轮深挖、14 条踩坑清单、一页速查命令。

几条最关键的：

```bash
# 钱包是否自称「可被双击唤起」
adb shell 'content query --uri content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG'
#   → SUPPORT_QUICK_START=true, HAS_ACTIVE_CARD=true   ← 劫持根源

# 系统侧真正的绑定键（AOSP 语义 0=相机 1=钱包）
adb shell settings get secure double_tap_power_button_gesture
# 厂商键（ColorOS 厂商页才写，本 ROM 无 UI 会写）
adb shell settings get secure double_tap_power_button_value

# 复现双击：必须同一个进程连发两次，否则会被判成两次单按
adb shell "input keyevent 26 26"
# 判定结果（CAMERA / WALLET / NOTHING）
./scripts/fastpress.sh
```

---

## 6. License

MIT，见 [LICENSE](LICENSE)。
