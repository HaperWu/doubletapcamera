#!/usr/bin/env python3
"""Minimal DEX reader: dump class static field values + string constants."""
import struct, sys, zipfile, io, re

class Dex:
    def __init__(self, data):
        self.d = data
        (self.string_ids_size, self.string_ids_off, self.type_ids_size, self.type_ids_off,
         self.proto_ids_size, self.proto_ids_off, self.field_ids_size, self.field_ids_off,
         self.method_ids_size, self.method_ids_off, self.class_defs_size,
         self.class_defs_off) = struct.unpack_from('<12I', data, 0x38)
        self.strings = [self._str(i) for i in range(self.string_ids_size)]
        self.types = [self.strings[struct.unpack_from('<I', data, self.type_ids_off + 4*i)[0]]
                      for i in range(self.type_ids_size)]

    def _str(self, idx):
        off = struct.unpack_from('<I', self.d, self.string_ids_off + 4*idx)[0]
        p = off
        # uleb128 length
        while self.d[p] & 0x80:
            p += 1
        p += 1
        e = self.d.index(b'\x00', p)
        return self.d[p:e].decode('utf-8', 'replace')

    def _uleb(self, p):
        r = 0; s = 0
        while True:
            b = self.d[p]; p += 1
            r |= (b & 0x7f) << s
            if not (b & 0x80): return r, p
            s += 7

    def class_def(self, i):
        base = self.class_defs_off + 32*i
        (class_idx, access, super_idx, iface_off, src_idx, anno_off,
         class_data_off, static_values_off) = struct.unpack_from('<8I', self.d, base)
        return dict(class_idx=class_idx, access=access, super=super_idx,
                    source=self.strings[src_idx] if src_idx != 0xffffffff else None,
                    class_data_off=class_data_off, static_values_off=static_values_off)

    def field_info(self, idx):
        base = self.field_ids_off + 8*idx
        cidx, tidx, nidx = struct.unpack_from('<HHI', self.d, base)
        return self.types[cidx], self.types[tidx], self.strings[nidx]

    def class_fields(self, ci):
        """returns (static_fields[(name,type)], instance_fields, methods)"""
        cd = self.class_def(ci)
        if not cd['class_data_off']:
            return [], [], []
        p = cd['class_data_off']
        sf, if_, dm, vm = 0, 0, 0, 0
        sf, p = self._uleb(p); if_, p = self._uleb(p)
        dm, p = self._uleb(p); vm, p = self._uleb(p)
        statics = []
        idx = 0
        for _ in range(sf):
            d, p = self._uleb(p); idx += d
            fl, p = self._uleb(p)
            statics.append((idx, fl))
        insts = []
        idx = 0
        for _ in range(if_):
            d, p = self._uleb(p); idx += d
            fl, p = self._uleb(p)
            insts.append((idx, fl))
        methods = []
        idx = 0
        for _ in range(dm + vm):
            d, p = self._uleb(p); idx += d
            fl, p = self._uleb(p)
            code, p = self._uleb(p)
            methods.append((idx, code))
        return statics, insts, methods

    def _value(self, vt, p):
        """read one encoded_value of type vt at p -> (python value, new p)"""
        if vt == 0x17:   # string
            idx, = struct.unpack_from('<I', self.d, p); p += 4
            return self.strings[idx], p
        if vt == 0x04:   # int
            return struct.unpack_from('<i', self.d, p)[0], p + 4
        if vt == 0x02:   # short
            return struct.unpack_from('<h', self.d, p)[0], p + 2
        if vt == 0x00:   # byte
            return struct.unpack_from('<b', self.d, p)[0], p + 1
        if vt == 0x03:   # char
            return struct.unpack_from('<H', self.d, p)[0], p + 2
        if vt == 0x06:   # long
            return struct.unpack_from('<q', self.d, p)[0], p + 8
        if vt == 0x10:   # float
            return struct.unpack_from('<f', self.d, p)[0], p + 4
        if vt == 0x11:   # double
            return struct.unpack_from('<d', self.d, p)[0], p + 8
        if vt in (0x15, 0x18):  # method type / type
            return self.types[struct.unpack_from('<H', self.d, p)[0]], p + 2
        if vt in (0x16, 0x19, 0x1a, 0x1b):  # method handle / field / method / enum
            return '<idx>', p + 4
        if vt == 0x1e:   # null
            return None, p
        if vt == 0x1f:   # boolean
            return None, p
        return '<type %#x>' % vt, p

    def static_values(self, ci):
        cd = self.class_def(ci)
        off = cd['static_values_off']
        if not off:
            return []
        size, p = self._uleb(off)
        vals = []
        for _ in range(size):
            arg = self.d[p]; p += 1
            vt = arg & 0x1f; varg = arg >> 5
            if vt == 0x1f:
                vals.append(bool(varg)); continue
            if vt == 0x1d:   # array
                n, p = self._uleb(p)
                for _ in range(n):
                    a2 = self.d[p]; p += 1
                    t2 = a2 & 0x1f
                    if t2 == 0x1f:
                        vals.append(bool(a2 >> 5)); continue
                    v, p = self._value(t2, p)
                    vals.append(v)
                continue
            if vt == 0x1c:   # annotation
                ti, p = self._uleb(p)
                n, p = self._uleb(p)
                for _ in range(n):
                    a2 = self.d[p]; p += 1
                    t2 = a2 & 0x1f
                    if t2 == 0x1f:
                        continue
                    _, p = self._value(t2, p)
                continue
            v, p = self._value(vt, p)
            vals.append(v)
        return vals

def load_dexes(path):
    """path: .jar/.apk/.dex -> list of Dex"""
    data = None
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        out = []
        for n in z.namelist():
            if n.endswith('.dex'):
                out.append(Dex(z.read(n)))
        return out
    return [Dex(open(path, 'rb').read())]

def main():
    path = sys.argv[1]
    pattern = sys.argv[2] if len(sys.argv) > 2 else None
    dexes = load_dexes(path)
    for di, dex in enumerate(dexes):
        for ci in range(dex.class_defs_size):
            cd = dex.class_def(ci)
            cname = dex.types[cd['class_idx']]
            if pattern and not re.search(pattern, cname):
                continue
            statics, insts, methods = dex.class_fields(ci)
            if not statics:
                continue
            vals = dex.static_values(ci)
            print(f'\n=== [{di}] {cname} (source={cd["source"]}) ===')
            for i, (fidx, flags) in enumerate(statics):
                fc, ft, fn = dex.field_info(fidx)
                v = vals[i] if i < len(vals) else '<none>'
                print(f'   {fn} : {ft} = {v!r}')
        if not pattern:
            break

if __name__ == '__main__':
    main()
