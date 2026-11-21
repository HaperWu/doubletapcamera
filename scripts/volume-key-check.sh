#!/usr/bin/env bash
# volume-key-check.sh —— 验证「相机内音量键功能」在锁屏 / 解锁两种状态下是否真的生效
#
# 用法:
#   bash scripts/volume-key-check.sh locked      # 锁屏场景（双击电源键进相机）
#   bash scripts/volume-key-check.sh unlocked    # 解锁场景
#   bash scripts/volume-key-check.sh locked auto # 不交互，直接用 input keyevent 24 注入
#
# 判定依据（相机 APK 里的日志签名，实测有效）：
#   点按快门按钮 = OCAM_CameraControlUI: onShutterButtonClick, ShutterButton.id: ...
#                 + OCAM_CommonCapMode: onCameraShutterButtonClick
#                 + OCAM_g1_BaseMode: CameraTest Shutter Respond Start
#   音量键被相机收到 = W OCAM_OplusCamera: Key down has been intercepted
#   锁屏相关标志 = OCAM_CameraEntry: isLockScreenStart, ... mbSecureStartFromFramework: ...
#
# 注意：ADB 的 `input keyevent 24` 与真实按键不等价（没有 scanCode / deviceId），
#       用它只能验证「事件是否送达」，不能替代真实按键验证快门是否真的触发。
set -u
PKG_CAM=com.oplus.camera
MODE="${1:-unlocked}"
AUTO="${2:-}"

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

say "环境"
adb devices | sed -n '2p'
adb shell dumpsys trust 2>/dev/null | grep -m1 -E "trustState|deviceLocked" | tr -d '\r'
MMKV="/data/data/${PKG_CAM}/files/mmkv/${PKG_CAM}_preferences"
adb shell su -c "grep -ao 'pref_volume_key_function_key.\{0,12\}' ${MMKV}" 2>/dev/null | head -2
echo "(相机内 音量键功能 的当前取值见上；shutter=快门 / zoom=变焦 / volume=音量)"

say "打开相机"
if [ "$MODE" = "locked" ]; then
  adb shell input keyevent 26 >/dev/null 2>&1   # 息屏
  sleep 1.5
else
  adb shell wm dismiss-keyguard >/dev/null 2>&1
  sleep 1
fi
adb shell am force-stop $PKG_CAM >/dev/null 2>&1
adb shell "input keyevent 26 26" >/dev/null 2>&1  # 单进程连发两次才会被判定为双击
sleep 4
adb shell dumpsys activity activities 2>/dev/null | grep -m1 ResumedActivity | cut -c1-160

PID=$(adb shell pidof $PKG_CAM | tr -d '\r')
if [ -z "$PID" ]; then echo "!! 相机进程没起来"; exit 1; fi
echo "camera pid=$PID"

adb logcat --pid=$PID -c 2>/dev/null
adb exec-out screencap -p > /tmp/vk_before.png 2>/dev/null

if [ "$AUTO" = "auto" ]; then
  say "注入音量↑ (input keyevent 24)"
  adb shell input keyevent 24 >/dev/null 2>&1
else
  say "请现在按一次【真实】音量↑ 键，然后回车"
  read -r _
fi
sleep 2
adb exec-out screencap -p > /tmp/vk_after.png 2>/dev/null

say "相机收到的按键"
adb logcat --pid=$PID -d 2>/dev/null | grep -iE "intercepted" | cut -c1-160

say "快门是否触发（判据: Shutter Respond Start / onShutterButtonClick）"
if adb logcat --pid=$PID -d 2>/dev/null | grep -qE "Shutter Respond Start|onShutterButtonClick|onCameraShutterButtonClick"; then
  echo "✔ 音量键触发了拍照"
else
  echo "✘ 没有看到拍照动作（若是 auto 模式，多半是注入事件与真实按键不等价，请用真实按键再测一次）"
fi

say "锁屏标志"
adb logcat --pid=$PID -d 2>/dev/null | grep -iE "isLockScreenStart|setShowWhenLocked" | cut -c1-200

say "缩放条变化（zoom 模式下有效）"
python3 - <<'PY' 2>/dev/null || echo "(无 PIL，跳过)"
from PIL import Image
def hl(p):
    im=Image.open(p).convert('RGB'); px=im.load()
    xs=[x for x in range(300,750) if (lambda c: c[0]>200 and 130<c[1]<200 and c[2]<80)(px[x,1650])]
    return (min(xs),max(xs)) if xs else None
a,b=hl('/tmp/vk_before.png'),hl('/tmp/vk_after.png')
print('before:',a,' after:',b, '→', '变化了' if a!=b else '没变')
PY
echo
echo "截图：/tmp/vk_before.png  /tmp/vk_after.png"
