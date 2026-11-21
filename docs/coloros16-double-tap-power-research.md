# ColorOS 16 「双击电源键」→ 钱包 (com.heytap.tas) instead of 相机 — research brief

**Target device:** OnePlus Ace 5 Pro, model `PKR110`, Android 16, ColorOS 16 CN build `PKR110_16.0.0.204(CN01)`.
**Scope:** web-only research (no device access). Compiled 2026-11-21.
**Source labels used below:** `[VENDOR DOC]` = OPPO/OnePlus/Google/AOSP official docs or source · `[GITHUB]` = community repo / source dump · `[REDDIT]` · `[FORUM]` · `[BUG REPORT]` · `[MEDIA]` · `[GUIDE]` = low-authority third-party how-to · `[INFERENCE]` = my reasoning, not sourced.

---

## 0. Bottom line

* On ColorOS the double-press-power action is **not** the AOSP camera gesture. It is an OPPO/OnePlus framework feature implemented in the Oplus `PhoneWindowManager` extension (log tag `KEYLOG_PhoneWindowManagerExtImpl`), driven by the **OEM Secure setting `double_tap_power_button_value`**: `0` = 相机 (Camera), `1` = 钱包 (Wallet), `2` = 助手 (Assistant), `3` = 快捷应用 (Quick app). `[GITHUB]`
* The “Wallet” target on Chinese ROMs is the preinstalled **钱包 app `com.heytap.tas`** — specifically `com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity` (NFC/刷卡/公交码 surface). Some builds instead try to launch `com.heytap.wallet`, a package that is usually **absent** on CN ROMs. `[GITHUB]`
* So “钱包 takes over instead of 相机” is **not a bug in the classic sense — it is a selectable target**: `double_tap_power_button_value` = 1. It *also* fails to open the camera after firmware updates because OEM updates have reset this key / removed the shortcut (documented for OxygenOS 16 / ColorOS 17 on OnePlus 15).
* AOSP has a parallel, independent mechanism: `Settings.Secure.double_tap_power_button_gesture` (`0` = Camera launch, `1` = Wallet launch) plus `double_tap_power_button_gesture_enabled` and `camera_double_tap_power_gesture_disabled`, surfaced in AOSP Settings as **Gestures → “Double tap power button”** (Android 16). **Changing those AOSP keys does not change the ColorOS action** (explicitly stated in the community repo). `[AOSP SOURCE] [MEDIA]`

---

## 1. UI path for the double-tap-power binding and the allowed targets

