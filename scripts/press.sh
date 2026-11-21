#!/bin/bash
# press.sh — 用 root sendevent 精确注入电源键（每次按键后发 EV_SYN），支持单击/双击
# 用法: ./press.sh [间隔秒] [press次数]   例: ./press.sh 0.10 2
GAP=${1:-0.10}
COUNT=${2:-2}
DEV=/dev/input/event1   # pmic_pwrkey: EV_KEY=1, KEY_POWER=116, EV_SYN=0

adb shell "input keyevent 224" >/dev/null 2>&1   # WAKEUP
adb shell wm dismiss-keyguard >/dev/null 2>&1
sleep 0.6

echo "== BEFORE =="
adb shell dumpsys activity activities | grep -m1 "ResumedActivity:" | sed 's/^ *//'

CMD=""
for i in $(seq 1 "$COUNT"); do
  [ -n "$CMD" ] && CMD="$CMD; sleep $GAP;"
  CMD="$CMD sendevent $DEV 1 116 1; sendevent $DEV 0 0 0; sleep 0.05; sendevent $DEV 0 116 0; sendevent $DEV 0 0 0"
done
adb shell su -c "$CMD" >/dev/null 2>&1
sleep 1.6

echo "== AFTER (gap=${GAP}s, presses=${COUNT}) =="
LINE=$(adb shell dumpsys activity activities | grep -m1 "ResumedActivity:" | sed 's/^ *//')
echo "$LINE"
case "$LINE" in
  *com.oplus.camera*) echo ">>> RESULT: CAMERA OPENED" ;;
  *com.heytap.tas*)   echo ">>> RESULT: WALLET OPENED" ;;
  *launcher*)         echo ">>> RESULT: NOTHING (launcher)" ;;
  *)                  echo ">>> RESULT: OTHER" ;;
esac
