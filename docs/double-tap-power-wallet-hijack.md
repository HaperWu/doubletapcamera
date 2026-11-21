# OnePlus Ace 5 Pro：双击电源键被「钱包」接管 —— 根因分析与排查/修复手册

> 设备：`PKR110`（OnePlus Ace 5 Pro，ColorOS 16 / `PKR110_16.0.0.204(CN01)`，Android 16 / SDK 36）
> 连接：ADB（`3B157N001GB00000`），原为 root（KernelSU，`u:r:ksu:s0`）
> 结论一句话：**不是系统手势被改写，而是「钱包」App 自己开启了「双击电源键唤起快捷服务」，它向 ColorOS 的 system_server 上报 `SUPPORT_QUICK_START=true`，system_server 的厂商层 `OplusWalletController` 就把双击电源键改派给了钱包（`com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity`），而不是相机。关掉钱包里的那个开关，劫持即消失。**

---

## 1. 结论摘要（实测）

| 项 | 实测结果 |
|---|---|
| 双击电源键实际打开 | `com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity`（钱包刷卡页） |
| 谁触发的 | **system_server 厂商层**（`/system/framework/oplus-services.jar` → `com.android.server.policy.OplusWalletController` / `PhoneWindowManagerExtImpl`），不是钱包自注册广播、不是无障碍、不是快捷手势 App 改写 |
| 钱包被允许接管的条件 | 钱包 App 自己上报的 flag：`content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG` → `SUPPORT_QUICK_START=true`（且 `HAS_ACTIVE_CARD=true`） |
| 该 flag 的总开关 | 钱包 App 内「设置 → 双击电源键 → 双击电源键唤起快捷服务」开关（App 私有状态：MMKV `quick_start_switcher_` / DB `CARD_BAG_FLAG`） |
| 系统侧绑定项 | `Settings.Secure double_tap_power_button_gesture`：**0 = 相机，1 = 钱包**（设置 App 的「相机/钱包」单选按钮**只写这一个键**） |
| 设置界面显示 | 一直是「相机」（已选中）—— 即 **系统配置本来就指向相机，是钱包侧把它抢走了** |
| 钱包开关关闭后 | 双击电源键 **不再打开钱包**（劫持解除 ✔），但相机**仍不会自动拉起**：AOSP 相机分支（`GestureLauncherService`）与厂商相机分支（`OplusQuickAppController`）的门禁在这台机器上都过不去（详见第 7 节） |
| 相机为什么拉不起来 | 本 ROM 启用了双击相机能力（资源 `config_cameraDoubleTapPowerGestureEnabled=true`），但 ① 本机指纹为 **光学**（`persist.vendor.fingerprint.sensor_type=optical`），厂商「双击→相机/快捷应用」分支要求 `=='side'`；② 设置页写的是 AOSP 键 `double_tap_power_button_gesture`，厂商框架读的是另一把键 `double_tap_power_button_value`（本 ROM 的 ColorOS 厂商页是死代码） |

已做的修复（设备当前状态）：钱包「双击电源键唤起快捷服务」= **关闭**；`secure double_tap_power_button_gesture=0`（相机）；其余键值均已还原。

---

## 2. 触发链路全景（实测拼图）

```
物理双击电源键
   │
   ├─ AOSP：PhoneWindowManager.interceptKeyBeforeQueueing()
   │     └─ handleKeyGesture → SingleKeyGestureDetector.interceptKey
   │          └─ handleCameraGesture → GestureLauncherService.interceptPowerKeyDown
   │               └─ 门禁：double_tap_power_button_gesture(_enabled) / camera_double_tap_power_gesture_disabled
   │                        / ROM 资源 0x0111006E(已确认=true) / Zen 模式(唯一厂商否决点)
   │               └─ sendGestureTargetActivityPendingIntent → 相机（本机未通过门禁）
   │
   ├─ 厂商扩展：PhoneWindowManagerExtImpl.overrideInterceptKeyBeforeQueueing / oplusInterceptPowerKeyUp
   │     · 日志 ', keyguardOn = ' ', screenOn = ' ', WalletSwitchState = ' ', IsQuickLaunchSupport = ' ...
   │     · 顺序：isQuickAppSupport → oplusSmartButtonControllerIsValid → isQuickDoubleWakeAppSupport
   │            → OplusWalletController.isQuickLaunchSupport → sendCheckWalletMessage / sendCheckQuickAppMessage
   │
   ├─ OplusWalletController.handlePowerKeyUpForWallet()       ← 钱包分支（优先级更高）
   │     · 读 content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG
   │     · SUPPORT_QUICK_START=true && HAS_ACTIVE_CARD=true
   │     · startWallet() → com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity
   │     · （provider 查询失败 / flag=false 时才让出）
   │
   └─ OplusQuickAppController.startQuickApp() → startCamera() ← 厂商相机/快捷应用分支
         · 门禁：isQuickAppOn = isQuickAppSupport(指纹须为 side + AppFeature 特性行)
         ·           && isSwitchOn && isQuickAppDoublePowerClicked
         · 本机指纹=optical ⇒ 先天不满足（本机未走到）
```

关键佐证：
- `dumpsys window policy` → `mDoublePressOnPowerBehavior=MULTI_PRESS_POWER_NOTHING`：**这是 Android 16 的正常值**，
  因为 AOSP 16 已经删掉 `PowerButtonBehaviorController`（双击相机改由 `com.android.server.GestureLauncherService` 实现），
  **不能**据此认为「厂商禁用了相机」；厂商对 AOSP 相机路径的唯一否决点是 Zen 模式。
- `dumpsys activity broadcasts` → system_server 注册了 `com.android.server.policy.OplusWalletController$2`（u-1）与 `$5`（u0），`Ssp: PatternMatcher{LITERAL: com.finshell.wallet}`。
- 钱包 App 的 Receiver Resolver Table 里**没有任何**电源键/双击相关 action（只有 NFC、账号、电池、carkey），⇒ 钱包是**被系统按目标拉起**的，不是自己监听的。
- 反向验证：把钱包包整个 `pm disable` 后，双击**什么都不启动**（不是转去相机）⇒ 钱包分支是「权威分支」，相机是另一条独立分支。

---

## 3. 系统化排查步骤（可直接复制执行）

### 3.1 环境自检

```bash
adb devices -l
adb shell getprop | grep -E 'ro.product.model|ro.build.display.id|ro.build.version.opporom|ro.build.version.release'
adb shell id                      # root?（本机重启后降级为 uid=2000(shell)）
adb shell 'ls -l /system/bin/logd /system/bin/logcat'   # 本机为 0 字节桩 → logcat 不可用
adb shell 'getprop init.svc.logd'                        # stopped
```
> ⚠️ 本机 `/system/bin/logd`、`/system/bin/logcat` 是 **0 字节占位文件**，`init.svc.logd=stopped`，
> `setprop ctl.start logd` 报 `PROP_ERROR_HANDLE_CONTROL_MESSAGE`。
> ⇒ **所有验证必须走状态面**：`dumpsys` / `settings` / `content query` / `uiautomator dump`。

### 3.2 找到「双击电源键」的绑定项（系统侧）

```bash
# 三个命名空间全量导出，再挑关键字
for ns in secure system global; do adb shell settings list $ns; done | grep -iE \
 'double_tap|camera_double|quick_launch|gesture|wallet'

# 本机关键值
# secure double_tap_power_button_gesture=0            ← 0=相机 / 1=钱包（真正的绑定项）
# secure double_tap_power_button_gesture_enabled=1     ← 设置里的总开关「启用“连按两次”动作」
# secure camera_double_tap_power_gesture_disabled=0
# system oplus_customize_double_click_camera_on=0
# system oplus_customize_gesture_to_take_photo_enabled=0
# secure oplus_customize_gesture_open_type=0           ← 快捷手势（屏幕双击）用，与电源键无关

# 厂商键（OplusQuickAppController 使用，本机默认不存在）
adb shell settings get secure double_tap_power_button_value   # null
adb shell settings get system double_tap_power_button_value   # null
```

> Android 16 没有 `settings.db`，设置以 protobuf 二进制存于 `/data/system/users/0/settings_{secure,system,global}.xml`；
> root 下可直接解析（字段 4 = 名称，字段 5 = 值）。

### 3.3 找到快捷手势（com.oplus.gesture）侧的存储

```bash
adb shell 'content query --uri content://com.oplus.gestureguide/setting'
# Row: 0 id=1, open_type=0, select_type=1     ← open_type/select_type 是快捷手势(松果)侧状态
```
> 该 provider 需要 `com.oplus.permission.safe.SETTINGS`：**root 可以查，普通 shell 会 SecurityException**。
> `content update` 可以改（root 下实测有效），但 shell 无权限。

### 3.4 抓到「谁响应了双击」

```bash
# ① 记录双击前后的前台 Activity（Android 16 是 ResumedActivity:，不是 topResumedActivity=）
adb shell "dumpsys activity activities | grep -E 'ResumedActivity:'"

# ② 复现双击（HOME → 两次电源键，间隔 ~0.12s）
adb shell input keyevent 3
adb shell input keyevent 26 ; sleep 0.12 ; adb shell input keyevent 26

# ③ 再看前台
adb shell "dumpsys activity activities | grep -E 'ResumedActivity:'"
# → com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity   ← 钱包被拉起

# ④ 系统侧广播/注册关系
adb shell dumpsys activity broadcasts | grep -iE 'heytap|finshell|wallet' | head -20

# ⑤ 钱包包是否有自注册 receiver（排除“钱包自己监听”的可能）
adb shell dumpsys package com.heytap.tas | sed -n '/Receiver Resolver Table/,/^  [A-Z]/p' | head -40
```

### 3.5 默认应用 / 角色 / NFC 支付归属（通常被误怪的对象）

