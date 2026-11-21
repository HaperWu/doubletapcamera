#!/bin/bash
adb shell input keyevent 3 >/dev/null 2>&1; sleep 0.8
adb shell input keyevent 26; sleep 0.12; adb shell input keyevent 26
sleep 2.4
adb shell "dumpsys activity activities | grep -E 'topResumedActivity=|ResumedActivity:' | head -1" | tr -d '\r'
