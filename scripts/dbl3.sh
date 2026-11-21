#!/bin/bash
adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME >/dev/null 2>&1; sleep 1.0
before=$(adb shell "dumpsys activity activities | grep -E 'ResumedActivity:' | head -1" | tr -d '\r')
adb shell input keyevent 26; sleep 0.12; adb shell input keyevent 26
sleep 2.5
after=$(adb shell "dumpsys activity activities | grep -E 'ResumedActivity:' | head -1" | tr -d '\r')
echo "   BEFORE: $before"
echo "   AFTER : $after"
