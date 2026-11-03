"""MTEF v3 (Microsoft Equation Editor 3.0) -> LaTeX."""
import re
import struct

END, LINE, CHAR, TMPL, PILE, MATRIX, EMBELL, RULER, FONT, SIZE = range(10)
SIZE_RECS = {10, 11, 12, 13, 14}

FN_TEXT, FN_FUNCTION, FN_VARIABLE, FN_LCGREEK, FN_UCGREEK, FN_SYMBOL, FN_VECTOR, FN_NUMBER = 1, 2, 3, 4, 5, 6, 7, 8
FN_MTEXTRA = 11


class Node:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def __repr__(self):
        d = {k: v for k, v in self.__dict__.items() if k != 'kind'}
        return f'{self.kind}{d}'


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, data):
        if len(data) < 28 + 5:
            raise ParseError('short')
        hdr_len = struct.unpack_from('<H', data, 0)[0]
        self.b = data
        self.i = hdr_len
        ver = self.b[self.i]
        if ver != 3:
            raise ParseError(f'MTEF version {ver}')
        self.i += 5

    def byte(self):
        if self.i >= len(self.b):
            raise ParseError('eof')
        v = self.b[self.i]
        self.i += 1
        return v

    def u16(self):
        v = struct.unpack_from('<H', self.b, self.i)[0]
        self.i += 2
        return v

    def nudge(self):
        dx, dy = self.byte(), self.byte()
        if dx == 128 and dy == 128:
            self.i += 4

    def parse(self):
        return self.object_list(top=True)

    def object_list(self, top=False):
        items = []
        while self.i < len(self.b):
            tag = self.byte()
            rtype, opts = tag & 0x0F, tag >> 4
            if rtype == END:
                return items
            node = self.record(rtype, opts)
            if node is not None:
                items.append(node)
        if top:
            return items
        raise ParseError('unterminated list')

    def record(self, rtype, opts):
        if rtype == LINE:
            if opts & 0x8:
                self.nudge()
            if opts & 0x4:
                self.i += 2
            if opts & 0x2:
                self.ruler()
            if opts & 0x1:
                return Node('line', items=[], null=True)
            return Node('line', items=self.object_list(), null=False)
        if rtype == CHAR:
            if opts & 0x8:
                self.nudge()
            tf = self.byte()
            ch = self.u16()
            emb = []
            if opts & 0x2:
                for e in self.object_list():
                    emb.append(e.etype)
            return Node('char', fn=tf - 128 if tf >= 128 else tf, ch=ch, emb=emb, auto=bool(opts & 0x1))
        if rtype == TMPL:
            if opts & 0x8:
                self.nudge()
            sel, var, _topts = self.byte(), self.byte(), self.byte()
            return Node('tmpl', sel=sel, var=var, items=self.object_list())
        if rtype == PILE:
            if opts & 0x8:
                self.nudge()
            self.byte(); self.byte()
            if opts & 0x2:
                self.ruler()
            return Node('pile', items=self.object_list())
        if rtype == MATRIX:
            if opts & 0x8:
                self.nudge()
            self.byte(); self.byte(); self.byte()
            rows, cols = self.byte(), self.byte()
            self.i += ((rows + 1) * 2 + 7) // 8
            self.i += ((cols + 1) * 2 + 7) // 8
            return Node('matrix', rows=rows, cols=cols, items=self.object_list())
        if rtype == EMBELL:
            if opts & 0x8:
                self.nudge()
            etype = self.byte()
            self.byte()  # v3 stores one more (unused) byte per embellishment
            return Node('embell', etype=etype)
        if rtype == RULER:
            self.ruler_body()
            return None
        if rtype == FONT:
            self.byte(); self.byte()
            while self.byte() != 0:
                pass
            return None
        if rtype == SIZE:
            lsize = self.byte()
            if lsize == 101:
                self.i += 2
            elif lsize == 100:
                self.i += 3
            else:
                self.i += 1
            return None
        if rtype in SIZE_RECS:
            return None
        raise ParseError(f'unknown record {rtype} at {self.i}')

    def ruler(self):
        tag = self.byte()
        if tag & 0x0F != RULER:
            raise ParseError('expected ruler')
        self.ruler_body()

    def ruler_body(self):
        n = self.byte()
        self.i += 3 * n


# ---------------------------------------------------------------- LaTeX

