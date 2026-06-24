#!/usr/bin/env python3
"""Adds <|end|> to stop sequences in aegis-cli.py"""
import os, sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else \
         os.path.expanduser("~/workspace/BitNet/src/aegis-cli.py")

SEARCH  = '"stop":           ["<|user|>", "<|system|>"],'
REPLACE = '"stop":           ["<|user|>", "<|system|>", "<|end|>", "<|im_end|>"],'

src = open(TARGET).read()
if SEARCH not in src:
    print("[TRIT_NEG] stop line not found — check file")
    sys.exit(1)

open(TARGET+".bak","w").write(src)
open(TARGET,"w").write(src.replace(SEARCH, REPLACE, 1))
print("[TRIT_POS] stop tokens updated")
