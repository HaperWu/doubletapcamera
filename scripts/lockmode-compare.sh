#!/usr/bin/env bash
# 对比「锁屏双击电源键」在不同启动入口下，相机内部状态标志的差异
#
# 用法: bash scripts/lockmode-compare.sh
#
# 依次测试三种入口（都需要 root 读 LSPosed 日志可不选）：
#   A. secure 入口      settings put system doubletap_camera_secure 0   (默认)
#   B. 普通 action      settings put system doubletap_camera_secure 2
#   C. 直拍页           settings put system doubletap_camera_lock_act 1
#
# 每种入口都会打印：前台 Activity、相机关键日志标志(setShowWhenLocked /
# setLockScreenStart / isLockScreenStart / mbSecureStartFromFramework)、
# 以及是否盖在 keyguard 之上(mKeyguardOccluded)。
set -uo pipefail
cd "$(dirname "$0")/.."
PIN="${PIN:-1234}"

run_case() {
  local name="$1"; shift
  echo
  echo "==================== $name ===================="
  "$@"
  adb shell input keyevent 26 >/dev/null 2>&1   # 息屏 -> 锁屏
  sleep 1.2
  adb shell input keyevent 224 >/dev/null 2>&1 # 亮屏（仍在锁屏）
  sleep 1.2
  adb logcat -c >/dev/null 2>&1
  adb shell "input keyevent 26 26" >/dev/null 2>&1
  sleep 3
  echo "-- 前台 Activity:"
  adb shell dumpsys activity activities 2>/dev/null | grep -m1 -E "ResumedActivity|topResumedActivity"
  echo "-- keyguard 状态:"
  adb shell dumpsys activity activities 2>/dev/null | grep -m1 -E "mKeyguardOccluded" || true
  echo "-- 相机日志标志:"
  adb logcat -d 2>/dev/null | grep -E "setShowWhenLocked|setLockScreenStart|isLockScreenStart|mbSecureStartFromFramework|mbShowOnKeyguardLocked|DblTapCam" | sed -E 's/^.{0,24}//' | cut -c1-190 | tail -12
}

echo "== 0. 环境"
adb devices | sed -n '2p'
adb shell dumpsys trust 2>/dev/null | grep -m1 trustState
adb shell locksettings set-pin "$PIN" >/dev/null 2>&1 && echo "临时 PIN 已设置（$PIN，测完请 clear）"

run_case "A. secure 入口（默认 secure=0 lock_act=0）" \
  adb shell settings put system doubletap_camera_secure 0
run_case "B. 普通 action（secure=2）" \
  adb shell settings put system doubletap_camera_secure 2
run_case "C. 直拍页 CapturePhotoActivity（secure=0 lock_act=1）" \
  bash -c 'adb shell settings put system doubletap_camera_secure 0; adb shell settings put system doubletap_camera_lock_act 1'

echo
echo "== 还原设置"
adb shell settings put system doubletap_camera_secure 0
adb shell settings put system doubletap_camera_lock_act 0
adb shell settings delete system doubletap_camera_secure
adb shell settings delete system doubletap_camera_lock_act
echo "已删除 doubletap_camera_secure / doubletap_camera_lock_act（回到默认）"
echo "提醒: 记得清除测试 PIN -> adb shell locksettings clear --old $PIN"
