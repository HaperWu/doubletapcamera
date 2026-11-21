#!/bin/bash
adb shell svc power stayon true >/dev/null 2>&1
adb shell wm dismiss-keyguard >/dev/null 2>&1
adb shell input keyevent 26; sleep 0.12; adb shell input keyevent 26
sleep 2.2
echo -n "   TOP: "
adb shell "dumpsys activity activities | grep -E 'topResumedActivity=' | head -1" | tr -d '\r'