```bash
adb shell cmd role get-role-holders android.app.role.ROLE_HOME
adb shell cmd role get-role-holders android.app.role.ROLE_PAYMENT
adb shell cmd role get-role-holders android.app.role.ROLE_CAMERA     # 本机为空（无人持有）
adb shell dumpsys activity service com.android.server.quickaccesswallet.QuickAccessWalletService   # No services match
adb shell 'cmd package resolve-activity --brief -a android.media.action.IMAGE_CAPTURE'  # com.oplus.camera/.component.CapturePhotoActivity
adb shell 'cmd package resolve-activity --brief -c android.intent.category.LAUNCHER com.heytap.tas'  # No activity found（钱包无桌面图标）
adb shell settings get secure nfc_payment_default_component     # null
adb shell settings get global has_pay_tokens                    # 0
```
> 结论：钱包**不是**默认应用/角色/无障碍/快捷手势 App 在拦截；它是厂商框架按目标直接拉起的。

### 3.6 钱包侧开关（本次根因所在）

```bash
# 钱包把「我可以被双击电源键唤起」暴露给 system_server 的唯一接口
adb shell 'content query --uri content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG'
# Row: 0 _id=1, UNIQUE_TAG=com.nearme.wallet.db.CardBagFlag, SUPPORT_QUICK_START=true, HAS_ACTIVE_CARD=true, PERIOD=72
```
`SUPPORT_QUICK_START=true` ＝ 钱包在 system_server 侧登记了「双击电源键 → 唤起我」。
这个值由钱包 App 自己维护（App 内部 DB `CARD_BAG_FLAG` + MMKV `quick_start_switcher_`），**App 一运行就会把 `true` 写回去**——所以 `content update`（provider 只读）或直接改 DB 都会被回写。

对应的用户可见开关（**真正的根因开关**）：

```bash
adb shell am start -n com.heytap.tas/com.finshell.setting.activity.WalletSettingActivity
# 钱包 → 设置 → 双击电源键 → 「双击电源键唤起快捷服务」(com.heytap.tas:id/coui_switch)
# 关闭时会弹确认框「确定关闭“双击电源键”功能吗？」→ 确认关闭
```
关闭后 provider 立即变为 `SUPPORT_QUICK_START=false, HAS_ACTIVE_CARD=false`，且钱包不再回写。

### 3.7 厂商定制层（ColorOS / 一加）

```bash
# 厂商框架扩展（真正的劫持逻辑在这里）
adb shell ls -l /system/framework/oplus-services.jar
# 关键类（位于 classes2.dex）：
#   com.android.server.policy.OplusWalletController        钱包分支（handlePowerKeyUpForWallet/startWallet）
#   com.android.server.policy.OplusQuickAppController       双击目标/快捷应用（KEY_DOUBLE_TAP_POWER_BUTTON_VALUE）
#   com.android.server.policy.PhoneWindowManagerExtImpl     电源键拦截（interceptKeyBeforeDispatching）
#   com.android.server.policy.OplusDoubleWakeAppController   双击唤醒/双击启动
#   com.android.server.policy.StrategyVolumeKeyLaunchCamera 音量键拉相机（另一条路径）
#   com.android.server.wm.OplusWindowAnimationManager        QUICK_LAUNCH_CAMERA_WAKE_DELAY 等

# 厂商钱包配置缓存（system_server 写）
adb shell cat /data/oplus/os/walletdata          # period=72 / supportQuickStart=true
adb shell getprop persist.sys.pkwallet.support    # true
adb shell getprop persist.sys.secondary_page_quick_start

# 快捷手势 / 松果（spruce）层
adb shell pm path com.oplus.gesture              # /system_ext/app/OplusGestureUI/OplusGestureUI.apk
adb shell 'dumpsys package com.oplus.gesture | grep -oE "com\.oplus\.gesture[./][A-Za-z0-9_.]*Activity"'
#   .sprucekey.SpruceSettingsActivity / .guide.GestureMainActivity / .customize.shake.ShakeQuickLaunchActivity ...
```
> 这些 Activity 受 `oplus.permission.OPLUS_COMPONENT_SAFE` 保护，只能由系统/设置 App 拉起，shell 直接 `am start` 会被拒：
> `SecurityException: ... requires oplus.permission.OPLUS_COMPONENT_SAFE`。

---

## 4. 已验证的根因（可复现的对照实验）

| # | 操作 | 结果 |
|---|---|---|
| A | 基线：双击电源键 | 打开 **钱包** `com.heytap.tas/...NfcConsumeActivity` |
| B | 钱包「双击电源键唤起快捷服务」→ 关闭 | provider 变 `false/false`；双击 **不再打开钱包** ✔ 劫持解除 |
| C | provider `content update` 改 `SUPPORT_QUICK_START=false` | **无效**（provider 对 shell 只读；且钱包 App 稍后把行写回 `true`） |
| D | root 下直接改钱包 DB `CARD_BAG_FLAG.SUPPORT_QUICK_START='false'` | provider 变 false，但**双击仍开钱包** ⇒ 框架不是实时读该行；且钱包 App 会把行写回 `true` ⇒ 真正的开关在 App 内部（MMKV `quick_start_switcher_`），必须用 App 自己的开关关 |
| E | `pm disable-user --user 0 com.heytap.tas` | 双击**什么也不发生**（相机也没开）⇒ 钱包分支是「权威」的，相机不是它的兜底 |
| F | `resetprop persist.sys.pkwallet.support false`（不重启） | 仍开钱包 ⇒ 该 prop 在 boot 时被 `preInitForWallet` 消费，不是每次手势实时读 |
| G | `resetprop persist.sys.pkwallet.support false` + 重启 | **prop 又变回 true**（resetprop 对 persist 属性不持久），且 `/data/oplus/os/walletdata` 被 system_server 重写 |
| H | 穷举 settings 矩阵：`double_tap_power_button_value`(0/1/2/3，secure+system)、`double_tap_power_button_gesture`(0/1)、`double_tap_power_button_gesture_enabled`、`camera_double_tap_power_gesture_disabled`、`oplus_customize_double_click_camera_on`、`oplus_customize_gesture_open_type`、`android_camera_launch_type`、`spruce_support_launch_camera`、`spruce_start_camera_name`、`spruce_camera_tap_none`（三个命名空间全试） | **无一能让相机拉起**（且在钱包开关 ON 时全部仍开钱包）⇒ 相机分支的门禁不在这些键上 |
| I | 设置 App「相机/钱包」单选按钮 | 只写 `secure double_tap_power_button_gesture`（钱包=1 / 相机=0），**不写**其它任何键，也**不碰** `com.oplus.gestureguide` provider ⇒ 系统侧本来就已经是「相机」 |

---

## 5. 修复方案

### 方案 A（推荐，已验证）：关掉钱包的「双击电源键唤起快捷服务」

```bash
# 1) 打开钱包设置页（该页不受权限限制）
adb shell am start -n com.heytap.tas/com.finshell.setting.activity.WalletSettingActivity
# 2) UI 操作：双击电源键 → 关闭「双击电源键唤起快捷服务」→ 确认关闭
#
# 3) 验证 flag 已落地
adb shell 'content query --uri content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG'
#    期望：SUPPORT_QUICK_START=false, HAS_ACTIVE_CARD=false
#
# 4) 验证双击不再开钱包
adb shell input keyevent 3
adb shell input keyevent 26 ; sleep 0.12 ; adb shell input keyevent 26
adb shell "dumpsys activity activities | grep -E 'ResumedActivity:'"
```

### 方案 B：把系统绑定强制回「相机」（防钱包再抢）

```bash
adb shell settings put secure double_tap_power_button_gesture 0        # 0=相机 1=钱包
adb shell settings put secure double_tap_power_button_gesture_enabled 1
adb shell settings put secure camera_double_tap_power_gesture_disabled 0
# 厂商键（部分 ROM 读它：0相机/1钱包/2助手/3快捷应用）
adb shell settings put secure double_tap_power_button_value 0
```
> 注意：本机上这些键**不能**单独把钱包拉下来（实验 H），钱包开关才是决定项；它们只保证「钱包若被拉起时，目标仍是相机」。
> 另外 `double_tap_power_button_value` 这类厂商键在 `OplusQuickAppController` 里被读，但 `oplus-services.jar` 的
> `static_values` 被厂商加密保护（读出来是垃圾数据），常量名可读、取值不可读。

### 方案 C：彻底屏蔽钱包组件（极端手段）

```bash
adb shell pm disable --user 0 com.heytap.tas/com.nearme.pay.contract.provider.WalletQuickStartFlagContentProvider
# 或整包：adb shell pm disable-user --user 0 com.heytap.tas
```
> ⚠️ 副作用：整包禁用后双击电源键**什么也不会发生**（实验 E），且钱包不可用。
> `pm disable-user` 对系统组件无效（返回 `new state: default`），要用 `pm disable`。
> 回滚：`adb shell pm enable --user 0 <组件>` / `pm enable --user 0 com.heytap.tas`。

### 回滚（恢复到「会开钱包」的原始状态）

```bash
adb shell am start -n com.heytap.tas/com.finshell.setting.activity.WalletSettingActivity   # 重新打开开关 → 确认
adb shell 'content query --uri content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG'   # 期望 SUPPORT_QUICK_START=true
adb shell settings put secure double_tap_power_button_gesture 1     # 若你原本选的是「钱包」
```

---

## 6. 验证脚本（仓库内已备好）