GREEK = {
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta', 'ε': r'\varepsilon', 'ζ': r'\zeta',
    'η': r'\eta', 'θ': r'\theta', 'ϑ': r'\vartheta', 'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda',
    'μ': r'\mu', 'ν': r'\nu', 'ξ': r'\xi', 'π': r'\pi', 'ϖ': r'\varpi', 'ρ': r'\rho', 'σ': r'\sigma',
    'ς': r'\varsigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\varphi', 'ϕ': r'\phi', 'χ': r'\chi',
    'ψ': r'\psi', 'ω': r'\omega', 'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
    'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Υ': r'\Upsilon', 'Φ': r'\Phi', 'Ψ': r'\Psi', 'Ω': r'\Omega',
}

SYMBOLS = {
    0x2212: '-', 0x2213: r'\mp', 0xB1: r'\pm', 0xD7: r'\cdot', 0x2219: r'\cdot', 0x22C5: r'\cdot',
    0x2022: r'\cdot', 0xF8: r'\div', 0xF7: r'\div', 0x2264: r'\le', 0x2265: r'\ge', 0x2260: r'\ne',
    0x2248: r'\approx', 0x2261: r'\equiv', 0x221E: r'\infty', 0x2208: r'\in', 0x2209: r'\notin',
    0x220B: r'\ni', 0x222A: r'\cup', 0x2229: r'\cap', 0x2282: r'\subset', 0x2283: r'\supset',
    0x2286: r'\subseteq', 0x2287: r'\supseteq', 0x2205: r'\varnothing', 0x2200: r'\forall',
    0x2203: r'\exists', 0x2192: r'\to', 0x2190: r'\leftarrow', 0x2194: r'\leftrightarrow',
    0x21D2: r'\Rightarrow', 0x21D0: r'\Leftarrow', 0x21D4: r'\Leftrightarrow', 0x2032: "'",
    0x2033: "''", 0xB0: r'^\circ', 0x2218: r'\circ', 0x2220: r'\angle', 0x22A5: r'\perp',
    0x2225: r'\parallel', 0x2016: r'\|', 0x2026: r'\ldots', 0x22EF: r'\cdots', 0x22EE: r'\vdots',
    0x2202: r'\partial', 0x2207: r'\nabla', 0x221A: r'\surd', 0x2211: r'\sum', 0x220F: r'\prod',
    0x222B: r'\int', 0x2245: r'\cong', 0x223C: r'\sim', 0x221D: r'\propto', 0x2227: r'\wedge',
    0x2228: r'\vee', 0xAC: r'\neg', 0x2295: r'\oplus', 0x2297: r'\otimes', 0x2329: r'\langle',
    0x232A: r'\rangle', 0x27E8: r'\langle', 0x27E9: r'\rangle', 0x2245 + 0: r'\cong',
    0x25B3: r'\triangle', 0x2206: r'\triangle', 0x2312: r'\frown', 0x2322: r'\frown', 0x2225 + 0: r'\parallel',
    0x2194 + 0: r'\leftrightarrow', 0x2195: r'\updownarrow', 0x2191: r'\uparrow', 0x2193: r'\downarrow',
    0x21D1: r'\Uparrow', 0x21D3: r'\Downarrow', 0x2223: r'\mid', 0x2224: r'\nmid', 0x226A: r'\ll', 0x226B: r'\gg',
    0x2284: r'\not\subset', 0x2234: r'\therefore', 0x2235: r'\because', 0x2135: r'\aleph', 0x2118: r'\wp',
    0x2111: r'\Im', 0x211C: r'\Re', 0x2205 + 0: r'\varnothing', 0x2116: r'\text{№}', 0x2030: r'\text{‰}',
    0x2215: '/', 0x2044: '/', 0x2010: '-', 0x2013: '-', 0x2014: '-', 0x2019: "'",
    0x201C: '``', 0x201D: "''", 0xAB: r'\text{«}', 0xBB: r'\text{»}',
    ord('{'): r'\{', ord('}'): r'\}', ord('%'): r'\%', ord('#'): r'\#', ord('&'): r'\&', ord('$'): r'\$',
    0x21D5: r'\Updownarrow', ord('_'): r'\_', ord('~'): r'\sim', ord('^'): r'\wedge', ord('\\'): r'\backslash',
}

