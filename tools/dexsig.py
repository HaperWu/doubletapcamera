#!/usr/bin/env python3
"""dexsig.py — 打印指定类名下所有方法的完整签名（返回类型 + 参数类型 + 参数名）。

用法: python3 dexsig.py <dex文件> <类描述符前缀...>
"""
import struct
import sys


def uleb128(b, o):
    r = 0
    s = 0
    while True:
        x = b[o]
        o += 1
        r |= (x & 0x7f) << s
        if not (x & 0x80):
            return r, o
        s += 7


class Dex:
    def __init__(self, path):
        self.b = b = open(path, 'rb').read()
        g = lambda off: struct.unpack_from('<I', b, off)[0]
        self.string_ids_size = g(0x38); self.string_ids_off = g(0x3c)
        self.type_ids_size = g(0x40); self.type_ids_off = g(0x44)
        self.proto_ids_size = g(0x48); self.proto_ids_off = g(0x4c)
        self.method_ids_size = g(0x58); self.method_ids_off = g(0x5c)
        self.class_defs_size = g(0x60); self.class_defs_off = g(0x64)
        self.strings = self._read_strings()
        self.types = self._read_types()
        self.methods = self._read_methods()
        self.protos = self._read_protos()

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
            out.append((self.types[c], self.strings[n], p))
        return out

    def _read_protos(self):
        b = self.b; out = []
        for i in range(self.proto_ids_size):
            shorty, ret, params = struct.unpack_from('<III', b, self.proto_ids_off + 12*i)
            plist = []
            if params:
                n = struct.unpack_from('<I', b, params)[0]
                for k in range(n):
                    t = struct.unpack_from('<H', b, params + 4 + 2*k)[0]
                    plist.append(self.types[t])
            out.append((self.types[ret], plist))
        return out

    def sig(self, mid):
        c, n, p = self.methods[mid]
        ret, params = self.protos[p]
        return f"{c}->{n}({', '.join(params)}) : {ret}"


def main():
    path = sys.argv[1]
    prefixes = sys.argv[2:]
    d = Dex(path)
    seen = set()
    for mid, (c, n, p) in enumerate(d.methods):
        if not any(c.startswith(pf) or c.endswith(pf) for pf in prefixes):
            continue
        key = (c, n, p)
        if key in seen:
            continue
        seen.add(key)
        print(d.sig(mid))


if __name__ == '__main__':
    main()