| 文件 | 用途 |
|---|---|
| `dbl5.sh` / `fastpress.sh` | 双击复现 + 判定（`fastpress.sh` 用**单进程** `input keyevent 26 26`，间隔几十毫秒，才会被判为双击） |
| `dbl4.sh` | 标准双击复现 + 判定（打印 BEFORE/AFTER `ResumedActivity:`、`mCurrentFocus`、相机包出现次数，并直接给出 `>>> RESULT: CAMERA/WALLET OPENED`） |
| `dbl3.sh` / `dbl.sh` / `tapcheck.sh` | 早期版本（注意 `dbl.sh` 不会先按 HOME，会误判） |
| `openact.sh` | 安全启动 Activity（自动处理 `$` 转义：`./openact.sh 'com.android.settings/.Settings$DoubleTapPowerSettingsActivity'`） |
| `press.sh` | root 下用 `sendevent /dev/input/event1` 注入 KEY_POWER（**实测无效**，pmic_pwrkey 丢弃合成事件，仅留作记录） |
| `uidump.sh` | uiautomator dump + 只打印文本节点（定位开关/单选钮的 bounds） |
| `dexmeth.py` | 自写 DEX 方法级分析器：`python3 dexmeth.py <dex> <字符串子串> [--dump]` → 打印含该字符串的方法、const-string、invoke 目标、字段引用 |
| `dexcls.py` | 按类前缀列出某个类/包下的方法及其字符串与调用（`dexcls.py <dex> <类前缀>`） |
| `disasm.py` | 极简反汇编（const/4、const/16、const、const-string、invoke），用于还原门禁判断 |
| `dexsv.py` | DEX `static_values` 解析器（本机 vendor dex 的 static_values 被加密，只能取类名/字段名） |
| `arsc2.py` | resources.arsc 解析器（查资源 ID→名称/取值；FLAG_OFFSET16 稠密块按 `offset=u16×2`、条目 8 字节 `[key u16][flags u16][value u32]`） |
| `wallet.db` / `wallet_mod.db` / `wallet_now.db` / `mmkv.default` | 钱包 DB / MMKV 的本地取证副本 |
| `coloros16-double-tap-power-research.md` | 社区资料：ColorOS 16 厂商键语义（0相机/1钱包/2助手/3快捷应用）与 `KEYLOG_PhoneWindowManagerExtImpl` 日志标签 |

---

## 7. 相机为什么仍然不自动拉起（第二轮深挖：Android 16 真实链路 + 厂商门禁）

> 结论先行：**「双击电源键 → 相机」在这台机器上不是被某条设置关掉的，而是这套 ROM 根本没有可用的相机分支**；
> 唯一真正生效的目标是钱包（钱包自己开关一开就抢）。下面是可以复现的证据链。

### 7.1 Android 16 里相机手势的真实实现（不再是 PowerButtonBehaviorController）

`com.android.server.policy.PowerButtonBehaviorController` 在本 ROM **不存在**；
AOSP 16 把「双击电源键」移到了 `com.android.server.GestureLauncherService`（services.jar）：

```
PhoneWindowManager.interceptKeyBeforeQueueing
  → PhoneWindowManager.handleKeyGesture            (services.jar classes3.dex)
      → SingleKeyGestureDetector.interceptKey      ← 判定是不是「双击」
          → PhoneWindowManager.handleCameraGesture
              → GestureLauncherService.interceptPowerKeyDown
                  → handleCameraGesture → sendGestureTargetActivityPendingIntent → 相机
```

`GestureLauncherService` 的精确门禁（DEX 方法级取证，见 `dexmeth.py` / `disasm.py`）：

| 门禁 | 读取对象 | 本机实测值 |
|---|---|---|
| `isCameraDoubleTapPowerEnabled()` | ROM 资源 bool `17891438` = `0x0111006E` = `config_cameraDoubleTapPowerGestureEnabled` | **true**（从 framework-res.apk 直接读出） |
| `getDoubleTapPowerGestureMode()` | ROM 资源 int `17694859` = `config_doubleTapPowerGestureMode` | **2**（多目标模式） |
| `getDoubleTapPowerGestureAction()` | 资源 int `17694860` = `config_doubleTapPowerGestureMultiTargetDefaultAction`，再叠加 secure `double_tap_power_button_gesture` | 默认 **0**（=相机） |
| `isMultiTargetDoubleTapPowerGestureSettingEnabled()` | secure `double_tap_power_button_gesture_enabled` | 试过 1/2/3/4 均无效 |
| `isCameraDoubleTapPowerSettingEnabled()` | secure `camera_double_tap_power_gesture_disabled` + `Flags.launchWalletOptionOnPowerDoubleTap()` + 上面两项 | 已置 0 |
| 双击计时 | global `power_double_tap_interval`、`power_consecutive_short_tap_count`（另 secure `multi_press_timeout=300`） | null→走 ROM 默认值 |
| 其他 | secure `camera_gesture_disabled` / `gesture.disable_camera_launch` / `emergency_gesture_enabled` / `user_setup_complete` | null / null / null / **1** |

**厂商侧对 AOSP 相机路径的唯一否决点是 Zen 模式**：
`com.android.server.GestureLauncherServiceExtImpl.interceptPowerKeyDownForCamera`（oplus-services.jar classes.dex）
只有 `ZenModeManagerExtImpl.isZenModeOn()` 为真时才拦截，日志串 `'camera blocked by zen mode!'`。
⇒ **钱包/厂商层并没有「吞掉」AOSP 相机事件**（这一条推翻了早期猜测）。

**但 AOSP 这条路在本 ROM 被“特性开关”在 ROM 层关掉了（决定性证据）**：

`GestureLauncherService.isGestureLauncherEnabled()` 的四个来源里，唯一可能成立的是
`Flags.launchWalletOptionOnPowerDoubleTap()`（多目标模式 + `config_cameraDoubleTapPowerGestureEnabled=true`）。
这个 flag 属于 **Quick Access Wallet 特性体系**（framework.jar）：

```
com.android.internal.hidden_from_bootclasspath.android.service.quickaccesswallet.Flags
  ├─ FLAG_LAUNCH_WALLET_OPTION_ON_POWER_DOUBLE_TAP
  ├─ FLAG_LAUNCH_WALLET_VIA_SYSUI_CALLBACKS
  └─ FLAG_LAUNCH_SELECTED_CARD_FROM_QS_TILE
com.android.internal.hidden_from_bootclasspath.android.service.quickaccesswallet.CustomFeatureFlags
  → 特性名（可直接当 key 用）：
    'android.service.quickaccesswallet.launch_wallet_option_on_power_double_tap'
    'android.service.quickaccesswallet.launch_wallet_via_sysui_callbacks'
    'android.service.quickaccesswallet.launch_selected_card_from_qs_tile'
```

本机实测（这条命令块可直接复制）：

```bash
# ROM 里根本没有 Quick Access Wallet 服务 ⇒ AOSP 的「双击→钱包/相机」服务不存在
adb shell 'service list | grep -i quickaccesswallet'          # 无输出
adb shell 'dumpsys activity service com.android.server.quickaccesswallet.QuickAccessWalletService'
# → No services match
# 也没有 aconfig 命令行（feature flags 的官方开关入口被裁掉）
adb shell cmd aconfig                                            # cmd: Can't find service: aconfig
# 只有 feature_flags binder 服务，且它本身是坏的（queryFlags 抛 NPE）
adb shell 'service call feature_flags 4 i32 0'                   # 返回空列表
adb shell 'service call feature_flags 4 i32 1 s16 "android"'     # 抛 NPE：
#   at android.provider.Settings$Config.getStrings → SettingsConfigDataStore.getProperties
# 出厂特性表里也没有这些 flag
adb shell 'grep -c quickaccesswallet /system/etc/aconfig/flag.map'   # 0
```

⇒ 结论：**本 ROM 的 AOSP 双击相机路径在 ROM 层就是关闭的**（特性 flag 关闭 + QuickAccessWallet 服务缺失），
这解释了为什么把所有 Settings 键都调成「相机」也毫无反应。

### 7.2 厂商自己的「相机/快捷应用」分支为什么也用不了

ColorOS 自己实现了一条双击分支（`com.android.server.policy.OplusQuickAppController`），门禁链是：

```
isQuickAppOn() = isQuickAppSupport() && isSwitchOn() && isQuickAppDoublePowerClicked()
isQuickAppSupport() = isSideFingerprintSupport() && isQuickAppFeatureSupport()
  ├─ isSideFingerprintSupport(): SystemProperties.get('persist.vendor.fingerprint.sensor_type') == 'side'
  └─ isQuickAppFeatureSupport(): AppfeatureHelper.isFeatureSupport(ctx, 'com.android.settings.double_tap_power_button_quickapp')
                                 → provider content://com.oplus.customize.coreapp.configmanager.configprovider.AppFeatureProvider
startQuickApp() → isCameraGestureEnabled() → startCamera()   (action android.media.action.STILL_IMAGE_CAMERA, package com.oplus.camera)
```

实测（本机 root 可复现）：

* `persist.vendor.fingerprint.sensor_type` 原值 **`optical`**（不是 `side`）⇒ **本机型（Ace 5 Pro，屏下光学指纹）先天不满足**。
  用 `resetprop persist.vendor.fingerprint.sensor_type side` 伪造后仍然无效（说明还有别的门禁）。
* `com.android.settings.double_tap_power_button_quickapp` 这条特性在 AppFeature 表里**原本没有行**；
  已用 `content insert` 插入 `_id=309 featurename=com.android.settings.double_tap_power_button_quickapp parameters=true`（验证后已删除）。
* 配套 secure 键 `quick_app_double_power_clicked=1`、`camera_double_tap_power_gesture_disabled=0`，
  厂商键 `double_tap_power_button_value` 依次取 0/1/2/3（厂商常量在 vendor dex 的 static_values 里被加密，只能行为反推），
  用「能被识别为双击」的注入方式复测 → **相机仍然没有拉起**（四种取值全部 NOTHING）。

### 7.3 设置页与实际行为「错位」= 本次现象的直接解释

* 本 ROM 的「设置 → 连按两次电源按钮」是 **AOSP 版**（`com.android.settings/.Settings$DoubleTapPowerSettingsActivity`，
  单选钮 `android:id/checkbox`），它只写 **secure `double_tap_power_button_gesture`（0=相机 / 1=钱包）**。
