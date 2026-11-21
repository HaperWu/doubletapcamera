#!/usr/bin/env python3
"""disasm.py — 极简 DEX 反汇编：打印某方法中 const/4、const/16、const、const-string、invoke 的顺序。

用法: python3 disasm.py <dex> <类名片段> <方法名>
"""
import sys, struct
from dexmeth import Dex

def s16(x): return x - 0x10000 if x >= 0x8000 else x
def s32(x): return x - 0x100000000 if x >= 0x80000000 else x

def main():
    path, cls, meth = sys.argv[1], sys.argv[2], sys.argv[3]
    d = Dex(path)
    for cdesc, mname, off in d._iter_methods_with_code():
        if cls not in cdesc or mname != meth: continue
        b = d.b
        insns_size = struct.unpack_from('<I', b, off + 12)[0]
        insns_off = off + 16
        i = 0
        print(f"=== {cdesc}->{mname} (insns={insns_size}) ===")
        while i < insns_size:
            p = insns_off + 2*i
            op = b[p]
            if op == 0x12:   # const/4 vA, #+B
                b1 = b[p+1]
                val = b1 & 0x0f
                if val >= 8: val -= 16
                print(f"  {i:04x} const/4    v{b1 & 0x0f}, #{val}")
                i += 1; continue
            if op == 0x13:   # const/16
                v = s16(struct.unpack_from('<h', b, p+2)[0])
                print(f"  {i:04x} const/16   v{b[p+1]}, #{v}")
                i += 2; continue
            if op == 0x14:   # const
                v = s32(struct.unpack_from('<i', b, p+2)[0])
                print(f"  {i:04x} const      v{b[p+1]}, #{v}")
                i += 3; continue
            if op == 0x1a:
                idx = struct.unpack_from('<H', b, p+2)[0]
                print(f"  {i:04x} const-string v{b[p+1]}, {d.strings[idx]!r}")
                i += 2; continue
            if op in (0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78):
                idx = struct.unpack_from('<H', b, p+2)[0]
                c, n = d.methods[idx]
                print(f"  {i:04x} invoke     {c}->{n}")
                i += 3; continue
            i += d.SIZE[op]
        return
    print('method not found')

if __name__ == '__main__':
    main()
