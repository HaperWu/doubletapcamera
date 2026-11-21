#!/usr/bin/env bash
# 锁屏（带 PIN）状态下验证「双击电源键 → 直接开相机」
#
# 用法：
#   bash scripts/verify-lockscreen.sh            # 用当前 PIN
#   bash scripts/verify-lockscreen.sh 1234       # 顺便设置/确认 PIN
#
# 注意：
#   * 双击必须由**同一个 input 进程**连发两次：adb shell "input keyevent 26 26"
#     （分两次 adb shell 的间隔 > multi_press_timeout(300ms)，系统不会判定为双击）
#   * 脚本需要 root 才能读 LSPosed 日志（/data/adb/lspd/log），没有 root 时相关部分会跳过
set -uo pipefail
cd "$(dirname "$0")/.."

PKG=io.github.doubletapcamera
PIN="${1:-}"
LOGS="build/locktest-$(date +%H%M%S).log"

say() { echo -e "\n=== $* ==="; }

say "0. 环境"
adb devices | sed -n '2p'
adb shell getprop ro.build.display.id 2>/dev/null
adb shell dumpsys trust 2>/dev/null | grep -m1 trustState

if [ -n "$PIN" ]; then
  say "1. 设置测试 PIN（测完记得 locksettings clear --old $PIN）"
  adb shell locksettings set-pin "$PIN" 2>&1 | head -2
fi

say "2. 让屏幕熄灭再点亮（进入锁屏）"
adb shell input keyevent 26   # power -> 息屏
sleep 1
adb shell input keyevent 224  # wakeup -> 亮屏（仍在锁屏）
sleep 1
adb shell dumpsys window windows 2>/dev/null | grep -m1 mCurrentFocus

say "3. 清日志 + 双击电源键"
adb logcat -c 2>/dev/null
adb shell "input keyevent 26 26"
sleep 3

say "4. 前台 Activity"
adb shell dumpsys activity activities 2>/dev/null | grep -m2 -E "ResumedActivity|topResumedActivity"

say "5. 关键日志"
adb logcat -d 2>/dev/null | grep -E "DblTapCam|isLockScreenStart|setShowWhenLocked|STILL_IMAGE_CAMERA|start wallet" | tail -40

say "6. LSPosed 模块日志（需要 root）"
if adb shell su -c "ls /data/adb/lspd/log" >/dev/null 2>&1; then
  adb shell su -c "cat /data/adb/lspd/log/modules_*.log" 2>/dev/null | grep -E "DblTapCam|module loaded" | tail -15
else
  echo "(无 root，跳过)"
fi

say "7. 结果判定"
OUT=$(adb logcat -d 2>/dev/null)
echo "$OUT" | grep -q "mbShowOnKeyguardLocked: true" && echo "✅ 相机认可「正规快捷启动」，应在锁屏上直接显示" \
  || echo "⚠️ 没看到 mbShowOnKeyguardLocked: true —— 相机可能仍被压在锁屏后面"
echo "$OUT" | grep -q "start wallet" && echo "❌ 钱包仍然被拉起" || echo "✅ 钱包没有被拉起"
echo "(完整输出见 $LOGS)"
adb logcat -d > "$LOGS" 2>/dev/null