* ColorOS 真正的厂商页是 `com.oplus.settings.feature.convenient.DoubleTapPowerButtonSettingsFragment`，
  它写的是 **secure `double_tap_power_button_value`**（preference key `camera/wallet/ask_alexa/quick_app/none`）。
  但该 fragment 在本 ROM 是**死代码**：manifest 字符串池、resources.arsc、全 APK 的 `new-instance` 都没有它。
* 于是形成错位：**设置页显示「相机」、写的是 AOSP 键；厂商框架读的是另一个键；真正劫持手势的是钱包 App 自己的开关。**
  这就是「设置里明明选了相机，双击却开钱包」的全部原因。

### 7.4 关于注入方式（重要方法论）

* `sendevent /dev/input/event1 1 116 1`（root 亦然）**不产生任何事件**：
  `pmic_pwrkey` 的 evdev 写入被内核丢弃，用 `dd if=/dev/input/event1` 抓包得到 0 字节。
* 可用注入：`adb shell "input keyevent 26 26"`（**同一个 input 进程连发两次**，间隔几十毫秒）——
  这是真正会被判定为「双击」的写法；`adb shell "input keyevent 26; input keyevent 26"`（两个进程）则因间隔 > `multi_press_timeout`（300ms）而漏判。
* 判定双击是否被识别的物理特征：**单按电源键 → 屏幕 Asleep（正常息屏）；双击 → 屏幕保持 Awake 但什么都不启动**
  ⇒ 说明「双击判定成功、后续动作没执行」，这正是厂商延迟息屏机制
  `PhoneWindowManagerExtImpl.sendGoToSleepDelayMessage`（日志 `'send powerPress, interactive='`）造成的观感。

### 7.5 结论与用户侧可行方案

1. **钱包劫持已彻底解决**：关掉钱包 App 自己的「双击电源键唤起快捷服务」后，
   provider `content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG` 变为
   `SUPPORT_QUICK_START=false, HAS_ACTIVE_CARD=false`，双击不再开钱包（已反复验证）。
2. **双击电源键拉起相机在本 ROM/机型上无法用设置强行打开**（AOSP 分支与厂商分支的门禁都试过，见 7.1/7.2）：
   * AOSP 分支（`GestureLauncherService`）虽然 ROM 资源是开着的
     （`config_cameraDoubleTapPowerGestureEnabled=true`、mode=2、default action=0=相机），
     但它依赖 Quick Access Wallet 特性 flag `android.service.quickaccesswallet.launch_wallet_option_on_power_double_tap`，
     而本 ROM **既没有该 flag（`flag.map` 里 0 命中）也没有 QuickAccessWallet 服务**
     （`service list` 无 quickaccesswallet；`dumpsys activity service ...QuickAccessWalletService` → No services match），
     连 `cmd aconfig` 与 `feature_flags` 服务都被裁掉/损坏 ⇒ **AOSP 这条路在 ROM 层就是关的**；
   * 厂商分支要求 `persist.vendor.fingerprint.sensor_type == 'side'`（本机是 **optical**，光学指纹机型），
     且要求 AppFeature 表里有 `com.android.settings.double_tap_power_button_quickapp` 行（本机没有）。
   ⇒ **在这台机器上，双击电源键唯一能打开的目标就是钱包（受钱包自身开关控制），相机无法通过任何设置项恢复。**
   若一定要「按一下就进相机」，建议改用下列任一 ColorOS 原生入口（都与电源键无关、稳定性更好）：
   * **快捷手势 → 双击屏幕拍照**（`com.oplus.gesture` 的 spruce 层，
     provider `content://com.oplus.gestureguide/setting` 与 `.../black/setting`，本机两表都是 `id=1, open_type=0, select_type=1`）；
   * **音量键快拍相机**（厂商 `StrategyVolumeKeyLaunchCamera`，
     开关属性 `oplus.software.camera_volume_quick_launch`，本机该属性为空＝未启用）；
   * **锁屏右下角/侧边快捷入口**。
3. 想恢复「双击电源键开钱包」：钱包 → 设置 → 双击电源键 → 重新打开「双击电源键唤起快捷服务」即可（见 §5 回滚）。


---

## 8. 踩坑清单（本机实测，避免重复踩）

1. **logcat 不可用**：`/system/bin/logd`、`/system/bin/logcat` 是 0 字节桩，`init.svc.logd=stopped`。
   用 `dumpsys activity activities|broadcasts|providers`、`settings`、`content query`、`uiautomator dump` 代替。
2. **Android 16 的前台行是 `ResumedActivity:`**（不是 `topResumedActivity=`）。grep 写错会静默输出空 → 误判「没反应」。
3. **`$` 必须转义**：`adb shell am start -n 'com.android.settings/.Settings$DoubleTapPowerSettingsActivity'`
   在设备端 shell 会展开 `$DoubleTapPowerSettingsActivity` → 变成 `com.android.settings/.Settings`。
   用 `openact.sh`（设备端单引号）最省事。
4. **通知栏/锁屏遮罩会让 uiautomator dump 只返回状态栏**：先 `input keyevent 224`（唤醒）→ `wm dismiss-keyguard`
   → `input swipe 540 1600 540 200`（收起通知栏），再 dump。
5. **屏保/息屏状态**会影响手势复现：`adb shell dumpsys power | grep mWakefulness=`（Awake/Asleep）。
6. **`pm disable-user` 不能禁用系统组件**（返回 `new state: default`），要用 `pm disable`。
7. **`content update` 对 `WalletQuickStartFlagContentProvider` 是静默 no-op**（provider 只读）。
8. **`am force-stop` 会让包进入 stopped 状态**，后续 `am start` 会失败（会伪装成「手势没反应」）。
   用 `am start -f 0x00000020 -n <组件>`（FLAG_INCLUDE_STOPPED_PACKAGES）解除。
9. **重启后 root 会掉**（本机 `adb shell id` 变 uid=2000）：`adb root` 报 `adbd cannot run as root in production builds`，
   `/data/adb` 与 `/system/bin/su` 都不可用；需要用户在 KernelSU（`me.weishu.kernelsu`）里重新给「Shell/ADB」授 root。
   root 丢失后 `content query` 快捷手势 provider 会报 `requires com.oplus.permission.safe.SETTINGS`。
10. **`resetprop` 改 `persist.*` 属性不持久**，重启即回默认值（只对当次运行期内的 system_server 有效，
    而该 prop 又是开机时读的）。
11. **`sendevent` 注入真实按键无效**：本机 `/dev/input/event1` 是 `pmic_pwrkey`，
    `sendevent /dev/input/event1 1 116 1`（root 也会）退出码 0 但**不产生任何事件**
    （`dd if=/dev/input/event1` 抓到 0 字节）；改用 `adb shell "input keyevent 26 26"`（单进程连发两次）。
12. **两次 `adb shell input keyevent 26`（两个进程）会被判为「非双击」**：adb 每次调用开销 200–500ms，
    超过 `multi_press_timeout=300`；必须合成一条命令 `input keyevent 26 26`。
13. **`content query --where "featurename='x'"` 在设备端会被 shell 吃掉引号** →
    `android.database.sqlite.SQLiteException: near ".": syntax error`；改用整表 query 后 grep。
14. **本 ROM 的 logd 是 0 字节残桩**（`init.svc.logd=stopped`，`setprop ctl.start logd` 报
    `PROP_ERROR_HANDLE_CONTROL_MESSAGE (0x20)`），`adb logcat` 永远为空 ⇒ 只能做状态式取证
    （dumpsys / settings / content query / uiautomator）。

---

## 9. 一页速查（最常用的命令）

```bash
# 当前绑定与开关（AOSP 键：设置页写的就是它）
adb shell settings get secure double_tap_power_button_gesture        # 0=相机 1=钱包
adb shell settings get secure double_tap_power_button_gesture_enabled
adb shell settings get secure camera_double_tap_power_gesture_disabled
# 厂商键（厂商框架真正读的，ColorOS 厂商页才会写；本 ROM 设置页不写）
adb shell settings get secure double_tap_power_button_value
# 钱包是否自称「可被双击唤起」
adb shell 'content query --uri content://heytap.tas.quickstart.flag.provider.open/CARD_BAG_FLAG'
# 快捷手势(松果)侧状态（需 root）
adb shell 'content query --uri content://com.oplus.gestureguide/setting'
adb shell 'content query --uri content://com.oplus.gestureguide/black/setting'
# 前台是谁（Android 16 是 ResumedActivity:，不是 topResumedActivity=）
adb shell "dumpsys activity activities | grep -E 'ResumedActivity:'"
# 屏幕是否被识别为双击（单按会息屏，双击会保持亮屏）
adb shell dumpsys power | grep mWakefulness=
# 复现双击（单进程连发两次才会被判定为双击！）
adb shell "input keyevent 26 26"
# 钱包开关页
adb shell am start -n com.heytap.tas/com.finshell.setting.activity.WalletSettingActivity
# 系统双击电源键设置页
./openact.sh 'com.android.settings/.Settings$DoubleTapPowerSettingsActivity'
# 一键判定（CAMERA / WALLET / NOTHING）
./fastpress.sh
```

---

## 10. 本机最终状态（排查结束后已还原/保留的项）

