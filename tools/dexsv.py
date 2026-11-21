#!/usr/bin/env python3
"""dexsv.py — decode DEX class static field VALUES (static_values_item).

Usage: dexsv.py <dex-file> <class-descriptor> [class-descriptor ...]
Prints each static field of the class with its decoded constant value.
"""
import struct
import sys

TYPES = {
    0x00: "byte", 0x02: "short", 0x03: "char", 0x04: "int", 0x06: "long",
    0x10: "float", 0x11: "double", 0x15: "method_type", 0x16: "method_handle",
    0x17: "string", 0x18: "type", 0x19: "field", 0x1a: "method", 0x1b: "enum",
    0x1c: "array", 0x1d: "annotation", 0x1e: "null", 0x1f: "boolean",
}
NUMERIC = {0x00, 0x02, 0x03, 0x04, 0x06, 0x10, 0x11}


class Dex:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.d = f.read()
        d = self.d
        self.string_ids_size, self.string_ids_off = struct.unpack_from("<II", d, 0x38)
        self.type_ids_size, self.type_ids_off = struct.unpack_from("<II", d, 0x40)
        self.proto_ids_size, self.proto_ids_off = struct.unpack_from("<II", d, 0x48)
        self.field_ids_size, self.field_ids_off = struct.unpack_from("<II", d, 0x50)
        self.method_ids_size, self.method_ids_off = struct.unpack_from("<II", d, 0x58)
        self.class_defs_size, self.class_defs_off = struct.unpack_from("<II", d, 0x60)

    def uleb(self, off):
        result = 0
        shift = 0
        while True:
            b = self.d[off]
            off += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                return result, off
            shift += 7

    def string(self, idx):
        off = struct.unpack_from("<I", self.d, self.string_ids_off + 4 * idx)[0]
        # ULEB128 utf16 size, then MUTF-8 bytes, NUL terminated
        _, p = self.uleb(off)
        end = self.d.index(b"\x00", p)
        return self.d[p:end].decode("utf-8", "replace")

    def type_desc(self, idx):
        return self.string(struct.unpack_from("<I", self.d, self.type_ids_off + 4 * idx)[0])

    def field(self, idx):
        f = self.field_ids_off + 8 * idx
        cls_idx, type_idx, name_idx = struct.unpack_from("<HHI", self.d, f)
        return self.type_desc(cls_idx), self.type_desc(type_idx), self.string(name_idx)

    def method(self, idx):
        m = self.method_ids_off + 8 * idx
        cls_idx, proto_idx, name_idx = struct.unpack_from("<HHI", self.d, m)
        return self.type_desc(cls_idx), self.string(name_idx)

    def find_class(self, desc):
        for i in range(self.class_defs_size):
            off = self.class_defs_off + 32 * i
            class_idx = struct.unpack_from("<I", self.d, off)[0]
            if self.type_desc(class_idx) == desc:
                return off
        return None

    def read_value(self, off):
        """Read one encoded_value; return (value, new_off)."""
        b = self.d[off]
        off += 1
        vtype = b & 0x1F
        varg = b >> 5
        name = TYPES.get(vtype, "?0x%02x" % vtype)
        if vtype in NUMERIC:
            n = varg + 1
            raw = self.d[off:off + n]
            off += n
            if vtype == 0x1F:  # boolean
                return (varg == 1), off
            if vtype == 0x00:
                return (struct.unpack("<b", raw)[0]), off
            if vtype == 0x02:
                return (struct.unpack("<h", raw[:2])[0], raw[:2]), off
            if vtype == 0x03:
                return (struct.unpack("<H", raw[:2])[0],), off
            if vtype == 0x04:
                return (struct.unpack("<i", raw)[0],), off
            if vtype == 0x06:
                return (struct.unpack("<q", raw)[0],), off
            if vtype == 0x10:
                return (struct.unpack("<f", raw)[0],), off
            if vtype == 0x11:
                return (struct.unpack("<d", raw)[0],), off
            return (raw,), off
        if vtype == 0x17:
            sidx = struct.unpack_from("<I", self.d, off)[0]
            off += 4
            return self.string(sidx), off
        if vtype == 0x18:
            tidx = struct.unpack_from("<I", self.d, off)[0]
            off += 4
            return self.type_desc(tidx), off
        if vtype == 0x19:
            fidx = struct.unpack_from("<I", self.d, off)[0]
            off += 4
            return "field:" + str(self.field(fidx)), off
        if vtype == 0x1a:
            midx = struct.unpack_from("<I", self.d, off)[0]
            off += 4
            return "method:" + str(self.method(midx)), off
        if vtype == 0x1b:
            fidx = struct.unpack_from("<I", self.d, off)[0]
            off += 4
            return "enum:" + str(self.field(fidx)), off
        if vtype == 0x1e:
            return None, off
        if vtype == 0x1c:  # array
            size, off = self.uleb(off)
            vals = []
            for _ in range(size):
                v, off = self.read_value(off)
                vals.append(v)
            return vals, off
        if vtype == 0x1d:  # annotation
            type_idx, off = self.uleb(off)
            size, off = self.uleb(off)
            for _ in range(size):
                _, off = self.uleb(off)  # name_idx
                _, off = self.read_value(off)
            return "annotation:" + self.type_desc(type_idx), off
        raise ValueError("unhandled value_type 0x%02x at 0x%x" % (vtype, off - 1))

    def class_static_values(self, desc):
        coff = self.find_class(desc)
        if coff is None:
            return None
        class_data_off, static_values_off = struct.unpack_from("<II", self.d, coff + 24)
        static_field_idxs = []
        if class_data_off:
            p = class_data_off
            static_fields_size, p = self.uleb(p)
            inst_size, p = self.uleb(p)
            direct_methods, p = self.uleb(p)
            virtual_methods, p = self.uleb(p)
            idx = 0
            for _ in range(static_fields_size):
                diff, p = self.uleb(p)
                _, p = self.uleb(p)  # access flags
                idx += diff
                static_field_idxs.append(idx)
            # skip instance fields + methods (not needed for static values)
        vals = []
        if static_values_off:
            size = struct.unpack_from("<I", self.d, static_values_off)[0]
            off = static_values_off + 4
            for _ in range(size):
                v, off = self.read_value(off)
                vals.append(v)
        out = []
        for i, fidx in enumerate(static_field_idxs):
            _, _, fname = self.field(fidx)
            out.append((fname, vals[i] if i < len(vals) else "<missing>"))
        return out


def main():
    dex = Dex(sys.argv[1])
    for desc in sys.argv[2:]:
        print("== %s ==" % desc)
        res = dex.class_static_values(desc)
        if res is None:
            print("   <class not found>")
            continue
        for name, val in res:
            print("   %-46s = %r" % (name, val))


if __name__ == "__main__":
    main()
