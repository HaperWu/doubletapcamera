#!/usr/bin/env bash
# 直接改 LSPosed 配置库：启用模块 + 设置作用域（不依赖 LSPosed 管理器 UI）
# 用法: ./lspdb.sh <模块包名> [作用域包名 ...]
# 依赖: adb 已 root(su -c)；本机 python3
set -euo pipefail
cd "$(dirname "$0")"

PKG="${1:-io.github.doubletapcamera}"; shift || true
SCOPES=("${@:-system com.heytap.tas android}")
read -r -a SCOPES <<< "${SCOPES[*]}"

APK=$(adb shell pm path "$PKG" | sed 's/package://' | tr -d '\r')
echo "模块 APK: $APK"

TMP=build/lspdb_work
mkdir -p "$TMP"
for f in "" "-wal" "-shm"; do
  adb shell su -c "cp /data/adb/lspd/config/modules_config.db$f /data/local/tmp/mc$f" >/dev/null 2>&1 || true
  adb pull "/data/local/tmp/mc$f" "$TMP/mc.db$f" >/dev/null 2>&1 || true
done

python3 - "$TMP/mc.db" "$PKG" "$APK" "${SCOPES[@]}" <<'PY'
import sqlite3, sys
db, pkg, apk = sys.argv[1], sys.argv[2], sys.argv[3]
scopes = sys.argv[4:]
c = sqlite3.connect(db)
c.execute("PRAGMA journal_mode=WAL")
# 清理旧包名残留（改包名/换模块时用）
for tbl in ("modules", "modules_state", "scope"):
    c.execute(f"DELETE FROM {tbl} WHERE module_pkg_name<>?", (pkg,))
c.execute("INSERT OR REPLACE INTO modules(module_pkg_name, apk_path) VALUES(?,?)", (pkg, apk))
c.execute("INSERT OR REPLACE INTO modules_state(module_pkg_name,user_id,enabled,scope_request_blocked) VALUES(?,?,1,0)", (pkg, 0))
for s in scopes:
    c.execute("INSERT OR REPLACE INTO scope(module_pkg_name,app_pkg_name,user_id) VALUES(?,?,0)", (pkg, s))
c.commit()
c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print("modules:", list(c.execute("select * from modules")))
print("state  :", list(c.execute("select * from modules_state")))
print("scope  :", list(c.execute("select * from scope")))
c.close()
PY

adb push "$TMP/mc.db" /data/local/tmp/mc_new.db >/dev/null
adb shell su -c "cp /data/local/tmp/mc_new.db /data/adb/lspd/config/modules_config.db"
adb shell su -c "rm -f /data/adb/lspd/config/modules_config.db-wal /data/adb/lspd/config/modules_config.db-shm"
adb shell su -c "chmod 600 /data/adb/lspd/config/modules_config.db"
echo "已写回 /data/adb/lspd/config/modules_config.db"
echo "提示：system_server（作用域 android）需要重启设备后才会注入模块"