| 项 | 值 | 说明 |
|---|---|---|
| 钱包「双击电源键唤起快捷服务」 | **关闭** | `SUPPORT_QUICK_START=false, HAS_ACTIVE_CARD=false` ⇒ 双击不再开钱包（这就是本次的修复） |
| 钱包包 `com.heytap.tas` | enabled（已用 `pm enable` 恢复，诊断期曾被 `pm disable`） | 钱包本体可正常使用 |
| `secure double_tap_power_button_gesture` | 0 | 设置页「相机」 |
| `secure double_tap_power_button_gesture_enabled` | 0 | AOSP 侧「启用连按两次动作」总闸；本 ROM 的 AOSP 相机路径被特性开关关闭（§7.1），改由 LSPosed 模块接管，此值不影响模块 |
| `secure camera_double_tap_power_gesture_disabled` | 0 | 未禁用相机 |
| `secure double_tap_power_button_value` / `quick_app_double_power_clicked` | 已删除（null） | 诊断期临时写入 |
| `global power_double_tap_interval` / `power_consecutive_short_tap_count` | 已删除（null） | 诊断期临时写入 |
| `persist.vendor.fingerprint.sensor_type` | `optical`（原值） | 诊断期曾用 resetprop 改成 `side`，已还原（resetprop 本就不持久） |
| AppFeature 表 | 已删除诊断期插入的行 `_id=309` | 特性名 `com.android.settings.double_tap_power_button_quickapp` |
| `persist.sys.pkwallet.support` | true（未改） | 框架侧钱包能力开关，诊断期改动无效（开机时读取） |
| LSPosed 模块 `io.github.haperwu.doubletapcamera` | 已安装 / 已启用（`Type: modern`）/ 作用域 = system + com.heytap.tas + android + **com.oplus.camera** | **双击电源键现在直开相机**（见 §11）；回滚：`settings put system doubletap_camera_mode 0` 或停用模块 |
| `system doubletap_camera_volkey` | 1（默认） | 锁屏态相机内「音量键=快门」兜底（§11.12）；0=不接管 |
| `system doubletap_camera_launch_type` | 未设置（默认 `quick_launch_from_framework`） | 传给相机的 `android_camera_launch_type`（§11.12.5） |
| `system doubletap_camera_mode` | 2（默认，= 只在 system_server 生效） | 模块模式位：0 关 / 1 钱包进程 / 2 system_server / 3 都开 |
| `/data/local/tmp` 临时文件 | 已清理 | 诊断期留下的 DB 副本、app_process 探针等已删除（仅保留 `wallet.db.bak` 钱包库备份） |
| 锁屏密码 | **测试用的 PIN 1234 已清除**（`locksettings clear --old 1234` → `deviceLocked=0`） | 测锁屏时临时设置，验证完已还原 |

> 备注：本机 `logd`/`logcat` 曾是 0 字节残桩（`init.svc.logd=stopped`），所有早期验证都改用
> `dumpsys` / `settings` / `content query` / `uiautomator` 的状态式取证；
> **后续某次重启后 logd 恢复正常**（`/system/bin/logd` 766 KB、`init.svc.logd=running`；
> KernelSU 模块 `/data/adb/modules/Logd_Disabler_ColorOS16/boot-completed.sh` 会把它换成残桩），
> 于是可以直接用 `adb logcat` 观察电源键链路（见 §7.1、§11.5）。


---

## 11. 终极方案：LSPosed 模块把双击电源键改成「直开相机」（已实测通过）

### 11.1 为什么必须上 hook
§7.5 已证明：本 ROM 上「双击电源键」**只有厂商的钱包分支能跑通**——
AOSP 的 `GestureLauncherService` 相机分支被 ROM 特性开关关掉（QuickAccessWallet 服务与 flag 都缺失），
ColorOS 自己的「相机/快捷应用」分支要求侧边指纹（本机 `persist.vendor.fingerprint.sensor_type=optical`）。
⇒ 思路：**让钱包分支照常跑起来（把 wallet switch 强制为 1），但把它最后要启动的
`OplusWalletController.startWallet(boolean)` 换成启动相机。**

### 11.2 模块做了什么（三个 hook：两个在 system_server，一个在相机进程）
1. `com.android.server.policy.OplusWalletController.getWalletSwitchState()` → 恒返回 `1`
   （否则 `PhoneWindowManagerExtImpl.sendCheckWalletMessage` 会因 "switch close" 直接放弃，钱包分支根本不触发）。
2. `com.android.server.policy.OplusWalletController.startWallet(boolean)` → **不执行原方法**，
   改为 `startActivity(Intent("android.media.action.STILL_IMAGE_CAMERA").setPackage("com.oplus.camera")
   .addFlags(NEW_TASK|CLEAR_TOP|SINGLE_TOP).putExtra("need_screen_on", true))`
   —— 完全是照抄厂商 `OplusQuickAppController.startCamera` 的做法。

另有可选的「钱包进程内兜底」hook（`Instrumentation.callActivityOnResume`），**默认关闭**，
以免把正常打开钱包（刷卡/通知/QS 磁贴）也改跳相机。

第三个 hook 在**相机进程**内（作用域 `com.oplus.camera`）：
`com.oplus.camera.Camera.onKeyDown(int, KeyEvent)` —— 锁屏快捷启动模式下相机自己的音量键功能
被 ColorOS 禁掉了（§11.12），模块在锁屏时把音量键兜底成「点快门」，解锁态完全不介入。

模式开关：`adb shell settings put system doubletap_camera_mode <0|1|2|3>`
（0=全关 / 1=只钱包进程 / **2=只 system_server（默认）** / 3=都开）。

### 11.3 打包格式：LSPosed 2.x 只认「现代 API」（本次最大的坑）
老格式模块（`assets/xposed_init` + manifest `xposedminversion`）在 LSPosed 2.2.1 里会被判成 legacy
而**根本不会加载**（表现：`lspctl hook-debug dump` → "No process to dump"，模块日志 0 条）。

| 包内文件 | 内容 |
|---|---|
| `META-INF/xposed/java_init.list` | 入口类全名 `io.github.haperwu.doubletapcamera.HookEntry` |
| `META-INF/xposed/module.prop` | `minApiVersion=100` / `targetApiVersion=102` / `staticScope=false` |
| `META-INF/xposed/scope.list` | `system`（=system_server）/ `com.heytap.tas` / `android` / `com.oplus.camera`（相机进程，§11.12 的音量键兜底） |
| `AndroidManifest.xml` | **不要** `xposedminversion`、**不要** `xposedscope` |

> ⚠️ **`system` 这一项不能删**（2026-11-21 实测）：把 scope.list 里的 `system` 去掉、只留 `android`，
> 模块**不会**再被注入 system_server —— 双击电源键什么都不开、日志里一条 `DblTapCam` 都没有，
> 而管理器里又显示「已启用 / 作用域已勾选」，极具迷惑性。
> LSPosed 的作用域里，**「系统框架(system)」与「Android 系统(android)」是两个并列且互相独立的条目**：
> `system` 才是 system_server（我们要 hook 厂商 `OplusWalletController` 的进程），
> `android` 指的是 Android 框架 app（SystemUI 所在包）。
> 判据：重启后 `adb logcat -d | grep DblTapCam` 或 LSPosed 日志里出现
> `module loaded: process=system isSystemServer=true api=102` 才算注入成功；
> 另外 LSPosed 是在开机后约 30 s 才加载模块，太早测试会误判为「没生效」。

入口类必须 `extends io.github.libxposed.api.XposedModule`，
实现 `onSystemServerStarting(SystemServerStartingParam)`（用 `param.getClassLoader()` 找厂商类）
与 `onPackageLoaded(PackageLoadedParam)`。

### 11.4 安装三步（ADB / root）
```bash
cd lsp-module && ./build.sh                     # 产物 build/out/doubletap-camera.apk
adb install -r build/out/doubletap-camera.apk
bash lspdb.sh                                   # 写 LSPosed 配置库：enabled + scope + apk_path
adb reboot                                      # 必须重启：system_server 注入发生在开机阶段
```
`lspdb.sh` 要点：
* LSPosed 2.2.1 的 `lspctl` 只有 `status`/`stop`；要先在管理器「设置 → 调试 → **开发者模式**」打开，
  才有 `module` / `scope` / `hook-debug` 子命令；
* 也可以用 CLI：`lspctl scope add --user=0 io.github.haperwu.doubletapcamera system`（输出 "Scope updated; reboot required"）；
* 配置文件 `/data/adb/lspd/config/modules_config.db`（表：`modules` / `modules_state` / `scope`）；
  **每次重装 APK 后 apk_path 都会变，必须重跑 `lspdb.sh`，否则模块不会被加载**；
* `app_process` 直写这个 SQLite 会被杀（`Bad file descriptor`，没有 binder fd）——改成宿主机 python sqlite3 改库再 push。

### 11.5 验证
```bash
adb shell su -c '/data/adb/modules/zygisk_lsposed/lspctl module show io.github.haperwu.doubletapcamera'
#   期望：API: min=100 target=102 / Type: modern / User 0: enabled
adb shell su -c 'cat /data/adb/lspd/log/modules_*.log' | tail
#   期望：DblTapCam: getWalletSwitchState -> force 1 / startWallet intercepted -> camera (ctx=true)
adb shell input keyevent 3; adb shell "input keyevent 26 26"; sleep 4
adb shell "dumpsys activity activities | grep -E 'topResumedActivity'"
#   期望：topResumedActivity=ActivityRecord{... com.oplus.camera/.Camera}
adb logcat -d | grep -E 'DblTapCam|start wallet|STILL_IMAGE_CAMERA'
#   期望：有 STILL_IMAGE_CAMERA 启动，且 **没有任何 'start wallet'**（钱包完全没被拉起）
```

### 11.6 回滚
```bash
# 1) 最快：关掉模式（hook 每次调用都读这个设置，无需重启）
adb shell settings put system doubletap_camera_mode 0
# 2) 停用模块（管理器里关开关，或 CLI）
adb shell su -c '/data/adb/modules/zygisk_lsposed/lspctl module disable io.github.haperwu.doubletapcamera'
adb reboot
# 3) 彻底卸载
adb uninstall io.github.haperwu.doubletapcamera
```
回滚后系统回到原生行为：**双击电源键 → 钱包**（受钱包自身开关控制）；
想恢复「双击电源键刷卡」，在 钱包 → 设置 → 双击电源键 里重新打开「双击电源键唤起快捷服务」。