# MT Extra private-use codes seen in Equation Editor 3.0 files.
MTEXTRA = {
    0xEC00: r'\ldots', 0xEB00: r'\cdots', 0xEC01: r'\cdots', 0xEC02: r'\vdots', 0xEC03: r'\ddots',
    0xEB01: r'\cdots', 0xEB02: r'\vdots', 0xEB03: r'\ddots', 0xEC04: r'\ldots',
    0xEF02: r'\,', 0xEF03: r'\;', 0xEF04: r'\;', 0xEF05: r'\,', 0xEF01: r'\,', 0xEF00: '',
    0xEB05: r'\frown', 0xE900: r'\frown', 0xEC05: r'\frown', 0xEB04: r'\ ',
    0xEC07: '|', 0xEC08: '|', 0xEC09: r'\parallel ', 0xEC0A: r'\parallel ',
}

FUNC_NAMES = {'sin', 'cos', 'tg', 'ctg', 'tan', 'cot', 'sec', 'cosec', 'csc', 'arcsin', 'arccos', 'arctg',
              'arcctg', 'arctan', 'arccot', 'log', 'lg', 'ln', 'lim', 'max', 'min', 'exp', 'sh', 'ch', 'th',
              'cth', 'sgn', 'det', 'deg', 'sup', 'inf', 'mod', 'arg', 'Ln', 'Arg', 'const', 'D', 'E', 'pr'}
# Longest first so "arcctg" wins over "ctg" and "tg".
VAR_FUNCS = ('arcsin', 'arccos', 'arcctg', 'arctg', 'cosec', 'sin', 'cos', 'ctg', 'tg', 'log', 'lg', 'ln')
LATEX_FUNCS = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'log', 'lg', 'ln',
               'lim', 'max', 'min', 'exp', 'sh', 'ch', 'th', 'det', 'deg', 'sup', 'inf', 'arg'}

FENCES = {
    0: (r'\langle', r'\rangle'), 1: ('(', ')'), 2: (r'\{', r'\}'), 3: ('[', ']'), 4: ('|', '|'),
    5: (r'\|', r'\|'), 6: (r'\lfloor', r'\rfloor'), 7: (r'\lceil', r'\rceil'), 8: ('[', '['),
    9: (']', ']'), 10: (']', '['), 11: ('[', ')'), 12: ('(', ']'),
}

EMBELL_TEX = {
    2: r'\dot', 3: r'\ddot', 4: r'\dddot', 5: "'", 6: "''", 7: "'", 8: r'\tilde', 9: r'\hat',
    10: r'\not', 11: r'\vec', 12: r'\overleftarrow', 13: r'\overleftrightarrow', 14: r'\vec',
    15: r'\overleftarrow', 16: r'\bar', 17: r'\bar', 18: "'''", 19: r'\overset{\frown}', 20: r'\underset{\smile}',
}


LOOKALIKE = dict(zip('аеорсухкАВЕКМНОРСТХ', 'aeopcyxkABEKMHOPCTX'))


class Unsupported(Exception):
    pass


