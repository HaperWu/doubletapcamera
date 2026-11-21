#!/bin/bash
# dbl4.sh — double-tap power key test with robust detection.
# Prints: BEFORE/AFTER resumed activity, current focus window, and whether the camera package appears.
set -u
PKG_CAM=com.oplus.camera

before=$(adb shell "dumpsys activity activities | grep -E 'ResumedActivity:' | head -1" 2>/dev/null | tr -d '\r')
adb shell input keyevent 3 >/dev/null 2>&1        # go HOME so a new launch is observable
sleep 0.8
adb shell input keyevent 26 >/dev/null 2>&1       # power down
sleep 0.12
adb shell input keyevent 26 >/dev/null 2>&1       # power up  => double tap
sleep 2.2
after=$(adb shell "dumpsys activity activities | grep -E 'ResumedActivity:' | head -1" 2>/dev/null | tr -d '\r')
focus=$(adb shell "dumpsys window windows | grep -E 'mCurrentFocus' | head -1" 2>/dev/null | tr -d '\r')
cam=$(adb shell "dumpsys activity activities | grep -c '$PKG_CAM'" 2>/dev/null | tr -d '\r')
echo "  BEFORE : $before"
echo "  AFTER  : $after"
echo "  FOCUS  : $focus"
echo "  camera-activity-mentions: $cam"
if echo "$after$focus" | grep -q "$PKG_CAM"; then echo "  >>> RESULT: CAMERA OPENED"; fi
if echo "$after$focus" | grep -q 'heytap.tas'; then echo "  >>> RESULT: WALLET OPENED"; fi