### 11.7 构建链踩坑（宿主机只有 JRE 25、无 Android SDK 的环境）
* 编译器用 `org.eclipse.jdt:ecj`（Maven Central 有 `.jar`，直接 `java -jar` 跑）；
* **D8 只能从 build-tools 里取**（`build-tools_r34/lib/d8.jar`），Maven Central 没有 `com.android.tools:r8`（404）；
* `jar` 命令不可用（只有 JRE 没有 JDK）→ 用 python `zipfile` 造 jar / 合并 APK；
* `aapt2` / `apksigner` / `zipalign` 均来自 build-tools_r34；
* D8 **必须逐个传 `.class` 文件**（传目录报 "Unsupported source file type"）；
* 用的 android.jar 是 API16 老包（`com.google.android:android:4.1.1.4`）→ 没有 `Settings.Global`、
  没有 `android.app.AppComponentFactory` → 需要自己补编译期桩（桩只进 stubs.jar，**不进 APK**）；
* `io.github.libxposed.api.*` 的真实签名可以从设备上 pull 的
  `/data/adb/modules/zygisk_lsposed/framework.dex` 反出来（本机用自写 `dexsig.py`）。

### 11.8 本次自研的逆向工具（仓库内）
| 工具 | 作用 |
|---|---|
| `dexmeth.py` | DEX 方法级分析：按字符串定位方法、解码指令流、抽 const-string / invoke / 字段引用 |
| `dexcls.py` | 按类前缀列出方法及其字符串与调用 |
| `dexsig.py` | 打印类的完整方法签名（proto） |
| `dexstatic.py` | 解析 static 字段及其取值 |
| `disasm.py` | 极简反汇编（const / const-string / invoke） |
| `arsc2.py` | resources.arsc 解析（资源 ID → 名称/取值） |
| `lspdb.sh` | 直接改 LSPosed 配置库（启用模块 + 作用域 + apk_path） |

### 11.9 锁屏有密码时相机拉不起来（keyguard 问题）

**现象**：亮屏/解锁状态下双击电源键能直接进相机；**锁屏且设了密码时，相机被启动但落在锁屏后面，
必须先解锁才看得到**（相机 task 起来约 0.1s 后被 CLOSE）。

**定位过程（三层）**：

1. **manifest 层**：`com.oplus.camera.Camera` 其实**声明了** `android:showWhenLocked=true`
   （`aapt2 dump xmltree --file AndroidManifest.xml apk/OplusCamera.apk` 可见），所以并不是「相机没有锁屏能力」。
   真正把它关掉的是相机自己：运行时日志
   `W OCAM_OplusCamera: setShowWhenLocked: false` +
   `D ActivityTaskManager: setShowWhenLocked from:false to false,ActivityRecord{... com.oplus.camera/.Camera}`
   ⇒ **门禁在相机进程内部**，由相机根据「这次启动是谁发起的」决定。
2. **相机进程的反编译取证**（`com.oplus.camera.CameraManager.F1`、`com.oplus.camera.entry.CameraEntry.d`）：
   相机会读三个 intent extra 来判断启动来源
   * `android_camera_launch_type`（String）——与 `'quick_launch_from_framework'` 比较；
   * `extra_key_caller_package_name`（String）——与 `'com.oplus.gesture'` 比较；
   * `com.android.systemui.camera_launch_source`（SystemUI 磁贴路径）。

   启动来源枚举（`CameraEntry.d(String)`）：`gimbal_launch_from_framework`、
   `quick_launch_from_framework`、`quick_launch_from_smart_button`、`watch_launch_from_framework`、
   `spruce_double_tap_launch_from_framework`、`action_button_launch_from_framework`。

   相机自己打的判定日志：`isLockScreenStart, mAction: …, mbSecureStartFromFramework: …,
   mbShowOnKeyguardLocked: …, isDeviceLocked: …`
   ⇒ 我们用 secure 入口启动时，`mbSecureStartFromFramework=false`、`mbShowOnKeyguardLocked=false`，
   所以相机主动 `setShowWhenLocked(false)`。
3. **厂商对照**：ColorOS 侧边键拉相机 `com.android.server.policy.OplusSmartButtonController.startCamera`
   正是「锁屏时用 `STILL_IMAGE_CAMERA_SECURE`，并 `putExtra("android_camera_launch_type", …)`」，
   而 `PhoneWindowManagerExtImpl.startCamera`（厂商「安全相机」入口）反汇编如下：

```java
Intent i = new Intent();
i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);          // 0x10000000
i.putExtra("caller_package", "android");
i.putExtra("mode", 29);
i.putExtra("lunch_type", 2);
i.setAction("android.media.action.STILL_IMAGE_CAMERA_SECURE");
i.setComponent(new ComponentName("com.oplus.camera", "com.oplus.camera.Camera"));
context.startActivityAsUser(i, userId);
```

**模块的修法**（`HookEntry.startCamera`）：

* 锁屏时走 secure 入口，并**补上相机认识的两个 extra**，让相机认定「这是系统手势服务的正规快捷启动」：
  ```java
  si.putExtra("android_camera_launch_type", "quick_launch_from_framework");
  si.putExtra("extra_key_caller_package_name", "com.oplus.gesture");
  ```
* 新增第三个开关 `doubletap_camera_lock_act`（`Settings.System`），用于在「secure 相机」与
  「直拍页」之间 A/B 测试：
  | 值 | 锁屏时的入口 |
  |---|---|
  | 0（默认） | `com.oplus.camera.Camera` + `STILL_IMAGE_CAMERA_SECURE`（+ 上面两个 extra） |
  | 1 | `com.oplus.camera.component.CapturePhotoActivity` + `IMAGE_CAPTURE`（该页 manifest 是 showWhenLocked+turnScreenOn） |
  | 2 | 普通入口 `STILL_IMAGE_CAMERA` |

* 其它开关：`doubletap_camera_secure`（0=自动 1=强制 secure 2=禁用）、
  `doubletap_camera_mode`（0=全关 1=钱包进程 2=system_server（默认） 3=都开）。

```bash
adb shell settings put system doubletap_camera_lock_act 1   # 切到「直拍页」
adb shell settings put system doubletap_camera_lock_act 0   # 切回 secure 相机
```

**验证脚本**（仓库内）：
```bash
bash scripts/locktest.sh      # 锁屏双击 → 看前台 Activity + 日志
bash scripts/lockvariants.sh  # 锁屏下逐个试探 5 种 Intent 写法，看哪种能盖在锁屏上
```
> 注意：注入双击必须用**同一个 input 进程**连发两次：`adb shell "input keyevent 26 26"`；
> 分两次 `adb shell` 的间隔会超过 `multi_press_timeout`(300ms)，判定不成立。
> 另外相机是否肯盖在锁屏上，看日志里 `isLockScreenStart … mbShowOnKeyguardLocked: true` 与
> `ActivityTaskManager: setShowWhenLocked from:false to true`。

**已知边界**：即便相机盖在锁屏上，**按下快门拍照仍可能要求先解锁**——这是 Android 对带密码锁屏的安全策略
（相机可以显示，但拍摄动作需要认证）。若手机支持「锁屏快拍」且要求输入密码，可配合系统的
「锁屏下不输入密码即可拍照」开关使用。

### 11.10 锁屏验证结果（已实测通过 ✔）

测试条件：临时 `locksettings set-pin 1234`（测完已 `locksettings clear --old 1234` 清除），
设备锁屏 → 双击电源键 → 关键日志链：

```
DblTapCam: startWallet intercepted -> camera (ctx=true)
START u0 {act=android.media.action.STILL_IMAGE_CAMERA_SECURE flg=0x10000000 cmp=com.oplus.camera/.Camera}
DblTapCam: camera launched (secure/锁屏路径, locked=true)
W OCAM_OplusCamera: setShowWhenLocked: true              ← 相机不再关闭锁屏显示
D ActivityTaskManager: setShowWhenLocked from:false to true
OCAM_CameraEntry: parseIntent, mCameraEntryType: 1, mCallPkg: com.oplus.gesture,
                  mAction: android.media.action.STILL_IMAGE_CAMERA_SECURE
OCAM_CameraEntry: isLockScreenStart, ... mbSecureStartFromFramework: true,
                  mbShowOnKeyguardLocked: false, isDeviceLocked: true
```

关键点：`mbSecureStartFromFramework` 由 **false 翻成 true**，正是靠补上的
`android_camera_launch_type=quick_launch_from_framework` +
`extra_key_caller_package_name=com.oplus.gesture` 这两个 extra；
相机随之调用 `setShowWhenLocked(true)`，于是**直接盖在 keyguard 之上**。

实测结论：
* 锁屏（带密码）双击电源键 → `topResumedActivity=ActivityRecord{… com.oplus.camera/.Camera}`，
  `mKeyguardOccluded=true`、`deviceLocked=1`，屏幕直接显示**相机取景界面**（专业/视频/照片/人像/更多 + 快门），
  **不再需要先解锁**（截图见 `build/locktest.png`）。
* 解锁态双击 → 同样直接进相机（普通 action `STILL_IMAGE_CAMERA`，flg=0x34000000）。
* 两种状态下钱包都**一次都没有被拉起**（logcat 里 `start wallet` 计数 = 0）。

> 复测时注意：模块的 `getWalletSwitchState -> force 1` 会让框架**无视钱包开关的去向**，
> 始终走 `startWallet()` → 被我们改写成启动相机。
> 也就是说：**模块生效与「钱包自带开关」是否关闭无关**，两条链路互不依赖。


### 11.11 「锁屏后相机内音量键功能用不了」的定位结论（重要：不是模块造成的）

用户反馈：**锁屏双击电源键打开相机后，相机里的音量键功能失效**（解锁后正常）。

#### 11.11.1 先把「音量键功能」到底是什么查清楚

相机的音量键功能存在自己的 MMKV 里（不是 Settings）：

```bash
adb shell su -c "grep -ao 'pref_volume_key_function_key.\{0,12\}' \
  /data/data/com.oplus.camera/files/mmkv/com.oplus.camera_preferences"
# → pref_volume_key_function_key  shutter      ← 本机取值 = shutter（快门）
# 另有 pref_shoulder_key_function_key = off
```

