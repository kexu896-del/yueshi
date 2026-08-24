#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电子书文本提取脚本（纯标准库）
支持：epub / mobi / azw3(KF8) / prc / txt / md / html

用法：
  python extract_book_text.py <书文件路径> [-o 输出目录]
  # 默认输出：书同目录下 <书名>.txt
  # 批量：python extract_book_text.py <文件夹>  → 处理文件夹内全部电子书

说明：
  - epub: 解压 zip，提取所有 html/xhtml 正文
  - mobi(旧格式): PalmDoc LZ77 解压
  - azw3/KF8: 定位 BOUNDARY 记录，提取内嵌 EPUB 的 HTML
  - HUFF/CDIC 压缩或 DRM 加密的文件无法提取 → 提示用 Calibre 转换
"""

import os
import re
import sys
import struct
import zipfile
from html.parser import HTMLParser

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class TextExtract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr", "blockquote"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip == 0:
            self.parts.append(data)


def strip_html(s):
    p = TextExtract()
    try:
        p.feed(s)
    except Exception:
        pass
    t = "".join(p.parts)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()


def extract_epub(path):
    try:
        return _extract_epub_zip(path)
    except Exception:
        pass
    # 兜底：文件缺中央目录/EOCD（截断下载）时按本地文件头顺序恢复
    with open(path, "rb") as f:
        data = f.read()
    out = []
    pos = 0
    n = len(data)
    while pos + 30 <= n and data[pos:pos + 4] == b"PK\x03\x04":
        flags, method = struct.unpack_from("<HH", data, pos + 6)
        comp, uncomp = struct.unpack_from("<II", data, pos + 18)
        nlen, elen = struct.unpack_from("<HH", data, pos + 26)
        name = data[pos + 30:pos + 30 + nlen].decode("utf-8", "replace")
        start = pos + 30 + nlen + elen
        if flags & 0x8:
            nxt = data.find(b"PK\x03\x04", start)
            if nxt < 0:
                break
            chunk = data[start:nxt]
            if chunk[-16:-12] == b"PK\x07\x08":
                chunk = chunk[:-16]
            elif chunk[-12:-8] == b"PK\x07\x08":
                chunk = chunk[:-12]
            pos = nxt
        else:
            chunk = data[start:start + comp]
            pos = start + comp
        if method == 8:
            import zlib
            try:
                chunk = zlib.decompress(chunk)
            except Exception:
                chunk = zlib.decompress(chunk, -15)
        if name.lower().endswith((".html", ".xhtml", ".htm")):
            out.append(strip_html(chunk.decode("utf-8", "replace")))
    return "\n\n".join(out)


def _extract_epub_zip(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.lower().endswith((".html", ".xhtml", ".htm")):
                try:
                    out.append(strip_html(z.read(n).decode("utf-8", "replace")))
                except Exception:
                    pass
    return "\n\n".join(out)


def palmdb_records(data):
    nrec, = struct.unpack(">H", data[76:78])
    recs = []
    for i in range(nrec):
        off, = struct.unpack(">I", data[78 + i * 8:82 + i * 8])
        end, = struct.unpack(">I", data[86 + i * 8:90 + i * 8])
        recs.append(data[off:end])
    return recs


def palmdoc_decompress(recs, text_len):
    data = b"".join(recs)
    out = bytearray()
    i, n = 0, len(data)
    while i < n and len(out) < text_len + 4096:
        c = data[i]
        i += 1
        if 1 <= c <= 8:
            if i + c > n:
                c = n - i
            out += data[i:i + c]
            i += c
        elif c < 128:
            out.append(c)
        elif c < 192:
            if i >= n:
                break
            d = data[i]
            i += 1
            dist = ((c << 8) | d) >> 3 & 0x7FF
            l = (d & 7) + 3
            for _ in range(l):
                out.append(out[-dist] if len(out) >= dist else 0x20)
        else:
            out.append(0x20)
            out.append(c ^ 0x80)
    return bytes(out[:text_len])


class HuffcdicReader:
    """HUFF/CDIC 解压（移植自 KindleUnpack mobi_uncompress.py，GPLv3）"""

    def load_huff(self, huff):
        if huff[0:8] != b"HUFF\x00\x00\x00\x18":
            raise ValueError("invalid huff header")
        off1, off2 = struct.unpack_from(b">LL", huff, 8)

        def dict1_unpack(v):
            codelen = v & 0x1F
            term = (v & 0x80) != 0
            maxcode = v >> 8
            maxcode = ((maxcode + 1) << (32 - codelen)) - 1
            return (codelen, term, maxcode)

        self.dict1 = [dict1_unpack(v) for v in
                      struct.unpack_from(b">256L", huff, off1)]
        dict2 = struct.unpack_from(b">64L", huff, off2)
        self.mincode, self.maxcode = (), ()
        for codelen, mincode in enumerate((0,) + dict2[0::2]):
            self.mincode += (mincode << (32 - codelen),)
        for codelen, maxcode in enumerate((0,) + dict2[1::2]):
            self.maxcode += (((maxcode + 1) << (32 - codelen)) - 1,)
        self.dictionary = []

    def load_cdic(self, cdic):
        if cdic[0:8] != b"CDIC\x00\x00\x00\x10":
            raise ValueError("invalid cdic header")
        phrases, bits = struct.unpack_from(b">LL", cdic, 8)
        n = min(1 << bits, phrases - len(self.dictionary))

        def getslice(off):
            blen, = struct.unpack_from(b">H", cdic, 16 + off)
            sl = cdic[18 + off:18 + off + (blen & 0x7FFF)]
            return (sl, blen & 0x8000)

        self.dictionary += [getslice(o) for o in
                            struct.unpack_from(b">%dH" % n, cdic, 16)]

    def unpack(self, data):
        bitsleft = len(data) * 8
        data += b"\x00\x00\x00\x00\x00\x00\x00\x00"
        pos = 0
        x, = struct.unpack_from(b">Q", data, pos)
        n = 32
        s = b""
        while True:
            if n <= 0:
                pos += 4
                x, = struct.unpack_from(b">Q", data, pos)
                n += 32
            code = (x >> n) & ((1 << 32) - 1)
            codelen, term, maxcode = self.dict1[code >> 24]
            if not term:
                while code < self.mincode[codelen]:
                    codelen += 1
                maxcode = self.maxcode[codelen]
            n -= codelen
            bitsleft -= codelen
            if bitsleft < 0:
                break
            r = (maxcode - code) >> (32 - codelen)
            sl, flag = self.dictionary[r]
            if not flag:
                self.dictionary[r] = None
                sl = self.unpack(sl)
                self.dictionary[r] = (sl, 1)
            s += sl
        return s


def _get_trailing_size(data):
    num = 0
    for v in data[::-1]:
        num = (num << 7) | (v & 0x7F)
        if (v & 0x80) == 0:
            break
    return num


def extract_huffcdic(recs, rec0, text_len, text_enc):
    # 字段偏移以 record 0 为基准（PalmDoc 16 字节 + MOBI 头）
    huffoff, huffnum = struct.unpack_from(b">LL", rec0, 0x70)
    reccnt, = struct.unpack_from(b">H", rec0, 8)
    if recs[huffoff][:4] != b"HUFF":
        for i, r in enumerate(recs):
            if r[:4] == b"HUFF":
                huffoff = i
                break
    reader = HuffcdicReader()
    reader.load_huff(recs[huffoff])
    for i in range(1, huffnum):
        reader.load_cdic(recs[huffoff + i])
    out = b""
    for i in range(1, reccnt + 1):
        out += reader.unpack(recs[i])
    if text_len and text_len < len(out):
        out = out[:text_len]
    enc = "utf-8" if text_enc == 65001 else "cp1252"
    return out.decode(enc, "replace")


def extract_mobi(path):
    with open(path, "rb") as f:
        data = f.read()
    # PalmDB type+creator 在偏移 60-67，文件名区可能被商家改写
    if data[60:68] != b"BOOKMOBI" and data[:8] != b"BOOKMOBI":
        return "[不是有效的 mobi/azw3 文件]"
    recs = palmdb_records(data)
    pd = recs[0][:16]
    comp, = struct.unpack(">H", pd[0:2])
    text_len, = struct.unpack(">I", pd[4:8])
    mh = recs[0][16:16 + 232]
    mobi_type, text_enc = 0, 65001
    if mh[:4] == b"MOBI":
        mobi_type, = struct.unpack(">I", mh[8:12])
        text_enc, = struct.unpack(">I", mh[12:16])
    # HUFF/CDIC 压缩（17480 = 'DH'）
    if comp == 17480:
        return strip_html(extract_huffcdic(recs, recs[0], text_len, text_enc))
    # KF8：找 BOUNDARY 记录，其后为内嵌 EPUB 数据
    for i, r in enumerate(recs):
        if r[:8] == b"BOUNDARY":
            raw = b"".join(recs[i + 1:])
            s = raw.decode("utf-8", "replace")
            if "<html" in s or "<body" in s or "<p" in s:
                return strip_html(s)
            break
    if mobi_type == 248:
        return "[KF8 未找到 BOUNDARY，请用 Calibre 转 epub]"
    if comp == 1:
        txt = b"".join(recs[1:])[:text_len]
    elif comp == 2:
        txt = palmdoc_decompress(recs[1:], text_len)
    else:
        return "[压缩类型 %d 暂不支持，请用 Calibre 转 epub]" % comp
    enc = "utf-8" if text_enc == 65001 else "cp1252"
    s = txt.decode(enc, "replace")
    if "<" in s[:2000] and ">" in s[:2000]:
        s = strip_html(s)
    return s


def extract_plain(path, ext):
    with open(path, "rb") as f:
        b = f.read()
    s = b.decode("utf-8", "replace")
    if ext in (".html", ".htm"):
        return strip_html(s)
    return s


def extract_one(path, out_dir):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".epub":
            text = extract_epub(path)
        elif ext in (".mobi", ".azw3", ".prc"):
            text = extract_mobi(path)
        elif ext in (".txt", ".md", ".markdown", ".html", ".htm"):
            text = extract_plain(path, ext)
        else:
            print(f"跳过（不支持格式）: {os.path.basename(path)}")
            return None
    except Exception as e:
        text = f"[提取失败: {e}]"
    name = os.path.splitext(os.path.basename(path))[0]
    safe = re.sub(r'[\\/:*?"<>|]', "_", name)
    out = os.path.join(out_dir, safe + ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✓ {os.path.basename(path)} → {out}（{len(text)} 字符）")
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python extract_book_text.py <文件|文件夹> [-o 输出目录]")
        return
    out_dir = None
    if "-o" in args:
        i = args.index("-o")
        out_dir = args[i + 1]
        args = args[:i] + args[i + 2:]
    src = args[0]
    if not out_dir:
        out_dir = src if os.path.isdir(src) else os.path.dirname(src)
    os.makedirs(out_dir, exist_ok=True)
    exts = (".epub", ".mobi", ".azw3", ".prc", ".txt", ".md", ".markdown", ".html", ".htm")
    if os.path.isdir(src):
        files = [os.path.join(src, f) for f in os.listdir(src)
                 if f.lower().endswith(exts)]
    else:
        files = [src]
    for f in files:
        extract_one(f, out_dir)


if __name__ == "__main__":
    main()
