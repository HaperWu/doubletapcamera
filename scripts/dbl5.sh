#!/bin/bash
# dbl5.sh — 双击电源键测试并判定结果 (camera / wallet / none)
# 用法: ./dbl5.sh   (可选: 传 1 表示测试后不回到桌面)
adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME >/dev/null 2>&1; sleep 1.2
before=$(adb shell "dumpsys activity activities | grep -E 'ResumedActivity:' | head -1" | tr -d '\r')
adb shell input keyevent 26 >/dev/null 2>&1; sleep 0.12; adb shell input keyevent 26 >/dev/null 2>&1
sleep 2.5
after=$(adb shell "dumpsys activity activities | grep -E 'ResumedActivity:' | head -1" | tr -d '\r')
res="NONE"
case "$after" in
  *com.oplus.camera*)  res="CAMERA" ;;
  *com.heytap.tas*)    res="WALLET" ;;
  *com.nearme.wallet*) res="WALLET" ;;
  *com.finshell.wallet*) res="WALLET" ;;
esac
echo "   BEFORE: $before"
echo "   AFTER : $after"
echo "   >>> RESULT: $res"