class Emitter:
    def __init__(self):
        self.warnings = []

    def char_tex(self, node):
        tex = self._char_tex(node)
        # Keep a space after control words so "\\in" + "Z" doesn't become "\\inZ";
        # tidy() drops the spaces that aren't needed.
        if re.search(r'\\[a-zA-Z]+$', tex):
            tex += ' '
        return tex

    def _char_tex(self, node):
        c = node.ch
        fn = node.fn
        if c in SYMBOLS:
            return SYMBOLS[c]
        if fn == FN_MTEXTRA or 0xE000 <= c <= 0xF8FF:
            if c in MTEXTRA:
                return MTEXTRA[c]
            self.warnings.append(f'mtextra {c:#x}')
            return ''
        if c in SYMBOLS:
            return SYMBOLS[c]
        s = chr(c)
        if s in GREEK:
            return GREEK[s] + ' '
        if fn == FN_TEXT:
            if c == 0x20:
                return r'\ '
            if 0x400 <= c <= 0x4FF or (0xC0 <= c <= 0xFF):
                if 0xC0 <= c <= 0xFF:
                    s = bytes([c]).decode('cp1251')
                return r'\text{' + s + '}'
            return s
        if c < 0x20:
            return ''
        if 0x400 <= c <= 0x4FF:
            if getattr(node, 'cyr', None) == 'latin':
                return LOOKALIKE[s]
            return r'\text{' + s + '}'
        if 0xC0 <= c <= 0xFF and fn in (FN_VARIABLE, FN_FUNCTION):
            return r'\text{' + bytes([c]).decode('cp1251') + '}'
        if c > 0x7F and not s.isalnum():
            self.warnings.append(f'char {c:#x} fn{fn}')
        return s

    @staticmethod
    def mark_cyrillic(items):
        """A run of Cyrillic letters made only of Latin look-alikes ("АВС", "х") is
        a variable typed on a Russian keyboard -> Latin; any other run is a word -> text."""
        run = []

        def flush():
            if run:
                latin = all(chr(x.ch) in LOOKALIKE for x in run)
                for x in run:
                    x.cyr = 'latin' if latin else 'text'
                run.clear()

        for x in items:
            if x.kind == 'char' and 0x400 <= x.ch <= 0x4FF and chr(x.ch).isalpha():
                run.append(x)
            else:
                flush()
        flush()

    def items(self, items):
        self.mark_cyrillic(items)
        out = []
        i = 0
        n = len(items)
        prev_script = None
        while i < n:
            node = items[i]
            if node.kind == 'char' and node.fn in (FN_VARIABLE, FN_TEXT) and chr(node.ch).isascii() and chr(node.ch).isalpha():
                # "tg", "ctg", "lg" typed in the variable font -> upright function names
                j = i
                run = ''
                while (j < n and items[j].kind == 'char' and items[j].fn == node.fn and not items[j].emb
                       and chr(items[j].ch).isascii() and chr(items[j].ch).isalpha()):
                    run += chr(items[j].ch)
                    j += 1
                fname = next((f for f in VAR_FUNCS if run.startswith(f)), None)
                if fname:
                    out.append(self.func_name(fname))
                    i += len(fname)
                    prev_script = None
                    continue
            if node.kind == 'char' and node.fn == FN_FUNCTION and chr(node.ch).isalpha():
                # Group consecutive function-font letters into one name.
                j = i
                name = ''
                while j < n and items[j].kind == 'char' and items[j].fn == FN_FUNCTION and chr(items[j].ch).isalpha() and not items[j].emb:
                    name += chr(items[j].ch)
                    j += 1
                if name:
                    out.append(self.func_name(name))
                    i = j
                    continue
            piece = self.node(node)
            is_script = node.kind == 'tmpl' and node.sel in (15, 44)
            if is_script:
                piece = piece.replace('^{}', '').replace('_{}', '')
                if not piece:
                    i += 1
                    continue
                # Two scripts in a row (x_{i}_{j}) need an empty base for the second.
                if prev_script and piece[0] in prev_script:
                    piece = '{}' + piece
                prev_script = piece[0] if piece[0] != '{' else piece[2]
                if piece.startswith('_{') and '}^{' in piece:
                    prev_script = '_^'
            else:
                prev_script = None
            out.append(piece)
            i += 1
        return ''.join(out)

    def func_name(self, name):
        if name in LATEX_FUNCS:
            return '\\' + name + ' '
        if name in FUNC_NAMES or len(name) > 1:
            return r'\operatorname{' + name + '} '
        return r'\mathrm{' + name + '}'

    def line(self, node):
        if node is None or node.kind != 'line' or node.null:
            return ''
        tex = self.items(node.items).strip()
        if tex[:1] in ('^', '_'):
            tex = '{}' + tex
        return tex

    def slots(self, node):
        lines = [x for x in node.items if x.kind in ('line', 'pile')]
        chars = [x for x in node.items if x.kind == 'char']
        return lines, chars

    def slot(self, x):
        if x is None:
            return ''
        if x.kind == 'pile':
            return self.pile(x)
        return self.line(x)

    def pile(self, node):
        rows = [self.slot(x) for x in node.items if x.kind in ('line', 'pile')]
        if len(rows) == 1:
            return rows[0]
        return r'\begin{gathered}' + r' \\ '.join(rows) + r'\end{gathered}'

    def node(self, node):
        k = node.kind
        if k == 'char':
            base = self.char_tex(node)
            for e in node.emb:
                t = EMBELL_TEX.get(e)
                if t is None:
                    continue
                if t.startswith("'"):
                    base = base + t
                elif t == r'\not':
                    base = r'\not' + base
                else:
                    base = t + '{' + base + '}'
            return base
        if k == 'line':
            return self.line(node)
        if k == 'pile':
            return self.pile(node)
        if k == 'matrix':
            cells = [self.slot(x) for x in node.items if x.kind in ('line', 'pile')]
            rows = []
            for r in range(node.rows):
                rows.append(' & '.join(cells[r * node.cols:(r + 1) * node.cols]))
            return r'\begin{matrix}' + r' \\ '.join(rows) + r'\end{matrix}'
        if k == 'tmpl':
            return self.tmpl(node)
        return ''

    def tmpl(self, node):
        """Equation Editor 3.0 (MTEF v3) template selectors, verified against the source files."""
        sel, var = node.sel, node.var
        lines, chars = self.slots(node)
        s = [self.slot(x) for x in lines]
        g = lambda k: s[k] if k < len(s) else ''

        if sel in FENCES:
            left, right = FENCES[sel]
            body = g(0)
            if sel == 5 and var in (1, 2):
                # "AB ∥ CD": a one-sided double bar is the parallel sign
                return (r'\parallel ' + body) if var == 1 else (body + r'\parallel ')
            inner = body
            if inner.startswith(r'\begin{gathered}'):
                inner = inner[len(r'\begin{gathered}'):-len(r'\end{gathered}')]
            if sel == 2 and var == 1:
                return r'\begin{cases}' + inner + r'\end{cases}'
            if sel == 3 and var == 1:
                return r'\left[\begin{gathered}' + inner + r'\end{gathered}\right.'
            lt = r'\left' + (left if var in (0, 1) else '.')
            rt = r'\right' + (right if var in (0, 2) else '.')
            return f'{lt} {body} {rt}'
        if sel == 13:  # radical: [radicand, index]
            if g(1):
                return r'\sqrt[' + g(1) + ']{' + g(0) + '}'
            return r'\sqrt{' + g(0) + '}'
        if sel == 14:  # fraction: [numerator, denominator]
            return r'\frac{' + g(0) + '}{' + g(1) + '}'
        if sel in (15, 44):  # scripts: [sub, sup]; var 0 sup, 1 sub, 2 both
            if sel == 44 or var == 0:
                return '^{' + g(1) + '}'
            if var == 1:
                return '_{' + g(0) + '}'
            return '_{' + g(0) + '}^{' + g(1) + '}'
        if sel == 16:
            return r'\underline{' + g(0) + '}'
        if sel == 17:
            return r'\overline{' + g(0) + '}'
        if sel == 24:  # integral with limits: [integrand, lower, upper]
            return r'\int' + self.limits(g(1), g(2)) + ' ' + g(0)
        if sel == 28:  # horizontal brace with label: [body, label]
            if any(c.ch == 0xFE37 for c in chars):
                return r'\overbrace{' + g(0) + '}^{' + g(1) + '}'
            return r'\underbrace{' + g(0) + '}_{' + g(1) + '}'
        if sel == 39:  # limit-style operator: [name, lower, upper]
            return r'\operatorname*{' + g(0) + '}' + self.limits(g(1), g(2)) + ' '
        if sel == 42:  # base with scripts: [pre-sub, pre-sup, sup, base]
            pre = ('{}_{' + g(0) + '}' if g(0) else '') + ('{}^{' + g(1) + '}' if g(1) else '')
            return pre + '{' + g(3) + '}^{' + g(2) + '}'
        if sel == 47:
            return g(0)
        raise Unsupported(f'template {sel}/{var}')

    def limits(self, lo, hi):
        out = ''
        if lo:
            out += '_{' + lo + '}'
        if hi:
            out += '^{' + hi + '}'
        return out


def to_latex(data):
    """Return (latex, warnings). Raises ParseError/Unsupported on failure."""
    tree = Parser(data).parse()
    em = Emitter()
    tex = em.items(tree).strip()
    return tidy(tex), em.warnings


def tidy(tex):
    import re
    tex = re.sub(r'\s+', ' ', tex).strip()
    tex = re.sub(r'(\\[a-zA-Z]+) (?=[^a-zA-Z])', r'\1', tex)
    while True:
        merged = re.sub(r'(\\text\{[^{}]*)\}\\text\{', r'\1', tex)
        if merged == tex:
            break
        tex = merged
    return tex


def dump(data):
    return Parser(data).parse()
