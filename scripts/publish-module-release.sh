#!/usr/bin/env bash
# 把新版本发布到 LSPosed 模块仓库（Xposed-Modules-Repo/<应用ID>）。
#
# 为什么需要这个脚本：
#   modules.lsposed.org 展示的是「模块仓库」里的 release + README/SUMMARY/SCOPE/SOURCE_URL，
#   **主仓库（本仓库）的 release 不会自动同步过去**。
#   必须在模块仓库里【新建一个带 APK 资产的 release】（不能只替换旧 release 的资产：
#   bot 感知不到 tag 不会更新），XposedBot 的 Tag 工作流才会把 tag 改成
#   {versionCode}-{versionName}，随后站点才会在下一轮构建里更新。
#
# 用法：
#   export GH_TOKEN=ghp_xxx              # 需要 repo 权限的 PAT
#   scripts/publish-module-release.sh 1.1.2                # 用 build/out/doubletap-camera.apk
#   scripts/publish-module-release.sh 1.1.2 path/to.apk    # 指定 APK
#   CHANGELOG_FILE=notes.md scripts/publish-module-release.sh 1.1.2   # 自定义更新说明
#
# 环境变量：
#   MODULE_REPO   默认 Xposed-Modules-Repo/io.github.haperwu.doubletapcamera
#   ASSET_NAME    默认 doubletap-camera.apk
#   GH_TOKEN      必需
set -euo pipefail

APP_ID="io.github.haperwu.doubletapcamera"
MODULE_REPO="${MODULE_REPO:-Xposed-Modules-Repo/${APP_ID}}"
ASSET_NAME="${ASSET_NAME:-doubletap-camera.apk}"

VERSION="${1:-}"
APK="${2:-build/out/doubletap-camera.apk}"

if [ -z "$VERSION" ]; then
  echo "用法: $0 <version> [apk]" >&2
  exit 1
fi
if [ ! -f "$APK" ]; then
  echo "找不到 APK: $APK" >&2
  exit 1
fi
if [ -z "${GH_TOKEN:-}" ]; then
  echo "请先 export GH_TOKEN=<PAT>" >&2
  exit 1
fi

API="https://api.github.com"
AUTH=(-H "Authorization: token ${GH_TOKEN}" -H "Accept: application/vnd.github+json")

# ---- 1) 从 APK 里的 module.prop 读版本号（bot 依据 AndroidManifest 的 versionCode/versionName 改 tag）----
read -r VC VNAME < <(python3 - "$APK" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
prop = z.read('META-INF/xposed/module.prop').decode('utf-8', 'replace')
d = dict(l.split('=', 1) for l in prop.splitlines() if '=' in l)
print(d.get('versionCode', '0'), d.get('version', '0'))
PY
)
EXPECTED_TAG="${VC}-${VNAME// /_}"
SHA256="$(sha256sum "$APK" | cut -d' ' -f1)"

echo "[1/4] APK: $APK"
echo "      versionCode=$VC versionName=$VNAME  → bot 期望 tag: $EXPECTED_TAG"
echo "      sha256=$SHA256"

# ---- 2) 组装 release 正文 ----
if [ -n "${CHANGELOG_FILE:-}" ] && [ -f "$CHANGELOG_FILE" ]; then
  BODY="$(cat "$CHANGELOG_FILE")"
else
  BODY="## 双击电源键 → 直开相机（LSPosed 模块 v${VERSION})

- 详见源码仓库更新日志：https://github.com/HaperWu/doubletapcamera/releases/tag/v${VERSION}

APK SHA-256：\`${SHA256}\`
签名证书：\`CN=DblTapCam, OU=dev, O=local, C=CN\`（与 v1.1.0+ 同证书，可直接覆盖升级）"
fi

# ---- 3) 在模块仓库新建 release 并上传 APK ----
echo "[2/4] 在 $MODULE_REPO 创建 release v${VERSION} ..."
RELEASE_JSON="$(curl -sS -X POST "${AUTH[@]}" "$API/repos/$MODULE_REPO/releases" \
  -d "$(jq -n --arg tag "v${VERSION}" --arg name "v${VERSION}" --arg body "$BODY" \
        '{tag_name:$tag, name:$name, body:$body, draft:false, prerelease:false}')")"
RELEASE_ID="$(printf '%s' "$RELEASE_JSON" | jq -r '.id // empty')"
if [ -z "$RELEASE_ID" ]; then
  echo "创建 release 失败: $(printf '%s' "$RELEASE_JSON" | jq -r '.message // .')" >&2
  exit 1
fi
echo "      release id=$RELEASE_ID"

echo "[3/4] 上传资产 $ASSET_NAME ..."
curl -sS -X POST -H "Authorization: token ${GH_TOKEN}" \
  -H "Content-Type: application/octet-stream" \
  "$API/repos/$MODULE_REPO/releases/$RELEASE_ID/assets?name=${ASSET_NAME}" \
  --data-binary "@${APK}" \
  | jq -r 'if .id then "      asset id=\(.id) size=\(.size)" else "      上传失败: \(.message // .)" end'

# ---- 4) 等 bot 把 tag 改成 {versionCode}-{versionName} ----
echo "[4/4] 等 XposedBot 的 Tag 工作流把 tag 改成 $EXPECTED_TAG ..."
for i in $(seq 1 40); do
  TAG="$(curl -sS "${AUTH[@]}" "$API/repos/$MODULE_REPO/releases/$RELEASE_ID" | jq -r '.tag_name')"
  DRAFT="$(curl -sS "${AUTH[@]}" "$API/repos/$MODULE_REPO/releases/$RELEASE_ID" | jq -r '.draft')"
  if [ "$TAG" = "$EXPECTED_TAG" ]; then
    echo "      ✔ tag 已改为 $TAG"
    echo
    echo "下载地址: https://github.com/$MODULE_REPO/releases/download/$EXPECTED_TAG/$ASSET_NAME"
    echo "模块页面: https://modules.lsposed.org/module/$APP_ID/"
    echo "（站点是 Astro 静态构建 + Worker 触发 Pages 部署，通常 5~30 分钟内更新，最迟 3 个工作日）"
    exit 0
  fi
  if [ "$DRAFT" = "true" ]; then
    echo "      ✘ release 被 bot 置为 draft —— APK 校验未通过（缺 AndroidManifest.xml /"
    echo "        META-INF/xposed/module.prop 的 minApiVersion/targetApiVersion / java_init.list）" >&2
    exit 1
  fi
  sleep 30
done
echo "      ! 超时未改名，当前 tag=$TAG；可到 https://github.com/Xposed-Modules-Repo/modules/actions 查 Tag 工作流日志" >&2
exit 1
