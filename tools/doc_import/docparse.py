"""Minimal MS-DOC (Word 97-2003) reader: main-document text in order, with
embedded OLE objects and pictures marked where they occur.

Output tokens: plain text, plus markers
  \x00EQ:<storage>\x00   OLE object (storage name in ObjectPool)
  \x00PIC\x00            inline/floating picture (not an OLE object)
"""
import struct

import olefile


def _u16(b, o): return struct.unpack_from('<H', b, o)[0]
def _u32(b, o): return struct.unpack_from('<I', b, o)[0]


SPRM_OPERAND = {0: 1, 1: 1, 2: 2, 3: 4, 4: 2, 5: 2, 7: 3}


def iter_sprms(grpprl):
    i = 0
    n = len(grpprl)
    while i + 2 <= n:
        sprm = _u16(grpprl, i)
        i += 2
        spra = (sprm >> 13) & 7
        if spra == 6:
            if sprm in (0xD606, 0xD608):  # sprmTDefTable etc: 2-byte size
                size = _u16(grpprl, i) - 1 if sprm == 0xD608 else grpprl[i]
                start = i + (2 if sprm == 0xD608 else 1)
            else:
                size = grpprl[i]
                start = i + 1
            yield sprm, grpprl[start:start + size]
            i = start + size
        else:
            size = SPRM_OPERAND[spra]
            yield sprm, grpprl[i:i + size]
            i += size


