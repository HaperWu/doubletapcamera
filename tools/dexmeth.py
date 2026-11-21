#!/usr/bin/env python3
"""dexmeth.py — 找到引用指定字符串的 DEX 方法，并打印该方法里的全部字符串常量与被调用的方法。

用法:
  python3 dexmeth.py <dex文件> <子串>            # 列出引用该子串的所有方法
  python3 dexmeth.py <dex文件> <子串> --dump     # 打印这些方法内的字符串常量 + 调用到的其他方法
"""
import sys, struct

def uleb128(b, o):
    r = 0; s = 0
    while True:
        x = b[o]; o += 1
        r |= (x & 0x7f) << s
        if not (x & 0x80): return r, o
        s += 7

class Dex:
    def __init__(self, path):
        self.b = b = open(path, 'rb').read()
        g = lambda off: struct.unpack_from('<I', b, off)[0]
        self.string_ids_size = g(0x38); self.string_ids_off = g(0x3c)
        self.type_ids_size   = g(0x40); self.type_ids_off   = g(0x44)
        self.proto_ids_size  = g(0x48); self.proto_ids_off  = g(0x4c)
        self.field_ids_size  = g(0x50); self.field_ids_off  = g(0x54)
        self.method_ids_size = g(0x58); self.method_ids_off = g(0x5c)
        self.class_defs_size = g(0x60); self.class_defs_off = g(0x64)
        self.strings = self._read_strings()
        self.types   = self._read_types()
        self.methods = self._read_methods()
        self.fields = self._read_fields()

    def _read_fields(self):
        b = self.b; out = []
        for i in range(self.field_ids_size):
            c, t, n = struct.unpack_from('<HHI', b, self.field_ids_off + 8*i)
            out.append((self.types[c], self.strings[n]))
        return out

    def _read_strings(self):
        b = self.b; out = []
        for i in range(self.string_ids_size):
            off = struct.unpack_from('<I', b, self.string_ids_off + 4*i)[0]
            _, o = uleb128(b, off)
            e = b.index(b'\x00', o)
            out.append(b[o:e].decode('utf-8', 'replace'))
        return out

    def _read_types(self):
        b = self.b
        return [self.strings[struct.unpack_from('<I', b, self.type_ids_off+4*i)[0]] for i in range(self.type_ids_size)]

    def _read_methods(self):
        b = self.b; out = []
        for i in range(self.method_ids_size):
            c, p, n = struct.unpack_from('<HHI', b, self.method_ids_off + 8*i)
            out.append((self.types[c], self.strings[n]))
        return out

    # ---------- 指令长度表（单位：16-bit code unit） ----------
    SIZE = [1]*256
    for o in (0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23,
              0x29,0x2d,0x2e,0x2f,0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,
              0x39,0x3a,0x3b,0x3c,0x3d,0x52,0x53,0x54,0x55,0x56,0x57,0x58,0x59,
              0x5a,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x62,0x63,0x64,0x65,0x66,
              0x67,0x68,0x69,0x6a,0x6b,0x6c,0x6d,0x6e,0x6f,0x70,0x71,0x72,
              0x74,0x75,0x76,0x77,0x78,0x90,0x91,0x92,0x93,0x94,0x95,0x96,0x97,
              0x98,0x99,0x9a,0x9b,0x9c,0x9d,0x9e,0x9f,0xa0,0xa1,0xa2,0xa3,0xa4,
              0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf,
              0xd0,0xd1,0xd2,0xd3,0xd4,0xd5,0xd6,0xd7,0xd8,0xd9,0xda,0xdb,0xdc,
              0xdd,0xde,0xdf,0xe0,0xe1,0xe2,0xfe,0xff):
        SIZE[o] = 2
    for o in (0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c,
              0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78,0xfa,0xfb,0xfc,0xfd):
        SIZE[o] = 3
    SIZE[0x18] = 5
    SIZE[0x00] = 1
    # 修正：以下操作码在初版表中缺失或长度写错，会导致指令流错位
    SIZE[0x1f] = 1            # monitor-exit
    SIZE[0x21] = 2            # instance-of
    for o in range(0x44, 0x52):   # aget/aput 系列
        SIZE[o] = 2
    SIZE[0x73] = 3            # invoke-virtual/range
    SIZE[0x7c] = 2            # binop
    for o in (0x7f, 0x80, 0x81, 0x82):  # binop/lit16, binop/lit8
        SIZE[o] = 2
    SIZE[0xfa] = 4            # invoke-polymorphic
    SIZE[0xfb] = 4            # invoke-polymorphic/range

    def _iter_methods_with_code(self):
        """产出 (class_desc, method_name, code_off)"""
        b = self.b
        for i in range(self.class_defs_size):
            base = self.class_defs_off + 32*i
            class_idx, _, _, _, _, _, class_data_off, _ = struct.unpack_from('<8I', b, base)
            if not class_data_off: continue
            cdesc = self.types[class_idx]
            o = class_data_off
            sf, o = uleb128(b, o); inf, o = uleb128(b, o)
            dm, o = uleb128(b, o); vm, o = uleb128(b, o)
            for _ in range(sf): _, o = uleb128(b, o); _, o = uleb128(b, o)
            for _ in range(inf): _, o = uleb128(b, o); _, o = uleb128(b, o)
            for count in (dm, vm):
                midx = 0
                for _ in range(count):
                    d, o = uleb128(b, o); _, o = uleb128(b, o); code_off, o = uleb128(b, o)
                    midx += d
                    if code_off:
                        yield cdesc, self.methods[midx][1], code_off

    def code_strings(self, code_off):
        b = self.b
        insns_size = struct.unpack_from('<I', b, code_off + 12)[0]
        insns_off = code_off + 16
        out = []; calls = []; frefs = []
        i = 0
        while i < insns_size:
            op = b[insns_off + 2*i]
            if op == 0x1a:
                idx = struct.unpack_from('<H', b, insns_off + 2*i + 2)[0]
                if idx < len(self.strings): out.append(self.strings[idx])
                i += 2
            elif op == 0x1b:
                idx = struct.unpack_from('<I', b, insns_off + 2*i + 2)[0]
                if idx < len(self.strings): out.append(self.strings[idx])
                i += 3
            elif 0x52 <= op <= 0x6d:
                idx = struct.unpack_from('<H', b, insns_off + 2*i + 2)[0]
                if idx < len(self.fields):
                    fc, fn = self.fields[idx]
                    frefs.append(f"{fc}->{fn}")
                i += 2
            elif op in (0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78):
                idx = struct.unpack_from('<H', b, insns_off + 2*i + 2)[0]
                if idx < len(self.methods): calls.append(self.methods[idx])
                i += 3
            else:
                i += self.SIZE[op]
        self._last_frefs = frefs
        return out, calls

def main():
    path, needle = sys.argv[1], sys.argv[2]
    dump = '--dump' in sys.argv
    d = Dex(path)
    hits = []
    for cdesc, mname, code_off in d._iter_methods_with_code():
        strings, calls = d.code_strings(code_off)
        if any(needle in s for s in strings):
            hits.append((cdesc, mname, strings, calls))
    print(f"# 命中 {len(hits)} 个方法 (needle={needle!r})")
    for cdesc, mname, strings, calls in hits:
        print(f"\n=== {cdesc}->{mname} ===")
        if dump:
            uniq = []
            for s in strings:
                if s not in uniq: uniq.append(s)
            print("  -- 字符串常量 --")
            for s in uniq: print("   ", repr(s))
            print("  -- 调用到的外部方法(去重) --")
            seen = []
            for c, n in calls:
                if (c, n) not in seen: seen.append((c, n))
            for c, n in seen: print("   ", f"{c}->{n}")

if __name__ == '__main__':
    main()
