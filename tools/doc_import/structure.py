"""Split converted documents into subsections -> theory paragraphs + A-E tasks."""
import os
import re

ROW_MARK = '\x00ROW\x00'
BR_MARK = '\x00BR\x00'

LETTERS = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E',
           'А': 'A', 'В': 'B', 'С': 'C', 'Д': 'D', 'Е': 'E', 'Б': 'B'}
LETTER_CLASS = 'ABCDEАВСДЕБ'

HEADER_RE = re.compile(r'^\s*(\d{2})\.(\d{2})\.?\s*(?=\S)(.*)$')
ANSWER_RE = re.compile(
    r'Правильн\w*\s+ответ\w*\s*[:\-–.]?\s*\(?\s*\$?\s*(?:\\text\{)?\s*([' + LETTER_CLASS + r'])(?![а-яА-Яa-zA-Z])', re.I)
OPTION_RE = re.compile(r'(?:(?<=^)|(?<=[\s\t.;,]))([' + LETTER_CLASS + r'])\s*\)')
GATHERED_OPTS_RE = re.compile(r'\$\\begin\{gathered\}\s*a\)(.*?)\\end\{gathered\}\$', re.S)
QNUM_RE = re.compile(r'^\s*(\d{1,3})\s*[.)]\s*')


def latex_escape(t):
    out = []
    for c in t:
        if c in '{}%#&$_^\\':
            out.append('\\' + c if c not in '\\^' else {'\\': r'\backslash ', '^': r'\wedge '}[c])
        elif 0x400 <= ord(c) <= 0x4FF:
            out.append(r'\text{' + c + '}')
        else:
            out.append(c)
    return ''.join(out)


def render(tokens, eqs):
    """Replace object markers with $latex$; mark unknown objects/pictures."""
    def rep(m):
        sid = m.group(1)
        if sid not in eqs:
            return '⟦?⟧'
        tex = eqs[sid]
        return f'${tex}$' if tex else ''
    text = re.sub(r'\x00EQ:(_\d+)\x00', rep, tokens)
    text = text.replace('\x00PIC\x00', '⟦PIC⟧')

    # Runs of super/subscript plain-text characters ("х4", "75" + "0") -> $^{4}$ / $_{2}$
    def script(m):
        kind = '^' if m.group(1) == 'SUP' else '_'
        chars = ''.join(re.findall(r'\x00(?:SUP|SUB):(.)\x00', m.group(0)))
        return f'${kind}{{{latex_escape(chars)}}}$'
    text = re.sub(r'(?:\x00(SUP|SUB):.\x00)(?:\x00\1:.\x00)*', script, text)
    # Adjacent formulas: "$a$$b$" -> "$a\ b$" so "$$" never appears.
    while '$$' in text:
        text = text.replace('$$', r'\ ')
    return text


def find_subsections(text, file_major):
    lines = text.split('\n')
    heads = []
    prev_minor = None
    for i, line in enumerate(lines):
        m = HEADER_RE.match(line)
        if not m:
            continue
        major, minor, title = int(m.group(1)), int(m.group(2)), m.group(3).strip()
        if not title or not title[0].isalpha():
            continue
        if prev_minor is None:
            if i > 5:
                continue
        elif not (prev_minor < minor <= prev_minor + 2):
            continue
        heads.append((i, minor, title))
        prev_minor = minor
    if not heads:
        return []
    if heads[0][0] > 0:
        # Header on line 0 missing (e.g. "06.01.Линейные"): treat start as first subsection
        pass
    out = []
    for k, (i, minor, title) in enumerate(heads):
        j = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        out.append({'code': f'{file_major:02d}.{minor:02d}', 'title': title, 'lines': lines[i + 1:j]})
    return out


def clean_inline(s):
    s = s.replace(ROW_MARK, '').replace(BR_MARK, ' ').replace('\t', ' ')
    s = re.sub(r'[  ]+', ' ', s)
    return s.strip()


def clean_option(s):
    s = clean_inline(s)
    s = re.sub(r'^[\s.:;,]+', '', s)
    s = re.sub(r'[\s.;,]+$', '', s)
    # "$x$." -> "$x$"
    return s.strip()


def split_options(block):
    """block: text after the prompt. Returns {letter: text} or None."""
    parts = OPTION_RE.split(block)
    # parts: [before, L1, text1, L2, text2, ...]
    opts = {}
    order = []
    for k in range(1, len(parts) - 1, 2):
        letter = LETTERS[parts[k].upper() if parts[k] in 'abcde' else parts[k]]
        if letter in opts:
            return None, None
        opts[letter] = clean_option(parts[k + 1])
        order.append(letter)
    return opts, order


