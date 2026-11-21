#!/usr/bin/env python3
"""dexcls.py — 列出指定类(或类名前缀)下的所有方法及其字符串常量/外部调用。

用法: python3 dexcls.py <dex文件> <类名前缀1> [类名前缀2 ...] [--calls]
"""
import sys
from dexmeth import Dex

def main():
    path = sys.argv[1]
    prefixes = [a for a in sys.argv[2:] if not a.startswith('--')]
    show_calls = '--calls' in sys.argv
    d = Dex(path)
    for cdesc, mname, code_off in d._iter_methods_with_code():
        if not any(cdesc.startswith(p) or cdesc.endswith(p) for p in prefixes):
            continue
        strings, calls = d.code_strings(code_off)
        uniq = []
        for s in strings:
            if s not in uniq: uniq.append(s)
        print(f"\n--- {cdesc}->{mname} ---")
        for s in uniq:
            print("    S:", repr(s))
        if show_calls:
            seen = []
            for c, n in calls:
                if (c, n) not in seen: seen.append((c, n))
            for c, n in seen:
                print("    C:", f"{c}->{n}")

if __name__ == '__main__':
    main()
