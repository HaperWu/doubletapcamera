#!/usr/bin/env python3
"""arsc2.py — 解析 APK 里的 resources.arsc，按资源 ID 查出名称与取值。

用法:
  python3 arsc2.py <apk>                 # 列出所有包/类型概览
  python3 arsc2.py <apk> 0x0111006E      # 查单个资源 ID
  python3 arsc2.py <apk> --grep doubleTap  # 按名称关键字搜索
"""
import sys, zipfile, struct


class Pool:
    """资源字符串池（ResStringPool）。"""

    def __init__(self, data, off):
        self.strings = []
        self.count = struct.unpack_from('<I', data, off + 8)[0]
        flags = struct.unpack_from('<I', data, off + 16)[0]
        strings_start = struct.unpack_from('<I', data, off + 20)[0]
        if flags & (1 << 8):  # UTF-8
            for i in range(self.count):
                p = off + 28 + 4 * i
                soff = struct.unpack_from('<I', data, p)[0]
                q = off + strings_start + soff
                n = data[q + 2]
                self.strings.append(data[q + 3:q + 3 + n].decode('utf-8', 'replace'))
        else:  # UTF-16
            for i in range(self.count):
                p = off + 28 + 4 * i
                soff = struct.unpack_from('<I', data, p)[0]
                q = off + strings_start + soff
                ln = struct.unpack_from('<H', data, q)[0]
                if ln & 0x8000:
                    ln = ((ln & 0x7FFF) << 16) | struct.unpack_from('<H', data, q + 2)[0]
                    q += 4
                else:
                    q += 2
                self.strings.append(data[q:q + ln * 2].decode('utf-16-le', 'replace'))

    def __len__(self):
        return len(self.strings)

    def __getitem__(self, i):
        return self.strings[i] if 0 <= i < len(self.strings) else '?'


def parse(arsc):
    pkgs = []
    off = 12  # ResTable_header 之后开始
    total = struct.unpack_from('<I', arsc, 4)[0]
    while off + 8 <= total:
        ctype, hsize, csize = struct.unpack_from('<HHI', arsc, off)
        if csize == 0:
            break
        if ctype == 0x0200:  # RES_TABLE_PACKAGE
            pid = struct.unpack_from('<I', arsc, off + 8)[0]
            name = arsc[off + 12:off + 12 + 256].decode('utf-16-le', 'replace').split('\x00')[0]
            type_strings = struct.unpack_from('<I', arsc, off + 268)[0]
            key_strings = struct.unpack_from('<I', arsc, off + 276)[0]
            type_id_off = struct.unpack_from('<I', arsc, off + 284)[0] if csize >= 288 else 0
            pkgs.append({
                'id': pid, 'name': name, 'off': off, 'size': csize,
                'type_strings': type_strings, 'key_strings': key_strings,
                'type_id_off': type_id_off, 'types': [],
            })
        elif ctype == 0x0201:  # RES_TABLE_TYPE（通常是包 chunk 的子块，这里也能兜住）
            if pkgs:
                tid = arsc[off + 8]
                res0 = arsc[off + 9]
                cnt, es = struct.unpack_from('<II', arsc, off + 12)
                pkgs[-1]['types'].append({
                    'tid': tid, 'res0': res0, 'cnt': cnt, 'es': es,
                    'hdr': hsize, 'off': off,
                })
        off += csize
    # 类型块通常内嵌在包 chunk 内部，需要再进一层遍历
    for p in pkgs:
        sub = p['off'] + 288
        end = p['off'] + p['size']
        while sub + 8 <= end:
            ct, hsize, csize = struct.unpack_from('<HHI', arsc, sub)
            if csize == 0:
                break
            if ct == 0x0201:
                tid = arsc[sub + 8]
                res0 = arsc[sub + 9]
                cnt, es = struct.unpack_from('<II', arsc, sub + 12)
                lang, country = struct.unpack_from('<HH', arsc, sub + 20 + 8)
                p['types'].append({'tid': tid, 'res0': res0, 'cnt': cnt, 'es': es,
                                   'hdr': hsize, 'off': sub, 'lang': lang, 'country': country})
            sub += csize
    for p in pkgs:
        # 同一 type id 可能有多份配置，只取默认配置（language=0, country=0）
        best = {}
        for t in p['types']:
            cur = best.get(t['tid'])
            if cur is None or (t.get('lang', 0) == 0 and t.get('country', 0) == 0
                               and (cur.get('lang', 0) != 0 or cur.get('country', 0) != 0)):
                best[t['tid']] = t
        p['types'] = list(best.values())
    for p in pkgs:
        p['tp'] = Pool(arsc, p['off'] + p['type_strings'])
        p['kp'] = Pool(arsc, p['off'] + p['key_strings'])
    return pkgs


