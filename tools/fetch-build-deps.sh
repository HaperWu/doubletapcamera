#!/usr/bin/env bash
# 下载离线构建所需的全部第三方依赖（无需 Android SDK / 无需联网的 gradle）
#   build/dl/ecj.jar          Eclipse 编译器（Java 源码 -> .class）
#   build/dl/android.jar      编译期 android.jar（API16，够用且体积小）
#   build/dl/bt/android-14/   Android build-tools r34（aapt2 / apksigner / zipalign / d8）
#
# 用法: ./tools/fetch-build-deps.sh
set -euo pipefail
cd "$(dirname "$0")/.."

DL=build/dl
BT=$DL/bt/android-14
mkdir -p "$DL" "$DL/bt"

ECJ_URL=https://repo1.maven.org/maven2/org/eclipse/jdt/ecj/3.46.100/ecj-3.46.100.jar
ANDROID_JAR_URL=https://repo1.maven.org/maven2/com/google/android/android/4.1.1.4/android-4.1.1.4.jar
BT_URL=https://dl.google.com/android/repository/build-tools_r34-linux.zip

fetch() {  # fetch <url> <目标文件>
  if [ -s "$2" ]; then
    echo "已存在，跳过: $2"
    return
  fi
  echo "下载 $1"
  curl -fSL --retry 3 -o "$2" "$1"
}

fetch "$ECJ_URL" "$DL/ecj.jar"
fetch "$ANDROID_JAR_URL" "$DL/android.jar"

if [ ! -x "$BT/aapt2" ]; then
  fetch "$BT_URL" "$DL/bt/build-tools_r34-linux.zip"
  command -v unzip >/dev/null || { echo "需要 unzip"; exit 1; }
  rm -rf "$DL/bt/android-14"
  unzip -q "$DL/bt/build-tools_r34-linux.zip" -d "$DL/bt"
  chmod +x "$BT/aapt2" "$BT/apksigner" "$BT/zipalign" 2>/dev/null || true
fi

echo "依赖就绪："
ls -1 "$DL"/ecj.jar "$DL"/android.jar 2>/dev/null
ls -1 "$BT" | head -8