| Source type | Path / targets | URL |
|---|---|---|
| `[GUIDE]` (third-party Chinese how-to for OPPO A3 Pro on ColorOS 16, 2026-09-25) | `设置 > 系统设置 > 手势体感 > 快捷启动 > 双击电源键 > 相机`; mentions other possible targets (手电筒 / 录音) | https://www.oppozhijia.com/wz/1067572.html |
| `[VENDOR DOC]` (ColorOS 16.0 User Manual, EN) | The manual documents **no** double-press-power binding at all. It documents `设置/设置 > 其他设置 > 手势体感` and `设置 > 辅助功能与便捷工具 > 手势体感 > 熄屏手势` (Double tap to turn on/off screen, Draw an **O** to open camera, Draw a V for flashlight, two-finger tap for media) and `设置 > 其他设置 > 电源键 > 长按电源键 → 电源菜单 / 语音助手`. | https://m.media-amazon.com/images/I/A1jX9eLPpYL.pdf |
| `[GITHUB]` | Allowed target set on CN ColorOS 16 (OPPO PMA120, `PMA120_16.0.9.402(CN01)`): `0` 相机, `1` 钱包, `2` 助手, `3` 快捷应用 — i.e. exactly **4 hard-coded OEM targets**, no free “pick any app”. | https://github.com/Nielk74/coloros-power-button-launcher |
| `[REDDIT]` (r/Oppo, 2026-05-20) | User states ColorOS “only offers **Camera** or **Access Card**”, and “the gesture handler is hard-coded to 4 packages, one of which (com.heytap.wallet, Oppo’s …)”. | https://www.reddit.com/r/Oppo/comments/1tirila/make_the_doublepress_power_button_open_google/ |
| `[MEDIA]` (Douyin, 2026-01-19, rooted OnePlus on ColorOS 16) | Demonstrates **游戏助手 (Game Assistant)** being used as the double-tap-power target on ColorOS 16 — consistent with the `2 = 助手` slot. | https://www.douyin.com/video/7597030239176470763 |
| `[GUIDE]` (TechBone, OnePlus/OxygenOS, low authority) | “Double click the power button” → **Camera** or **None**; on OnePlus the page lives in the system-wide button/gesture settings; Reddit adds that on OnePlus the toggle sits in the **accessibility** section and **does not persist across reboot**. | https://www.techbone.net/oneplus/smartphone/double-click-the-power-button-starts-camera · https://www.reddit.com/r/OnePlusOpen/comments/1poi89m/double_click_camera_launch_settings_dont_stick/ |
| `[FORUM]` (OnePlus BBS, 2021) | Older CN path for the *screen* gesture: `设置 - 基础功能 - 便捷工具 - 手感体验 - 黑屏手势 - 画 O 快速启动相机`. | https://bbs.oneplus.com/thread/5899561?mod=viewthread&page=1&tid=5899561 |
| `[MEDIA]` (今日头条, ColorOS 16 tip round-ups) | ColorOS 16 gesture hubs: `设置 → 便捷工具 → 黑屏手势` (画O 打开相机, 画V 手电筒, 双击屏幕亮屏) and `设置 → 快捷与辅助 → 智能体感 → 双击机身背部` (截屏 / 启动相机 / 调出收付款码). | https://www.toutiao.com/article/7610242001342054964/ · https://www.toutiao.com/article/7601314615758193188/ · https://www.toutiao.com/article/7610250908928148020/ · https://www.toutiao.com/article/7626221452244664867/ |

**Not confirmed (flagged):**
* I could **not** find an **official OPPO/OnePlus CN documentation page** (coloros.com 使用技巧 / oppo.com support / manual) that lists the ColorOS 16 “双击电源键启动” screen and its option list. `coloros.com` 使用技巧 pages are client-rendered and their API (`https://www.coloros.com/api/colorOS/business/article/detail/{id}` etc.) returned 404/500/“必填项不能为空”, so the official tree could not be retrieved.
* The exact CN menu label for ColorOS 16 is uncertain across third-party sources (“系统设置 → 手势体感 → 快捷启动”, “特色功能 → 手势体感 → 黑屏手势”, “其他设置 → 快捷手势”). **Verify on-device** (Settings search for “双击” / “电源键” is the fastest route).
* Whether `PKR110_16.0.0.204(CN01)` ships the 4-target picker at all, and whether 钱包 is listed there, is **unconfirmed** for this exact build.

---

## 2. Wallet taking over the double-tap-power gesture (and known regressions)