def entries(arsc, t, pkg):
    """返回 {entry_index: (name, value, dataType)}。"""
    out = {}
    base = t['off'] + t['es']
    arr = t['off'] + t['hdr']
    if t['res0'] & 0x01:  # FLAG_SPARSE
        for i in range(t['cnt']):
            eoff = struct.unpack_from('<I', arsc, arr + 4 * i)[0]
            p = base + eoff
            size, flags = struct.unpack_from('<HH', arsc, p)
            key = struct.unpack_from('<I', arsc, p + 4)[0]
            vsz, res0, dtype = struct.unpack_from('<HBB', arsc, p + 8)
            data = struct.unpack_from('<I', arsc, p + 12)[0]
            out[key] = (pkg['kp'][key], data, dtype)
    elif t['res0'] & 0x02:  # FLAG_OFFSET16：entry = key(u16) | flags(u16) | value(u32)
        for i in range(t['cnt']):
            o16 = struct.unpack_from('<H', arsc, arr + 4 * i)[0]
            p = base + o16 * 2
            key = struct.unpack_from('<H', arsc, p)[0]
            flags = struct.unpack_from('<H', arsc, p + 2)[0]
            data = struct.unpack_from('<I', arsc, p + 4)[0]
            out[i] = (pkg['kp'][key], data, flags >> 8)
    else:  # 经典稠密
        for i in range(t['cnt']):
            eoff = struct.unpack_from('<I', arsc, arr + 4 * i)[0]
            p = base + eoff
            size, flags = struct.unpack_from('<HH', arsc, p)
            key = struct.unpack_from('<I', arsc, p + 4)[0]
            vsz, res0, dtype = struct.unpack_from('<HBB', arsc, p + 8)
            data = struct.unpack_from('<I', arsc, p + 12)[0]
            out[i] = (pkg['kp'][key], data, dtype)
    return out


def main():
    apk = sys.argv[1]
    with zipfile.ZipFile(apk) as z:
        arsc = z.read('resources.arsc')
    pkgs = parse(arsc)
    args = [a for a in sys.argv[2:] if not a.startswith('--')]
    grep = None
    if '--grep' in sys.argv:
        grep = sys.argv[sys.argv.index('--grep') + 1]
        args = [a for a in args if a != grep]

    if not args and not grep:
        for p in pkgs:
            print('pkg id=0x%02x name=%s types=%d' % (p['id'], p['name'], len(p['types'])))
            for t in p['types']:
                print('   tid=%d(%s) res0=0x%02x cnt=%d' % (t['tid'], p['tp'][t['tid']], t['res0'], t['cnt']))
        return

    for p in pkgs:
        for t in p['types']:
            ents = entries(arsc, t, p)
            for idx, (nm, val, dt) in ents.items():
                rid = (p['id'] << 24) | (t['tid'] << 16) | idx
                if grep and grep.lower() not in nm.lower():
                    continue
                if args:
                    want = [int(a, 0) for a in args]
                    if rid not in want:
                        continue
                print('0x%08X %-14s %-34s type=0x%02x value=%s (0x%X)'
                      % (rid, p['name'], nm, dt, val, val))


if __name__ == '__main__':
    main()
