#!/bin/bash
# fastpress.sh — 快速双击电源键（单个 input 进程发两次 keyevent），报告前台 Activity + 屏幕状态
# 用法: ./fastpress.sh [keycode]
KC=${1:-26}
adb shell "input keyevent 224" >/dev/null 2>&1
adb shell wm dismiss-keyguard >/dev/null 2>&1
sleep 0.7
BEFORE=$(adb shell dumpsys activity activities | grep -m1 "ResumedActivity:" | sed 's/.* u0 //; s/ .*//')
adb shell "input keyevent $KC $KC" >/dev/null 2>&1
sleep 1.6
AFTER=$(adb shell dumpsys activity activities | grep -m1 "ResumedActivity:" | sed 's/.* u0 //; s/ .*//')
WAKE=$(adb shell dumpsys power | grep -m1 mWakefulness | tr -d '\r' | awk '{print $2}')
echo "before=$BEFORE after=$AFTER wakefulness=$WAKE"
case "$AFTER" in
  *com.oplus.camera*) echo ">>> CAMERA OPENED" ;;
  *com.heytap.tas*)   echo ">>> WALLET OPENED" ;;
  *launcher*)         echo ">>> NOTHING (launcher)" ;;
  *)                  echo ">>> OTHER: $AFTER" ;;
esac