对照相机资源名：`camera_volume_key_function_{shutter,zoom,volume}`、
`volume_key_function_values/names`、`volume_button_function_title`。
所以本机「音量键功能」= **快门**（按音量↑/↓ = 拍照），**不是变焦**——
用「缩放条有没有变」来判断会得出错误结论。

#### 11.11.2 事件确实送到了相机（锁屏与解锁都有）

```
W OCAM_OplusCamera: Key down has been intercepted
W OCAM_OplusCamera: Key up has been intercepted
```

来源 `Lcom/oplus/camera/Camera;->onKeyDown`（反汇编：只打日志并 `super.onKeyDown`，
真正的音量键动作在相机 UI 层处理）。锁屏态与解锁态**都收到**，
所以不是「事件没送达」。

#### 11.11.3 关键对照实验：与模块无关

用**正常方式**（从桌面图标）启动相机，再按音量↑，**同样没有快门动作**：

```bash
adb shell am start -n com.oplus.camera/.Camera   # 正常启动（非模块路径）
adb shell input keyevent 24                       # 注入音量↑
# 相机日志：只有 'Key down has been intercepted'，没有
#   OCAM_CameraControlUI: onShutterButtonClick
#   OCAM_CommonCapMode: onCameraShutterButtonClick
#   OCAM_g1_BaseMode: CameraTest Shutter Respond Start
```

对比「点按快门按钮」时相机会打出上面那三行日志（可用作拍照是否发生的签名）。
⇒ **锁屏相机音量键失效不是 LSPosed 模块引入的**；ADB 的 `input keyevent`
与真实按键不等价（没有 scanCode / deviceId），注入事件无法触发相机的音量键动作。

#### 11.11.4 结论与验证方法

* 模块侧无需改动：模块只负责「把双击电源键的启动目标从钱包换成相机」，
  相机内部行为与它无关。
* 要判定「锁屏到底是不是真的不能用」，必须用**真实音量键**验证：

```bash
bash scripts/volume-key-check.sh locked      # 锁屏场景，脚本会提示你按真实音量↑
bash scripts/volume-key-check.sh unlocked    # 解锁场景，对照组
```

脚本会自动输出：按键是否送达相机、是否触发快门（按上面三行日志判定）、
`isLockScreenStart / mbSecureStartFromFramework / isDeviceLocked` 标志、缩放条前后对比。

* 若真实按键在解锁态能拍照、锁屏态不能，那就是 **Android 对带密码锁屏的安全策略**
  （相机可显示，但拍摄需要认证）——这时可考虑系统自带的「锁屏快拍 / 锁屏下不输入密码即可拍照」
  开关；或改用更轻的入口（下面 11.11.5）。
* 若真实按键在锁屏态也能拍照，则此前的现象只是 ADB 注入的假象。

#### 11.11.5 备选入口：`doubletap_camera_lock_act`

模块提供的 `Settings.System "doubletap_camera_lock_act"`：

| 值 | 锁屏时启动的 Activity | 说明 |
|---|---|---|
| 0（默认） | `com.oplus.camera/.Camera`（action `STILL_IMAGE_CAMERA_SECURE`） | 完整相机界面 |
| 1 | `com.oplus.camera/.component.CapturePhotoActivity` | 厂商的「直拍页」，manifest 带 `showWhenLocked` + `turnScreenOn` + action `IMAGE_CAPTURE`，界面更轻 |
| 2 | `com.oplus.camera/.Camera`（普通 action） | 兜底 |

```bash
adb shell settings put system doubletap_camera_lock_act 1
adb shell input keyevent 26 26      # 锁屏双击 → CapturePhotoActivity
adb shell settings put system doubletap_camera_lock_act 0   # 还原
```
实测：值=1 时锁屏双击确实进入 `com.oplus.camera/.component.CapturePhotoActivity`（已验证）。

---

### 11.12 锁屏态「相机内音量键功能」失效的根因与模块兜底（已实测通过 ✔）

#### 11.12.1 现象

锁屏（有密码）双击电源键 → 相机直接盖在锁屏上（§11.10 ✔），但**相机里的音量键功能没反应**
（本机「音量键功能」= 快门，见 §11.11.1：相机 MMKV `pref_volume_key_function_key` = `shutter`）。

#### 11.12.2 根因：ColorOS 相机的「锁屏快捷启动」模式，与启动入口无关

锁屏启动相机时，相机会进入**锁屏快捷启动模式**，标志是相机自己的日志：

```
D OCAM_EventMessageUIContainerContext: setLockScreenStart: true     ← 锁屏双击启动
D OCAM_EventMessageUIContainerContext: setLockScreenStart: false    ← 正常启动（解锁态）
V OCAM_CameraEntry: isLockScreenStart, mAction: ..., mbSecureStartFromFramework: ..., mbShowOnKeyguardLocked: ...
```

该模式下相机**自己的音量键监听没有生效**：音量键事件其实送到了相机
（`W OCAM_OplusCamera: Key down has been intercepted`），但没有任何快门/变焦动作
（缺 `OCAM_CameraControlUI: onShutterButtonClick` / `OCAM_CommonCapMode: onCameraShutterButtonClick` /
`OCAM_g1_BaseMode: CameraTest Shutter Respond Start`）。

**关键实验：换启动入口没用。** 设备锁定（`deviceLocked=1`）时冷启动相机，四种入口对比：

| 入口 | 结果 |
|---|---|
| `STILL_IMAGE_CAMERA_SECURE`（secure 相机，默认） | `setLockScreenStart: true` |
| 普通 action `STILL_IMAGE_CAMERA` | `setLockScreenStart: true` |
| `CapturePhotoActivity`（直拍页） | `setLockScreenStart: true` |
| `android_camera_launch_type=spruce_double_tap_launch_from_framework` | `setLockScreenStart: true` |

⇒ 这个模式由**设备是否处于锁屏**决定（相机 `onCreate` 里读 keyguard 状态：
`Lm5/c9;->get` 会打印 `onCreate, this: ..., isKeyguardLocked: ..., isSpruceOrActionLaunch: ...`），
不是由 Intent / extra 决定的 ⇒ **不是模块造成的，也换不掉**。

##### ⚠ 重要更正（真机按键复测后）

* **ADB 注入的音量键在「解锁 + 普通 action 启动」的相机里同样不会触发快门**
  （`onShutterButtonClick` 计数 = 0）。⇒ 注入事件与真实按键不等价，
  **任何用 `input keyevent 24` 得出的「解锁态音量键正常」结论都不成立**，只能真机按键验证。
* 模块第一版用 `KeyguardManager.isKeyguardLocked()` 作为兜底触发条件是**错的**：
  相机启动时会主动 dismiss keyguard——

  ```
  I ActivityTaskManager: Activity requesting to dismiss Keyguard: ActivityRecord{... com.oplus.camera/.Camera}
  V FlexibleTaskController: notifyKeyguardStateChanged keyguardShowing = false
  ```

  （没有锁屏凭据时 keyguard 直接被 dismiss ⇒ `isKeyguardLocked()` 变成 **false**
  ⇒ 兜底分支永远进不去 ⇒ 用户真机按音量键「还是不行」）。
* 真正的判据不是「现在锁没锁屏」，而是「**相机的原生音量键处理这次有没有真的触发快门**」。

#### 11.12.3 模块兜底：第三个 hook（相机进程内）+ 快门计数自校准

模块新增作用域 `com.oplus.camera`，在相机进程里 hook 两个方法：

| # | hook 目标 | 作用 |
|---|---|---|
| 1 | `com.oplus.camera.ui.control.CameraControlUI$f.d(ShutterButton, int)` | 相机**快门处理入口**（打印 `onShutterButtonClick, ShutterButton.id: …`），每触发一次就 `sShutterCount++` |
| 2 | `com.oplus.camera.Camera.onKeyDown(int, KeyEvent)` | 音量键事件（打印 `Key down has been intercepted`） |

`onKeyDown` 里的判定顺序：

1. 键码是 `KEYCODE_VOLUME_UP/DOWN`，否则放行；
2. `Settings.System doubletap_camera_volkey`（默认 1）为 0 则放行；
3. 相机自己的「音量键功能」必须是 `shutter`（读相机 MMKV `files/mmkv/com.oplus.camera_preferences`
   的 `pref_volume_key_function_key`，MMKV 字节布局 `[keyLen][key][valLen][valType][value…]`），
   否则放行（用户改成 zoom/volume 时不接管）；
4. **自校准**：`chain.proceed()` 前后比较 `sShutterCount`
   * 计数**增加** ⇒ 相机的原生音量键处理这次真的触发了快门（解锁态正常）⇒ **不重复点击**（避免连拍两张）；
   * 计数**没变** ⇒ 原生处理这次是哑的（锁屏快捷启动模式）⇒ 在视图树里找类名含 `ShutterButton` 的 View
     （`com.oplus.camera.control.MainShutterButton`）并 `performClick()`，走相机**自己的快门逻辑**。

关键点：**不再用 `isKeyguardLocked()` 判断**，因此相机自己 dismiss 掉 keyguard 之后依然能兜底；
同时因为有快门计数，解锁态原生功能正常时不会多拍一张。

#### 11.12.4 验证（锁屏态真实链路日志）

```bash
adb shell am force-stop com.oplus.camera
adb shell input keyevent 26            # 息屏 -> 锁屏
adb shell input keyevent 224           # 亮屏
adb shell "input keyevent 26 26"       # 锁屏双击 -> 相机盖在锁屏上
adb logcat -c
adb shell input keyevent 24            # 音量↑（注入只验证兜底链路；真机按键才有代表性）
adb logcat -d | grep -E "DblTapCam|Shutter|intercepted"
```

期望日志链：

```
W OCAM_OplusCamera: Key down has been intercepted
I DblTapCam: volume key fallback -> shutter click (com.oplus.camera.control.MainShutterButton)
E OCAM_CameraControlUI: onShutterButtonClick, ShutterButton.id: 2131297655
W OCAM_CommonCapMode: onCameraShutterButtonClick
E OCAM_g1_BaseMode: CameraTest Shutter Respond Start, count: 0
```

