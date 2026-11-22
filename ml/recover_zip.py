"""Recover the complete images from a zip whose download was cut off (no central directory).

    ml\\.venv\\Scripts\\python -I ml\\recover_zip.py OUT_DIR file1.zip [file2.zip ...]

Kaggle downloads of the King dataset arrived cut off (505 and 765 of 965 MB). A zip stores every file behind a
"local header", so complete files can still be read one by one. Only files that decompress fully AND open as a
valid image are written; files that already exist in OUT_DIR are kept. Paths are normalised to
<class>/<default|real_world>/<file> (the leading "images/" folders are dropped).
"""
import io
import mmap
import os
import re
import struct
import sys
import zlib
from collections import Counter

from PIL import Image


def recover(out_dir, zip_path, stats):
    with open(zip_path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as m:
        offsets = [x.start() for x in re.finditer(rb"PK\x03\x04", m)] + [len(m)]
        for a, b in zip(offsets, offsets[1:]):
            if a + 30 > len(m):
                continue
            _, _, flag, method, _, _, _, csize, usize, nlen, elen = struct.unpack("<IHHHHHIIIHH", m[a:a + 30])
            name = m[a + 30:a + 30 + nlen].decode("utf8", "replace")
            if not name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            raw = m[a + 30 + nlen + elen:b]
            try:
                if method == 0:
                    data = raw[:usize] if (usize and usize != 0xFFFFFFFF and not flag & 8) else raw
                elif method == 8:
                    d = zlib.decompressobj(-15)
                    data = d.decompress(raw)
                    if not d.eof:
                        stats["incomplete"] += 1
                        continue
                else:
                    stats["other_method"] += 1
                    continue
                Image.open(io.BytesIO(data)).load()          # must be a complete, valid image
            except Exception:
                stats["broken"] += 1
                continue
            parts = name.split("/")
            while parts and parts[0] == "images":
                parts = parts[1:]
            dest = os.path.join(out_dir, *parts)
            if os.path.exists(dest):
                stats["already_there"] += 1
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            stats["recovered"] += 1


if __name__ == "__main__":
    out = sys.argv[1]
    for zp in sys.argv[2:]:
        s = Counter()
        recover(out, zp, s)
        print(zp, dict(s))
