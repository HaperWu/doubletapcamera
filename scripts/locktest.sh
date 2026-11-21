#!/usr/bin/env bash
# locktest.sh — 锁屏场景下验证「双击电源键 → 相机」
#
# 用法： bash scripts/locktest.sh
#
# 说明：
#   * 注入双击必须用 **同一个 input 进程** 连发两次，否则 adb 两次进程间间隔 >300ms，
#     AOSP/厂商的「双击」判定不成立（实测 `input keyevent 26; input keyevent 26` 会被当成两次单击）。
#   * 锁屏判定用 `dumpsys window policy | grep keyguard` / `dumpsys window | grep mDreamingLockscreen`。

set -u
PKG=com.oplus.camera

echo "==================== 1. 息屏 + 确认锁屏状态 ===================="
adb shell input keyevent 26
sleep 1.5
adb shell dumpsys window | grep -E "mDreamingLockscreen|mShowingLockscreen|mCurrentFocus" | head -5

echo
echo "==================== 2. 锁屏双击电源键 ===================="
adb logcat -c
adb shell "input keyevent 26 26"
sleep 2.5

echo "-- 前台 Activity --"
adb shell dumpsys activity activities | grep -E "topResumedActivity|ResumedActivity" | head -3

echo
echo "-- 关键日志（模块 / 相机启动 / 钱包） --"
adb logcat -d | grep -iE "DblTapCam|STILL_IMAGE_CAMERA|ActivityTaskManager: START|start wallet|NfcConsumeActivity" | tail -40

echo
echo "-- 相机进程是否活着 --"
adb shell ps -A | grep -E "com.oplus.camera" | head -3
