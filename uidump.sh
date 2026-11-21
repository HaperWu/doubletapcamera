#!/bin/bash
# usage: uidump.sh [tag]
adb shell uiautomator dump /sdcard/_u.xml >/dev/null 2>&1
adb pull /sdcard/_u.xml /tmp/_u.xml >/dev/null 2>&1
python3 - <<'PY'
import xml.etree.ElementTree as ET
try: r=ET.parse('/tmp/_u.xml').getroot()
except Exception as e: print("  dump failed",e); raise SystemExit
for n in r.iter():
    a=n.attrib
    t=a.get('text') or a.get('content-desc')
    if t: print(f"  {a.get('class','').split('.')[-1]:12s} id={a.get('resource-id')} text={t!r} bounds={a.get('bounds')}")
PY
