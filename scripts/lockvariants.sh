#!/usr/bin/env bash
# lockvariants.sh — 锁屏下逐个试探哪种启动相机的 Intent 能盖在锁屏之上
#
# 用法： bash scripts/lockvariants.sh
# 每次尝试后打印前台 Activity；能覆盖到锁屏上的方案会直接看到相机界面。

set -u
try() {
    local desc="$1"; shift
    echo "---- $desc ----"
    adb shell "$@" >/dev/null 2>&1
    sleep 1.5
    adb shell dumpsys activity activities | grep -E "topResumedActivity" | head -1
    adb shell input keyevent 3 >/dev/null 2>&1   # 回桌面
    adb shell input keyevent 26 >/dev/null 2>&1 # 重新息屏
    sleep 1
}

echo "==================== 0. 息屏 ===================="
adb shell input keyevent 26
sleep 1.5
adb shell dumpsys window | grep -E "mDreamingLockscreen|mShowingLockscreen" | head -3

try "A. 普通 action（当前模块用的）" \
    "am start -a android.media.action.STILL_IMAGE_CAMERA -p com.oplus.camera --ez need_screen_on true"

try "B. secure action + 厂商组件（ColorOS 自己的锁屏快拍入口）" \
    "am start -a android.media.action.STILL_IMAGE_CAMERA_SECURE -n com.oplus.camera/com.oplus.camera.Camera"

try "C. secure action + 厂商组件 + 厂商 extras" \
    "am start -a android.media.action.STILL_IMAGE_CAMERA_SECURE -n com.oplus.camera/com.oplus.camera.Camera --es caller_package android --ei mode 29 --ei lunch_type 2"

try "D. 显式组件 com.oplus.camera.Camera（不带 action）" \
    "am start -n com.oplus.camera/com.oplus.camera.Camera"

try "E. IMAGE_CAPTURE action" \
    "am start -a android.media.action.IMAGE_CAPTURE -p com.oplus.camera"
