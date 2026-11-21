#!/bin/bash
# openact.sh — start an activity safely (device-side single quotes protect '$' in class names)
# usage: ./openact.sh 'com.android.settings/.Settings$DoubleTapPowerSettingsActivity'
act="$1"
adb shell "am start -n '$act'" 2>&1 | tr -d '\r' | grep -E 'Starting|Error|Exception' | head -3