若原生路径生效（解锁态），则应看到 `I DblTapCam: volume key handled natively (shutter N -> N+1)`，
且**不会**出现 `volume key fallback`。

#### 11.12.5 新增开关

| 设置 | 值 | 说明 |
|---|---|---|
| `system doubletap_camera_volkey` | 0 / 1（默认 1） | 锁屏态音量键是否兜底成快门；0=完全不接管 |
| `system doubletap_camera_launch_type` | 默认 `quick_launch_from_framework` | 传给相机的 `android_camera_launch_type`（可试 `spruce_double_tap_launch_from_framework` 等，实测都进锁屏快捷启动模式） |

#### 11.12.6 已知边界

* 锁屏带密码时，按下快门本身是否需要认证，取决于系统「锁屏快拍 / 免密拍照」策略；
  本兜底只解决「音量键 = 快门」在锁屏快捷启动模式下不生效的问题。
* 相机若把「音量键功能」改成 `zoom` / `volume`，模块不接管（只处理 `shutter`）。

#### 11.12.7 真机按键复测结果（已通过 ✔）

设备端常驻抓日志后，用**真实按键**（不是 ADB 注入）压测：

```bash
adb shell su -c "logcat -v threadtime -s DblTapCam OCAM_OplusCamera OCAM_CameraControlUI \
  OCAM_g1_BaseMode OCAM_CommonCapMode ActivityTaskManager > /data/local/tmp/vk2.log &"
# 锁屏双击电源键 -> 相机盖在锁屏上 -> 手动按音量↑若干次
```

日志解析结果（`build/vk2.log`，877 行）：

| 指标 | 数量 |
|---|---|
| `Key down has been intercepted`（音量键到达相机） | 14 |
| `volume key fallback -> shutter click`（模块兜底） | 14 |
| `onShutterButtonClick`（快门真的被点下） | 14 |
| `volume key handled natively`（原生分支） | 0 |

**14 次按键 → 14 次兜底 → 14 次快门动作，严格 1:1**：既不漏拍也不连拍 ✔
（其中 15:03:11.706 / 15:03:11.940 相隔 234 ms 连按两次，各自对应一次快门，无叠加）。

另外，锁屏双击启动相机的完整链路在真实按键下同样成立：

```
I DblTapCam: camera launched (secure/锁屏路径, locked=true)
D ActivityTaskManager: setShowWhenLocked  from:false to true,ActivityRecord{... com.oplus.camera/.Camera t416}
W OCAM_OplusCamera: setShowWhenLocked: true
```

> 注：本机（PKR110 / ColorOS 16 / 光学指纹）相机的**原生**音量键快门分支始终没有接管
> （`handled natively` = 0），即锁屏快捷启动模式下音量键确实收不到快门动作 ——
> 这正是兜底逻辑存在的意义；若将来某次升级让原生分支生效，模块会自动改为放行而不再重复点击。

---

### 11.13 「锁屏双击打开的相机只能拍一张照片」的根因与修复（已定位 ✔）

#### 11.13.1 现象

锁屏双击电源键拉起的相机：按快门 / 音量键，**第一张出不来或出不来第二张**，
`/sdcard/DCIM/Camera/` 里没有新文件；连按第二下时相机直接报
`capture, failed to send request`。

#### 11.13.2 先排除「不是模块的锅」

| 对照实验 | 结论 |
|---|---|
| 模块兜底链路日志齐全（`volume key fallback -> shutter click` → `onShutterButtonClick`） | 事件与快门动作都正常触发 |
| 用 uiautomator 找到 `content-desc="快门"`（bounds `[423,1944][657,2178]`）**直接点屏幕快门** | **同样不出图** ⇒ 与音量键兜底无关，是相机自身没完成拍照 |
| 解锁后用普通入口启动相机再点快门 | **正常出图**（`IMG2026xxxx.jpg` + `onFinishAddFrame, complete capture, ID: 1`）⇒ 相机硬件/HAL 没问题 |
| 解锁后用 `_SECURE` action 启动相机再点快门 | **正常出图** ⇒ 与 `_SECURE` action 本身无关 |

⇒ 变量只剩「**启动时设备处于锁屏**」这一个。

#### 11.13.3 根因：厂商「安全相机」的两个 extra

模块最初照抄了厂商 `com.android.server.policy.PhoneWindowManagerExtImpl.startCamera`
（ColorOS 自己拉「安全相机」的入口）的完整参数：

```java
i.putExtra("caller_package", "android");
i.putExtra("mode", 29);          // ← 元凶之一
i.putExtra("lunch_type", 2);     // ← 元凶之一
i.setAction("android.media.action.STILL_IMAGE_CAMERA_SECURE");
```

把 extra 逐个做二分（锁屏下启动 → 点一次快门 → 看有没有 `complete capture` + 文件）：

| 启动参数（都带 `android_camera_launch_type=quick_launch_from_framework`） | 拍照完成 | 出图 |
|---|---|---|
| 仅 `action=_SECURE` | ✅ `complete capture, ID: 1` | ✅ |
| `+ caller_package=android` | ✅ | ✅ |
| `+ extra_key_caller_package_name=com.oplus.gesture` | ✅ | ✅ |
| **`+ mode=29`** | ❌ `capture, failed to send request` | ❌ |
| **`+ lunch_type=2`** | ❌ `capture, failed to send request` | ❌ |
| `+ mode=29 + lunch_type=2`（= 修复前的模块） | ❌ | ❌ |

**结论**：`mode=29` / `lunch_type=2` 是厂商「安全相机」专用参数，带上后 ColorOS 相机会把拍照
管线切到受限模式（`OCAM_CaptureProcessor: isReadyToCapture, foreground capture: 1`、
`OCAM_AutoLogHelper: tryCatchCaptureFailedLog, reason: CF_FOREGROUND_CAPTURE`、
`CameraUnit, ApsProcessor: onAddPreviewFrameBuffFail` 刷屏），
表现就是「快门响应了但不出图 / 只能拍一张」。

> 这两个 extra 是「谁在拉相机 + 以什么业务模式拉」的业务参数，相机侧会据此走
> 「由系统代拍/受限」的分支；我们只是模拟系统手势，并不具备那条业务链路，
> 所以带了反而把相机推进去死胡同。

#### 11.13.4 修复

模块的 secure 启动路径**去掉 `mode` 与 `lunch_type`**，只保留：

```
action                        = android.media.action.STILL_IMAGE_CAMERA_SECURE
component                     = com.oplus.camera/.Camera
caller_package                = android
android_camera_launch_type    = quick_launch_from_framework
extra_key_caller_package_name = com.oplus.gesture
flags                         = FLAG_ACTIVITY_NEW_TASK
```

这三个 key（`android_camera_launch_type` + `extra_key_caller_package_name`）必须留着 ——
相机靠它们判断「是不是系统/手势服务的正规快捷启动」，
从而在锁屏时调用 `setShowWhenLocked(true)` 把相机盖在 keyguard 之上
（去掉后相机会落在锁屏后面，必须先解锁才能看到）。

#### 11.13.5 验证

```bash
# 锁屏 → 双击电源键 → 相机盖在锁屏上 → 连点 3 下快门
adb shell "input keyevent 26 26"; sleep 6
adb shell input tap 540 2061; sleep 3
adb shell input tap 540 2061; sleep 3
adb shell input tap 540 2061; sleep 3
adb shell "ls -lt /sdcard/DCIM/Camera/ | sed -n '2,4p'"

# 期望：3 个新文件 + 日志里 3 次
#   OCAM_CaptureProcessor: onFinishAddFrame, complete capture, ID: n
#   （不再出现 capture, failed to send request）
```

> ⚠️ 注入的音量键不会触发快门（见 §11.11.3），验证拍照请**点屏幕快门**或用真机音量键。

#### 11.13.6 实测验证结果（已通过 ✔）

修复后（模块 v1.0.3，APK SHA-256 `7716da68f0d87d6eb1961e4e5a93de50645856c70dd83facdac1809422a00f47`）：

| 场景 | 结果 |
|---|---|
| 锁屏双击 → 相机 | ✔ `topResumedActivity=ActivityRecord{... com.oplus.camera/.Camera}` |
| 锁屏连点 3 下快门 | ✔ **3 张照片全部落盘**（`IMG20261121191837/1841/1844.jpg`），日志 3 次 `onFinishAddFrame, complete capture, ID: 1/2/3` |
| **带密码锁屏**（`locksettings set-pin 1234`）双击 | ✔ 相机仍盖在 keyguard 之上：`setShowWhenLocked from:true to true` + `mbShowOnKeyguardLocked: true` + `isKeyguardShowing=true`，且照片正常落盘（`IMG20261121191923.jpg` + `complete capture, ID: 1`） |
| 锁屏态音量键（快门功能） | ✔ 模块兜底仍生效：`volume key fallback -> shutter click` → `onShutterButtonClick` |
| 解锁态双击 | ✔ `com.oplus.camera/.component.CameraImageActivity` |
| 钱包是否被拉起 | ✔ 全程 0 次（`grep -c "start wallet"` = 0） |

> ⚠️ 本次修复**没有**改变「谁先谁后」：模块仍然强制 `getWalletSwitchState()=1`，
> 让 ColorOS 走到 `startWallet()`，再把这次启动改写成相机；
> 钱包自身的「双击电源键唤起快捷服务」开关保持关闭（provider 报 `SUPPORT_QUICK_START=false`）。

> 📌 顺带加固了 `lspdb.sh`：写回 LSPosed 配置库前会检查 `modules/modules_state/scope`
> 三张表是否存在，设备上的库被写坏时回退到本地备份 `mc.db.lastgood`，
> 没有备份就直接中止（避免再次出现「模块静默不加载」）。
