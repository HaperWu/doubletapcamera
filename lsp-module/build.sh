#!/usr/bin/env bash
# 构建 LSPosed 模块 APK（无 Android SDK 依赖：ECJ 编译 + D8 转 dex + aapt2 打包 + apksigner 签名）
# 用法: ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

DL=../build/dl
BT=$DL/bt/android-14
OUT=../build/out
ANDROID_JAR=$DL/android.jar
ECJ=$DL/ecj.jar

rm -rf "$OUT"; mkdir -p "$OUT"/{stubclasses,classes,apk}

echo "[1/6] 编译 Xposed API 桩（仅编译期使用）"
java -jar "$ECJ" -nowarn -proc:none -source 8 -target 8 \
  -classpath "$ANDROID_JAR" -d "$OUT/stubclasses" $(find stubs -name '*.java')

echo "[2/6] 打包 stubs.jar（用 python zipfile，JRE 没有 jar 工具）"
python3 - "$OUT/stubclasses" "$OUT/stubs.jar" <<'PY'
import os,sys,zipfile
src,dst=sys.argv[1],sys.argv[2]
with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as z:
    for root,_,files in os.walk(src):
        for f in files:
            p=os.path.join(root,f)
            z.write(p, os.path.relpath(p,src))
PY

echo "[3/6] 编译模块源码"
java -jar "$ECJ" -nowarn -proc:none -source 8 -target 8 \
  -classpath "$ANDROID_JAR:$OUT/stubs.jar" -d "$OUT/classes" $(find src -name '*.java')

echo "[4/6] D8: class -> classes.dex"
java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 --release --min-api 27 \
  --lib "$ANDROID_JAR" --lib "$OUT/stubs.jar" --output "$OUT/apk" $(find "$OUT/classes" -name "*.class")
ls -l "$OUT/apk/classes.dex"

echo "[5/6] aapt2: 资源 + Manifest -> base.apk"
"$BT/aapt2" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$ANDROID_JAR" \
  --manifest AndroidManifest.xml "$OUT/res.zip" \
  --min-sdk-version 27 --target-sdk-version 34 --auto-add-overlay

echo "[6/6] 合并 dex/assets 并签名"
python3 - "$OUT/base.apk" "$OUT/unsigned.apk" <<'PY'
import sys,zipfile,shutil
src,dst=sys.argv[1],sys.argv[2]
extra=['../build/out/apk/classes.dex',
       'META-INF/xposed/java_init.list',
       'META-INF/xposed/module.prop',
       'META-INF/xposed/scope.list']
skip={'classes.dex','assets/xposed_init','META-INF/xposed/java_init.list',
      'META-INF/xposed/module.prop','META-INF/xposed/scope.list'}
zin=zipfile.ZipFile(src,'r')
zout=zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    if it.filename in skip: continue
    zout.writestr(it, zin.read(it.filename))
for e in extra:
    arc=e.split('/')[-1] if e.endswith('classes.dex') else e
    zout.write(e, arc)
zout.close(); zin.close()
PY

if [ ! -f keystore.jks ]; then
  if [ -n "${MODULE_KEYSTORE_B64:-}" ]; then
    # 仓库 Secret 里保存了正式签名密钥（base64），CI 与本地用同一把钥匙 → 跨版本可直接覆盖升级
    echo "==> 从 MODULE_KEYSTORE_B64 恢复签名密钥"
    printf '%s' "$MODULE_KEYSTORE_B64" | base64 -d > keystore.jks
  else
    keytool -genkeypair -keystore keystore.jks -alias mod -keyalg RSA -keysize 2048 \
      -validity 10000 -storepass android -keypass android \
      -dname "CN=DblTapCam, OU=dev, O=local, C=CN" >/dev/null 2>&1
  fi
fi
"$BT/zipalign" -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
"$BT/apksigner" sign --ks keystore.jks --ks-pass pass:android --key-pass pass:android \
  --min-sdk-version 27 --out "$OUT/doubletap-camera.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify --print-certs "$OUT/doubletap-camera.apk" | head -5
ls -l "$OUT/doubletap-camera.apk"
echo "==> 产物: $OUT/doubletap-camera.apk"