| Source type | Finding | URL |
|---|---|---|
| `[GITHUB]` | The repo was created because “OPPO firmware **hard-wires the gesture to Wallet** and does not expose a normal app picker”. On the tested CN build the power policy launches `com.heytap.tas/com.nearme.wallet.nfc.ui.NfcConsumeActivity`; on other builds it launches the (missing) `com.heytap.wallet`. | https://github.com/Nielk74/coloros-power-button-launcher |
| `[GITHUB]` (CN fork) | `yqia03/coloros-wallet-bridge` keeps the factory “双击电源键打开钱包” behaviour *and* the 钱包 app working, by redirecting the OEM wallet activity with an AccessibilityService; tested on 国行 OPPO Find X9 (ColorOS 16.0.10.502 / 17.0.0.101). | https://github.com/yqia03/coloros-wallet-bridge · https://github.com/yqia03/coloros-wallet-bridge/blob/main/docs/使用说明.md |
| `[GUIDE]` (Baidu 经验, OPPO Reno3 / ColorOS 12.1 / 钱包 5.6.1) | The **钱包 app itself** has a toggle “**双击电源键打开刷卡**” at `钱包 → 我的(右下角) → 右上角齿轮(设置)`; the article is literally a complaint that locking the screen with the power key accidentally opens the 刷卡 page and that the switch is hard to find. | https://jingyan.baidu.com/article/148a1921d8f4e30c71c3b1f5.html · related: https://jingyan.baidu.com/article/d8072ac4beb3c3ad95cefd98.html |
| `[BUG REPORT]` (OnePlus BBS, 2025-03-14) | Title: “偶发BUG，解锁手机莫名进去公交卡” (unlock → inexplicably enters the bus/transit card). Body not retrievable (JS shell). | https://bbs.oneplus.com/thread/1816403599089991687 |
| `[REDDIT]` (r/oneplus, 2026-10-30, 23 pts / 15 comments) | “**Fix for OnePlus 15 double-click power to open Camera in ColorOS 17**” — “the recent ColorOS 17 update broke the shortcut which let you quickly open (camera)”. | https://www.reddit.com/r/oneplus/comments/1xjc1l0/fix_for_oneplus_15_doubleclick_power_to_open/ |
| `[REDDIT]` (r/TheOnePlus15, 2026-10-28) | “ColorOS 17: ‘Double-press power → Camera’ is **enabled but doesn’t work**” after an OxygenOS 16 → ColorOS 17 switch. | https://www.reddit.com/r/TheOnePlus15/comments/1xi1xpj/coloros_17_doublepress_power_camera_is_enabled/ |
| `[FORUM]` (OnePlus community, 2025-11-15) | “PSA: Double-tap power button is **gone with OxygenOS 16**. Here’s how to get it back”. Body is geo-blocked for mainland-China IPs (“自2024年5月31日起，中国大陆用户将无法访问海外社区”) → **content unconfirmed**. | https://community.oneplus.com/thread/1994755344798056452 |
| `[FORUM]` (Facebook OnePlus flagships, 2025-12-10) | After an OxygenOS update the “power button double click → camera” setting resets to default (users report the same on OnePlus 15). | https://www.facebook.com/groups/oneplusflagships/posts/3413642308784546 |
| `[MEDIA]` (DroidWin, updated 2025-09-08) | “Many users on the Indian ROM have reported that OnePlus has removed the double-click Power button shortcut to open the Camera app… there does exist a method … though with a catch.” Body fetch blocked → **details unconfirmed**. | https://droidwin.com/how-to-enable-double-click-power-button-for-camera-on-oneplus |
| `[VENDOR DOC]` (competitor, for mechanism comparison) | Huawei Wallet ships the identical design: `双击电源键唤起刷卡界面` (设置方法 in Huawei Wallet → 我的 → 设置), incl. “双击电源键优先唤起银行卡刷卡界面” priority behaviour. | https://consumer.huawei.com/cn/support/content/zh-cn00716027/ |

**Not confirmed:** I found **no** ColorOS **15/16 CN**-specific public bug report titled “wallet replaces camera”, and **no** report proving an involuntary wallet takeover on a CN Ace 5 Pro build. The Chinese evidence is: (a) the Wallet app’s own “双击电源键打开刷卡” switch `[GUIDE]`, (b) the OEM target slot `1 = 钱包` `[GITHUB]`, (c) the BBS “莫名进去公交卡” title `[BUG REPORT]`. The “regression” reports found are all **OxygenOS 16 / ColorOS 17 on OnePlus 15 (EU/US)** and concern the *camera* side, not the wallet side.

---

## 3. Setting keys that govern the gesture

### Confirmed

