#!/usr/bin/env python3
"""dexstatic.py — 读取 DEX 中某个类的 static 字段名与 static_values 真值。

用法:
    python3 dexstatic.py <dex文件> <类描述符, 如 Landroid/server/Flags;> [--field 子串]

修复过的坑（与 dexsv.py 相比）:
  * DEX header 偏移: string_ids_off=0x3c, type_ids_off=0x44, proto=0x4c, field_ids_off=0x54,
    method_ids_off=0x5c, class_defs_size=0x60, class_defs_off=0x64。
  * class_data 里的 field_idx / method_idx 是 **相对前一条的差值**，必须累加
    （dexsv.py 漏了这一步，所以取出来的字段名/值全是乱的）。
  * field_ids_item: class_idx(u2) type_idx(u2) name_idx(u4) —— 类型索引是 u2。
  * encoded_value 头字节: (value_arg<<4) | value_type；
    0x00 byte / 0x02 short / 0x03 char / 0x04 int / 0x06 long / 0x10 float / 0x11 double /
    0x17 string / 0x18 type / 0x1c array / 0x1e null / 0x1f boolean（boolean 值即 value_arg!=0）。
"""
import struct
import sys


class Dex:
    def __init__(self, path):
        self.d = open(path, "rb").read()
        self.sids_off = self.u4(0x3C)
        self.tids_off = self.u4(0x44)
        self.fids_off = self.u4(0x54)
        self.mids_off = self.u4(0x5C)
        self.cds_off = self.u4(0x64)
        self.cds_size = self.u4(0x60)

    def u1(self, o):
        return self.d[o]

    def u2(self, o):
        return struct.unpack_from("<H", self.d, o)[0]

    def u4(self, o):
        return struct.unpack_from("<I", self.d, o)[0]

    def uleb(self, o):
        r = 0
        s = 0
        while True:
            b = self.d[o]
            o += 1
            r |= (b & 0x7F) << s
            s += 7
            if not b & 0x80:
                return r, o

    def string(self, idx):
        off = self.u4(self.sids_off + 4 * idx)
        _, o = self.uleb(off)
        end = self.d.index(b"\x00", o)
        return self.d[o:end].decode("utf-8", "replace")

    def type_desc(self, idx):
        return self.string(self.u4(self.tids_off + 4 * idx))

    def field(self, idx):
        o = self.fids_off + 8 * idx
        return self.type_desc(self.u2(o)), self.type_desc(self.u2(o + 2)), self.string(self.u4(o + 4))

    def find_class(self, desc):
        for i in range(self.cds_size):
            o = self.cds_off + 32 * i
            if self.type_desc(self.u4(o)) == desc:
                return o
        return None

    def read_value(self, o):
        h = self.u1(o)
        o += 1
        t = h & 0x0F
        arg = h >> 4
        if t == 0x1E:
            return None, o
        if t == 0x1F:
            return (arg != 0), o
        if t == 0x17:
            return self.string(self.u4(o)), o + 4
        if t == 0x18:
            return self.type_desc(self.u4(o)), o + 4
        if t == 0x04:
            return struct.unpack_from("<i", self.d, o)[0], o + 4
        if t == 0x02:
            return struct.unpack_from("<h", self.d, o)[0], o + 2
        if t == 0x00:
            return self.u1(o), o + 1
        if t == 0x06:
            return struct.unpack_from("<q", self.d, o)[0], o + 8
        if t == 0x10:
            return struct.unpack_from("<f", self.d, o)[0], o + 4
        if t == 0x11:
            return struct.unpack_from("<d", self.d, o)[0], o + 8
        if t == 0x03:
            return self.u2(o), o + 2
        if t == 0x15:  # method_type: proto_idx
            return ("method_type", self.u4(o)), o + 4
        if t == 0x16:  # method_handle: (method_idx, type_idx)
            return ("method_handle", self.u4(o), self.u4(o + 4)), o + 8
        if t == 0x19:  # field
            return ("field_ref", self.u4(o)), o + 4
        if t == 0x1A:  # method
            return ("method_ref", self.u4(o)), o + 4
        if t == 0x1B:  # enum
            return ("enum", self.u4(o)), o + 4
        if t == 0x1D:  # annotation: type_idx + element[]
            typ = self.type_desc(self.u4(o))
            o += 4
            n, o = self.uleb(o)
            elems = []
            for _ in range(n):
                _, o = self.uleb(o)          # name_idx
                v, o = self.read_value(o)     # value
                elems.append(v)
            return ("annotation", typ, elems), o
        if t == 0x1C:
            n, o = self.uleb(o)
            vals = []
            for _ in range(n):
                v, o = self.read_value(o)
                vals.append(v)
            return vals, o
        raise ValueError("unknown encoded_value type 0x%02x at %d" % (t, o - 1))

    def static_values(self, desc):
        cd = self.find_class(desc)
        if cd is None:
            return None
        cdo = self.u4(cd + 24)
        svo = self.u4(cd + 28)
        sf, o = self.uleb(cdo)
        ifs, o = self.uleb(o)
        dm, o = self.uleb(o)
        vm, o = self.uleb(o)
        names = []
        acc = 0
        for _ in range(sf):
            diff, o = self.uleb(o)
            _, o = self.uleb(o)
            acc += diff
            names.append(self.string(self.u4(self.fids_off + 8 * acc + 4)))
        if svo == 0:
            return [(n, "<no static_values>") for n in names]
        n, o = self.uleb(svo)
        vals = []
        for _ in range(n):
            v, o = self.read_value(o)
            vals.append(v)
        return list(zip(names, vals))


if __name__ == "__main__":
    path = sys.argv[1]
    desc = sys.argv[2]
    filt = sys.argv[3] if len(sys.argv) > 3 else None
    dx = Dex(path)
    res = dx.static_values(desc)
    if res is None:
        print("class not found:", desc)
        sys.exit(1)
    for name, val in res:
        if filt and filt not in name:
            continue
        print("   %-46s = %r" % (name, val))