class Doc:
    def __init__(self, path):
        self.ole = olefile.OleFileIO(path)
        self.wd = self.ole.openstream('WordDocument').read()
        flags = _u16(self.wd, 0x0A)
        tbl = '1Table' if flags & 0x0200 else '0Table'
        self.table = self.ole.openstream(tbl).read()
        self.data = self.ole.openstream('Data').read() if self.ole.exists('Data') else b''

        o = 32
        csw = _u16(self.wd, o); o += 2 + csw * 2
        cslw = _u16(self.wd, o); o += 2
        rglw = o
        self.ccp_text = struct.unpack_from('<i', self.wd, rglw + 3 * 4)[0]
        o += cslw * 4
        cb = _u16(self.wd, o); o += 2
        self.fclcb = [(_u32(self.wd, o + 8 * k), _u32(self.wd, o + 8 * k + 4)) for k in range(cb)]

        self._read_pieces()
        self._read_chpx()
        self._read_papx()

    def _read_pieces(self):
        fc, lcb = self.fclcb[33]
        clx = self.table[fc:fc + lcb]
        i = 0
        while clx[i] == 0x01:
            i += 3 + _u16(clx, i + 1)
        assert clx[i] == 0x02
        lcb = _u32(clx, i + 1)
        plc = clx[i + 5:i + 5 + lcb]
        n = (lcb - 4) // 12
        cps = [_u32(plc, 4 * k) for k in range(n + 1)]
        self.pieces = []
        for k in range(n):
            pcd = plc[4 * (n + 1) + 8 * k: 4 * (n + 1) + 8 * k + 8]
            fcv = _u32(pcd, 2)
            compressed = bool(fcv & 0x40000000)
            fcv &= 0x3FFFFFFF
            if compressed:
                fcv //= 2
            self.pieces.append((cps[k], cps[k + 1], fcv, compressed))

    def _read_chpx(self):
        fc, lcb = self.fclcb[12]
        plc = self.table[fc:fc + lcb]
        n = (lcb - 4) // 8
        self.chpx_runs = []  # (fc_start, fc_end, grpprl)
        for k in range(n):
            pn = _u32(plc, 4 * (n + 1) + 4 * k) & 0x3FFFFF
            page = self.wd[pn * 512:(pn + 1) * 512]
            crun = page[511]
            for r in range(crun):
                a = _u32(page, 4 * r)
                b = _u32(page, 4 * (r + 1))
                off = page[4 * (crun + 1) + r] * 2
                grpprl = b''
                if off:
                    cbp = page[off]
                    grpprl = page[off + 1:off + 1 + cbp]
                self.chpx_runs.append((a, b, grpprl))
        self.chpx_runs.sort()
        self._run_starts = [r[0] for r in self.chpx_runs]

    def _read_papx(self):
        fc, lcb = self.fclcb[13]
        plc = self.table[fc:fc + lcb]
        n = (lcb - 4) // 8
        self.papx_runs = []
        for k in range(n):
            pn = _u32(plc, 4 * (n + 1) + 4 * k) & 0x3FFFFF
            page = self.wd[pn * 512:(pn + 1) * 512]
            crun = page[511]
            for r in range(crun):
                a = _u32(page, 4 * r)
                b = _u32(page, 4 * (r + 1))
                off = page[4 * (crun + 1) + 13 * r] * 2
                in_table = ttp = False
                if off:
                    cb = page[off]
                    if cb:
                        start, length = off + 1, 2 * cb - 1
                    else:
                        start, length = off + 2, 2 * page[off + 1]
                    grpprl = page[start + 2:start + length]  # skip istd
                    for sprm, op in iter_sprms(grpprl):
                        if sprm == 0x2416 and op:
                            in_table = op[0] == 1
                        elif sprm == 0x6649 and len(op) == 4:
                            in_table = in_table or _u32(op, 0) > 0
                        elif sprm in (0x2417, 0x244C) and op:
                            ttp = ttp or op[0] == 1
                self.papx_runs.append((a, b, in_table, ttp))
        self.papx_runs.sort()
        self._papx_starts = [r[0] for r in self.papx_runs]

    def para_props(self, fc):
        import bisect
        i = bisect.bisect_right(self._papx_starts, fc) - 1
        if i < 0:
            return False, False
        a, b, in_table, ttp = self.papx_runs[i]
        if not (a <= fc < b):
            return False, False
        return in_table, ttp

    def char_props(self, fc):
        import bisect
        i = bisect.bisect_right(self._run_starts, fc) - 1
        if i < 0:
            return {}
        a, b, grpprl = self.chpx_runs[i]
        if not (a <= fc < b):
            return {}
        cache = self.__dict__.setdefault('_props_cache', {})
        if i in cache:
            return cache[i]
        props = cache[i] = {}
        for sprm, op in iter_sprms(grpprl):
            if sprm == 0x6A03 and len(op) == 4:
                props['pic'] = _u32(op, 0)
            elif sprm == 0x080A:
                props['ole2'] = op[0] == 1
            elif sprm == 0x0855:
                props['spec'] = op[0] == 1
            elif sprm == 0x0856:
                props['obj'] = op[0] == 1
            elif sprm == 0x0838:
                props['vanish'] = op[0] == 1
            elif sprm == 0x2A48:
                props['iss'] = op[0]  # 1 superscript, 2 subscript
        return props

    def chars(self):
        """Yield (char, fc) for the main document text."""
        for cp0, cp1, fc0, compressed in self.pieces:
            if cp0 >= self.ccp_text:
                break
            cp1 = min(cp1, self.ccp_text)
            count = cp1 - cp0
            if compressed:
                raw = self.wd[fc0:fc0 + count]
                for j, byte in enumerate(raw):
                    yield bytes([byte]).decode('cp1252', errors='replace'), fc0 + j
            else:
                raw = self.wd[fc0:fc0 + 2 * count]
                for j in range(count):
                    yield chr(_u16(raw, 2 * j)), fc0 + 2 * j

    def tokens(self):
        """Text with field instructions removed and objects replaced by markers."""
        out = []
        # Each open field: [in_instruction, is_ole_object]
        field_stack = []
        for ch, fc in self.chars():
            o = ord(ch)
            if o == 0x13:
                field_stack.append([True, False])
                continue
            if o == 0x14:
                if field_stack:
                    field_stack[-1][0] = False
                    props = self.char_props(fc)
                    if props.get('ole2') and props.get('pic'):
                        field_stack[-1][1] = True
                        out.append(f"\x00EQ:_{props['pic']}\x00")
                continue
            if o == 0x15:
                if field_stack:
                    field_stack.pop()
                continue
            in_instr = any(f[0] for f in field_stack)
            in_ole_result = any(f[1] for f in field_stack)
            if in_instr or in_ole_result:
                continue
            if o in (0x01, 0x08):
                props = self.char_props(fc)
                if props.get('spec', o == 0x08):
                    out.append('\x00PIC\x00')
                continue
            iss = self.char_props(fc).get('iss', 0) if o >= 0x20 else 0
            if iss in (1, 2) and not ch.isspace():
                out.append(f'\x00{"SUP" if iss == 1 else "SUB"}:{ch}\x00')
                continue
            if o == 0x07:
                in_table, ttp = self.para_props(fc)
                # cell mark -> tab; row-end mark -> end of a table row
                # Some older tables carry no TTP flag on the row mark; a cell mark that
                # isn't inside a table paragraph is that row end.
                out.append('\x00ROW\x00\n' if ttp or not in_table else '\t')
            elif o == 0x0D and self.para_props(fc)[0]:
                out.append('\x00BR\x00')  # paragraph break inside a table cell
            elif o in (0x0D, 0x0B, 0x0C):
                out.append('\n')
            elif o == 0x1E:
                out.append('-')
            elif o in (0x1F, 0xAD):
                continue
            elif o == 0xA0:
                out.append(' ')
            elif o < 0x20 and o != 0x09:
                continue
            else:
                out.append(ch)
        return ''.join(out)

    def object_progid(self, storage):
        path = f'ObjectPool/{storage}/\x01CompObj'
        if not self.ole.exists(path):
            return None
        d = self.ole.openstream(path).read()
        # CompObj: header(28) then AnsiUserType, AnsiClipboardFormat, AnsiProgID (length-prefixed)
        try:
            o = 28
            vals = []
            for _ in range(3):
                n = _u32(d, o); o += 4
                if n == 0xFFFFFFFF or n == 0xFFFFFFFE:
                    o += 4
                    vals.append('')
                    continue
                vals.append(d[o:o + n].rstrip(b'\x00').decode('latin-1'))
                o += n
            return vals[2] or vals[0]
        except Exception:
            return None

    def equation_native(self, storage):
        path = f'ObjectPool/{storage}/Equation Native'
        if self.ole.exists(path):
            return self.ole.openstream(path).read()
        return None