| Key | Namespace | Meaning | Source |
|---|---|---|---|
| `double_tap_power_button_value` | `Settings.Secure` (OEM) | **0 = 相机, 1 = 钱包, 2 = 助手, 3 = 快捷应用** — the key that actually selects the ColorOS double-tap-power target | `[GITHUB]` https://github.com/Nielk74/coloros-power-button-launcher (measured on OPPO PMA120, ColorOS 16.1 / Android 16) |
| `double_tap_power_button_gesture` | `Settings.Secure` (AOSP) | “Double tap power button gesture behavior. **0 = Camera launch, 1 = Wallet launch**” | `[AOSP SOURCE]` https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/master/core/java/android/provider/Settings.java (lines ~11050–11071) |
| `double_tap_power_button_gesture_enabled` | `Settings.Secure` (AOSP) | whether the double-tap-power gesture is enabled at all | same AOSP file |
| `camera_double_tap_power_gesture_disabled` | `Settings.Secure` (AOSP) | disables the camera-launch variant of the gesture | same AOSP file; used by AOSP Settings’ `DoubleTapPowerPreferenceController` |
| `android.settings.QUICK_ACCESS_WALLET_SETTINGS` | `Settings.ACTION_*` | the Android 16 “Quick Access Wallet” settings screen | same AOSP file (line ~2787) |
| `oplus_customize_gesture_double_touch_on` (current) / `oplus_customize_gesture_double_touch` (legacy) | `Settings.Secure`, **per user** | ColorOS **双击亮屏 / double-tap-screen wake** switch (0/1); also honours the global `disable_gestures` | `[GITHUB]` https://github.com/YuKongA/ColorOS-AVD — `docs/coloros-firmware-changes.md` (line 57), `docs/coloros-double-tap-validation.md` (line 11), `native/double_tap_wake/DoubleTapWake.java` (reads `oplus_customize_gesture_double_touch_on` first, falls back to `oplus_customize_gesture_double_touch`) |
| `disable_gestures` | `Settings.Global` | master kill-switch respected by the double-tap-screen gesture | same |
| `app_start_confirm_rus_enable` | `Settings.Global` | suppresses the “允许打开 / wants to open” confirmation toast when a shortcut launches an app | `[GITHUB]` repo README |
| `KEYLOG_PhoneWindowManagerExtImpl` | log tag | the Oplus `PhoneWindowManager` extension that consumes the power-key presses and decides what to launch | `[GITHUB]` repo README |
| `com.oplus.gesture` = `/system/system_ext/app/OplusGestureUI` | system app | the Oplus gesture UI app (debloat lists show it as a system_ext app) | `[GITHUB]` debloat list: https://pastebin.com/MSWKJruP |

### Not confirmed (searched, no authoritative hit)
* `oplus_customize_gesture_open_type` — **no hits anywhere** (exa/bing/so360/GitHub). Likely does not exist under that exact name, or is internal and undocumented.
* `oplus_customize_double_click_camera_on` — **no hits anywhere**.
* `oplus_customize_gesture_double_touch` — exists, but it is the **double-tap-screen** key (§6), *not* a power-key key.
* `OplusGestureUI` / `com.oplus.gesture` — confirmed only as an installed system app; **no published documentation** of which settings it owns.
* Wallet package names: `com.heytap.tas` confirmed (with `com.nearme.wallet.nfc.ui.NfcConsumeActivity`); `com.heytap.wallet` confirmed as a *launched* package that is often absent on CN ROMs; the ColorOS “钱包” stock-app entry is `my_stock/del-app/FinShellWallet` (FinShell Wallet) — the exact package id `com.finshell.wallet` is **[INFERENCE, unconfirmed]**.

---

## 4. Published ADB commands that switch the target back to the camera

From the community project (most concrete, measured on ColorOS 16.1): https://github.com/Nielk74/coloros-power-button-launcher