def first_question_line(lines, first_answer):
    """Where the test starts: the first numbered line followed by an answer key within
    a few lines, with no worked example in between (theory also has numbered lists)."""
    answers = [i for i, l in enumerate(lines) if ANSWER_RE.search(l)]
    for i, line in enumerate(lines):
        if not QNUM_RE.match(line):
            continue
        nxt = next((a for a in answers if a >= i), None)
        if nxt is None or nxt - i > 30:
            continue
        between = lines[i + 1:nxt]
        if any(l.strip().startswith(('Пример', 'Решение', 'Ответ')) for l in between):
            continue
        if not any(OPTION_RE.search(l) or GATHERED_OPTS_RE.search(l) for l in lines[i:nxt]):
            continue
        return i
    # fallback: right above the options of the first answered question
    k = first_answer
    while k >= 0 and not OPTION_RE.search(lines[k]):
        k -= 1
    while k > 0 and OPTION_RE.search(lines[k - 1]):
        k -= 1
    return max(k - 1, 0)


def parse_subsection(sub):
    lines = sub['lines']
    answer_idx = [i for i, l in enumerate(lines) if ANSWER_RE.search(l)]
    tasks, problems = [], []
    theory_end = len(lines)
    start = None
    if answer_idx:
        theory_end = start = first_question_line(lines, answer_idx[0])
    prev = start
    for ai in answer_idx:
        block_lines = lines[prev:ai + 1]
        prev = ai + 1
        ans_line = lines[ai]
        m = ANSWER_RE.search(ans_line)
        answer = LETTERS[m.group(1)]
        body = '\n'.join(block_lines).replace(ROW_MARK, '').replace(BR_MARK, ' ')
        body = body[:body.rfind('Правильн')] if 'Правильн' in body else body
        # Prompt: text before the first option label
        om = OPTION_RE.search(body)
        gm = GATHERED_OPTS_RE.search(body)
        if om:
            prompt = body[:om.start()]
            opts, order = split_options(body[om.start():])
        elif gm:
            # options typed inside one formula: $\begin{gathered}a)0 \\ b)4 ...\end{gathered}$
            prompt = body[:gm.start()]
            items = re.split(r'\s*\\\\\s*', 'a)' + gm.group(1))
            opts, order = {}, []
            for item in items:
                im = re.match(r'\s*([a-e])\)\s*(.*)$', item, re.S)
                if not im:
                    opts = None
                    break
                letter = im.group(1).upper()
                value = clean_option(im.group(2))
                opts[letter] = f'${value}$' if value else ''
                order.append(letter)
            if not opts:
                problems.append(('bad-gathered', body[:200]))
                continue
        else:
            problems.append(('no-options', body[:200]))
            continue
        if opts is None:
            problems.append(('dup-label', body[:200]))
            continue
        # Keep only the last numbered item: earlier ones are worked problems without options.
        plines = prompt.strip().split('\n')
        last_num = max((k for k, l in enumerate(plines) if QNUM_RE.match(l)), default=0)
        prompt = '\n'.join(plines[last_num:])
        prompt = QNUM_RE.sub('', prompt.strip(), count=1)
        prompt = '\n'.join(clean_inline(l) for l in prompt.split('\n') if clean_inline(l))
        tasks.append({'prompt': prompt, 'opts': opts, 'order': order, 'answer': answer})
    theory = lines[:theory_end]
    return theory, tasks, problems


def table_row(raw):
    cells = raw.replace(ROW_MARK, '').split('\t')
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    out = []
    for c in cells:
        parts = [clean_inline(x) for x in c.split(BR_MARK)]
        out.append('<br>'.join(x for x in parts if x))
    return out


def theory_paragraphs(title, lines):
    """Split theory into paragraphs at indented short heading lines.

    Body items are plain lines, or a table: '[table]\n' + rows joined by newlines,
    cells by tabs, in-cell line breaks as <br>.
    """
    paras = []
    cur_title, cur = title, []
    table = []

    def flush_table():
        if table:
            width = max(len(r) for r in table)
            rows = [r + [''] * (width - len(r)) for r in table]
            if width >= 2 or len(rows) >= 2:
                cur.append('[table]\n' + '\n'.join('\t'.join(r) for r in rows))
            else:
                cur.extend(c for r in rows for c in r if c)
            table.clear()

    for raw in lines:
        if ROW_MARK in raw:
            row = table_row(raw)
            if any(row):
                table.append(row)
            continue
        flush_table()
        raw = raw.replace(BR_MARK, ' ')
        indent = len(raw) - len(raw.lstrip(' \t'))
        text = clean_inline(raw)
        if not text:
            continue
        is_heading = (indent >= 8 and len(text) < 110 and '$' not in text and not text.startswith(('Пример', 'Решение', 'Ответ'))
                      and text[0].isupper())
        if is_heading:
            if cur:
                paras.append((cur_title, cur))
            cur_title, cur = text.rstrip('.'), []
            continue
        cur.append(text)
    flush_table()
    if cur:
        paras.append((cur_title, cur))
    return paras