```
# read the current OEM target
adb shell settings get secure double_tap_power_button_value      # 0=相机 1=钱包 2=助手 3=快捷应用

# switch the double-tap-power target back to the CAMERA
adb shell settings put secure double_tap_power_button_value 0

# switch it to the WALLET again
adb shell settings put secure double_tap_power_button_value 1

# suppress the "允许打开" / app-start confirmation toast (restore with 1)
adb shell settings put global app_start_confirm_rus_enable 0

# open the companion UI
adb shell am start -n com.nielk74.colorospowerlauncher/.MainActivity

# remove the community wallet shim, if installed
adb shell pm uninstall com.heytap.wallet
```
Notes from the same README: the standard AOSP `double_tap_power_button_gesture` setting “is not changed (i.e. changing Android's standard camera double-tap setting does not change the OEM action)”; the *Wallet* path needs a persistent **AccessibilityService** redirect (`com.heytap.wallet/.WalletRedirectAccessibilityService`) because the tested firmware launches `NfcConsumeActivity` directly, and that firmware **removes third-party accessibility entries during restart** (hence a boot receiver re-adding the service to `enabled_accessibility_services`).

Other published fixes:
* `[REDDIT]` r/oneplus 2026-10-30 (ColorOS 17, OnePlus 15): “make sure the double-click power setting is enabled in Settings, then run these two commands in an adb shell: `settings put secure …`” — **the two exact commands could not be retrieved** (Reddit body not fetchable). `[INFERENCE]` they are most likely `settings put secure double_tap_power_button_gesture_enabled 1` and/or `settings put secure camera_double_tap_power_gesture_disabled 0` — **unconfirmed, do not present as fact**.
* `[XDA]` generic Android remap (Samsung-style, **not** ColorOS): `adb shell "settings put system double_tab_launch_component com.sec.android.app.camera/com.sec.android.app.camera.Camera"` — https://xdaforums.com/t/guide-remapping-the-power-button-double-press-to-any-app.3752276/
* `[GITHUB]` no-root alternative: `yqia03/coloros-wallet-bridge` (accessibility redirect, keeps the OEM 钱包 shortcut) and `Nielk74/coloros-power-button-launcher` (logcat-monitor route: watch `KEYLOG_PhoneWindowManagerExtImpl` to detect the OEM Wallet launch and redirect).

**On-device checklist for `PKR110_16.0.0.204(CN01)`:**
```
adb shell settings list secure | grep -i -E "double|power|gesture"   # all OEM + AOSP keys
adb shell settings get secure double_tap_power_button_value
adb shell settings get secure double_tap_power_button_gesture
adb shell settings get secure double_tap_power_button_gesture_enabled
adb shell settings get secure camera_double_tap_power_gesture_disabled
adb shell settings get global disable_gestures
adb shell dumpsys activity service quickaccesswallet      # is a QAW service bound?
adb shell pm list packages | grep -E "heytap|finshell|oplus.camera"
```
Also check, in the 钱包 app itself: `钱包 → 我的 → 设置 → 双击电源键打开刷卡` (turn **off**) — otherwise the wallet surface can appear even when the OS target is 相机.

---

## 5. AccessibilityService vs vendor service, and `android.service.quickaccesswallet`

* **OEM side is a vendor *framework* service, not an AccessibilityService.** The double-tap-power decision lives in the Oplus `PhoneWindowManager` extension inside `system_server` (log tag `KEYLOG_PhoneWindowManagerExtImpl`); it reads `Settings.Secure.double_tap_power_button_value` and starts the target activity/component directly. AccessibilityServices appear **only in community workarounds** (the shim/redirect apps). `[GITHUB]`
* **AOSP/Pixel side:** Android 16 added a **“Double tap power button”** page under *Settings → Gestures* that swaps the gesture between **Camera**, the **default wallet app**, and **off** (“present but disabled by default in the first Android 16 Beta; also spotted in Android 15 QPR2 Beta 3”). `[MEDIA]` https://9to5google.com/2025/01/27/android-16-wallet-shortcut-camera-power-button — implemented on top of `Settings.Secure.double_tap_power_button_gesture` (0 = camera, 1 = wallet) and the `android.settings.QUICK_ACCESS_WALLET_SETTINGS` screen. `[AOSP SOURCE]`
* **How Quick Access Wallet is configured on Pixel-like devices:** the wallet app (Google Wallet) publishes the **`android.service.quickaccesswallet`** service; SystemUI binds to it as the *QuickAccessWalletHost* to render the lockscreen wallet affordance, and the user picks/authorises the wallet in *Settings → Wallets*. The service you see in SystemUI dumps on your device is that host/service — it is a **lockscreen/quick-access wallet surface**, and by itself it does **not** own the power-button gesture on ColorOS.
  * **Unconfirmed:** I could not fetch the AOSP `QuickAccessWalletHost`/`WalletController` sources (android.googlesource.com paths returned 404 and the aosp-mirror GitHub SystemUI paths 404), so the **exact AOSP service action string** (`android.service.quickaccesswallet.QuickAccessWalletService`) is **[UNVERIFIED]**, as is the claim that ColorOS’s `com.heytap.tas` (or `com.heytap.wallet`) registers that service. **Verify on-device** with `dumpsys quickaccesswallet` and `dumpsys package com.heytap.tas | grep -i quickaccesswallet`.
* **Key point for the reported symptom:** `com.heytap.tas` and `com.oplus.camera` are simply **two different hard-coded targets of the same OEM slot**. Nothing about `quickaccesswallet` is required for the wallet to open.

---

## 6. 双击电源键 vs 双击屏幕 vs AOD (“松松”)

| Gesture | Mechanism / key | Where it lives | Source |
|---|---|---|---|
| **双击电源键** (double press of the physical power key) | OEM policy in `PhoneWindowManagerExtImpl`; `Settings.Secure.double_tap_power_button_value` = 0/1/2/3 | ColorOS gesture/快捷启动 page (exact CN label unconfirmed, §1) | `[GITHUB]` |
| **双击屏幕 / 双击亮屏** (double tap on the panel to wake) | `Settings.Secure.oplus_customize_gesture_double_touch_on` (legacy `oplus_customize_gesture_double_touch`), per-user, honours global `disable_gestures`; real hardware also uses the kernel node `/proc/touchpanel/double_tap_enable` | `黑屏手势` / `熄屏手势` page (ColorOS 16 manual EN: *Accessibility & convenience → Gestures & motions → Screen-off gestures*) | `[GITHUB]` https://github.com/YuKongA/ColorOS-AVD/blob/main/docs/coloros-firmware-changes.md · `[VENDOR DOC]` https://m.media-amazon.com/images/I/A1jX9eLPpYL.pdf |
| **画 O / 画 V** (screen-off gestures) | draw-O opens camera, draw-V toggles the flashlight | same 熄屏手势 page | `[VENDOR DOC]` (manual) |
| **双击机身背部** (back-tap) | `设置 → 快捷与辅助 → 智能体感 → 双击机身背部` → 截屏 / 启动相机 / 调出收付款码 | ColorOS 16 | `[MEDIA]` https://www.toutiao.com/article/7601314615758193188/ |
| **AOD / “松松” double-tap** | **Not confirmed.** The ColorOS 16 manual lists AOD “Raise to wake” and the screen-off gestures but **no** AOD-specific double-tap-to-launch feature. “松松” (per-OOD widget/quick-action ecosystem) was not documented in any source I could reach. | — | `[UNCONFIRMED]` |

Also confirmed from the same ColorOS-AVD project: the stock-app list marks 钱包 as `my_stock/del-app/FinShellWallet` (i.e. the 钱包 app is a system stock app on CN ColorOS) — https://github.com/YuKongA/ColorOS-AVD/blob/main/docs/coloros-firmware-changes.md (line 153).

---

## 7. Explicit list of things I could NOT confirm

1. **Official OPPO/OnePlus CN documentation** of the ColorOS 16 “双击电源键启动” screen, its exact menu path and its option list (coloros.com 使用技巧 pages are client-rendered; their API endpoints errored).
2. Whether `PKR110_16.0.0.204(CN01)` exposes the 4-target picker (相机/钱包/助手/快捷应用) or a 2-target picker (相机/钱包 / 门禁卡) — i.e. the exact list on **this** build.
3. Any **ColorOS 15/16 CN** bug report specifically about “钱包 replaces 相机” (the Chinese evidence is indirect: the 钱包 app’s own 刷卡 switch + the OEM target slot + one BBS 公交码 title).
4. The exact ADB commands in the r/oneplus “Fix for OnePlus 15 double-click power to open Camera in ColorOS 17” thread (Reddit body not fetchable).
5. The body of the OnePlus community thread “Double-tap power button is gone with OxygenOS 16” (geo-blocked for CN) and of the DroidWin article (fetch blocked).
6. The exact AOSP service-action string for `android.service.quickaccesswallet`, and whether ColorOS’s `com.heytap.tas` registers it (the service visible in your SystemUI dump is presumably the OEM wallet’s QAW host — plausible but **not verified**).
7. `oplus_customize_gesture_open_type` and `oplus_customize_double_click_camera_on` — no source found; treat as **non-existent or internal/undocumented**.
8. Any AOD-specific “松松” double-tap behaviour in ColorOS 16.
9. The precise FinShell Wallet package id (`com.finshell.wallet`) — inferred from the stock-app name `FinShellWallet`.
