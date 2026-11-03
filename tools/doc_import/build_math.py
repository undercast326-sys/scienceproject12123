"""Build backend/content/math.json from the chapter .doc files.

usage: python -I build_math.py <folder with .doc files> <out.json>
"""
import collections
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from convert import convert_folder  # noqa: E402
import structure as st  # noqa: E402

SUBJECT = {'name': 'Математика', 'icon': '🧮', 'description': 'Алгебра, начала анализа, геометрия и текстовые задачи.'}

# File prefix -> topic name. Each file is one chapter; its NN.NN subsections become paragraphs.
TOPICS = {
    '01.01': 'Арифметика, дроби и проценты',
    '01.03': 'Алгебраические выражения и формулы сокращённого умножения',
    '01.04': 'Степени и корни',
    '02.01': 'Уравнения и системы уравнений',
    '03.01': 'Иррациональные уравнения',
    '04.01': 'Показательная функция и уравнения',
    '05.01': 'Логарифмы и логарифмические уравнения',
    '06.01': 'Неравенства и системы неравенств',
    '07.01': 'Показательные и логарифмические неравенства',
    '08.01': 'Иррациональные неравенства',
    '09.01': 'Текстовые задачи',
    '10.01': 'Тригонометрические функции и формулы',
    '11.01': 'Обратные тригонометрические функции и уравнения',
    '12.01': 'Тригонометрические неравенства',
    '13.01': 'Последовательности и прогрессии',
    '14.01': 'Функции и их свойства',
    '15.01': 'Производная и её применение',
    '16.01': 'Первообразная и интеграл',
    '17.01': 'Планиметрия',
    '18.01': 'Стереометрия',
    '19.01': 'Векторы и метод координат',
}
# Files that are not maths material and are left out on purpose.
SKIP_FILES = ('Действия с радикалами). Освобождение Формула',)


def first_sentences(title, limit=150):
    title = re.sub(r'\s+', ' ', title).strip().rstrip('.')
    if len(title) <= limit:
        return title, ''
    parts = re.split(r'(?<=\.)\s+', title)
    head = ''
    for p in parts:
        if len(head) + len(p) + 1 > limit and head:
            break
        head = (head + ' ' + p).strip()
    if len(head) > limit:
        head = head[:limit].rsplit(' ', 1)[0] + '…'
    rest = title[len(head):].strip(' .')
    return head.rstrip('.'), rest


def clean_theory_line(text):
    text = text.replace('⟦PIC⟧', '').replace('⟦?⟧', '…')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_theory_item(item):
    if item.startswith('[table]\n'):
        rows = []
        for row in item.split('\n')[1:]:
            cells = [clean_theory_line(c) for c in row.split('\t')]
            cells = [c if c.count('$') % 2 == 0 else c.replace('$', '') for c in cells]
            rows.append('\t'.join(cells))
        return '[table]\n' + '\n'.join(rows)
    text = clean_theory_line(item)
    return text if text.count('$') % 2 == 0 else ''


def build_task(t):
    opts = dict(t['opts'])
    answer = t['answer']
    if answer not in opts:
        return None, 'answer-not-in-options'
    # drop empty options unless it's the key
    for k in [k for k, v in opts.items() if not v and k != answer]:
        del opts[k]
    order = [k for k in t['order'] if k in opts]
    values = [opts[k] for k in order]
    text = t['prompt'] + ''.join(values)
    if '⟦' in text:
        return None, 'missing-formula-or-picture'
    if not t['prompt'].strip():
        return None, 'empty-prompt'
    if any(not v for v in values):
        return None, 'empty-option'
    if len(set(values)) != len(values):
        return None, 'duplicate-options'
    if len(values) < 2:
        return None, 'too-few-options'
    if any(s.count('$') % 2 for s in [t['prompt'], *values]):
        return None, 'unbalanced-math'
    return {'type': 'single', 'prompt': t['prompt'].strip(), 'options': values, 'correct_answer': opts[answer]}, None


def main(src, out):
    docs = convert_folder(src)
    skipped = collections.Counter()
    topics = []
    for path in sorted(docs):
        name = unicodedata.normalize('NFC', os.path.basename(path)[:-4])
        if any(skip in name for skip in SKIP_FILES):
            continue
        key = name[:5]
        tokens, eqs = docs[path]
        text = st.render(tokens, eqs)
        subs = st.find_subsections(text, int(key[:2]))
        paragraphs, tasks, sub_titles = [], [], []
        for sub in subs:
            theory, raw_tasks, problems = st.parse_subsection(sub)
            for kind, _ in problems:
                skipped[kind] += 1
            short, rest = first_sentences(sub['title'])
            sub_titles.append(short)
            lines = []
            if rest:
                lines.append(rest + '.')
            for head, body in st.theory_paragraphs(short, theory):
                body = [clean_theory_item(b) for b in body]
                body = [b for b in body if b]
                if not body:
                    continue
                if head != short:
                    lines.append('### ' + clean_theory_line(head))
                lines.extend(body)
            if lines:
                paragraphs.append({'title': f"{sub['code']} {short}", 'content': '\n\n'.join(lines)})
            for t in raw_tasks:
                task, why = build_task(t)
                if task:
                    tasks.append(task)
                else:
                    skipped[why] += 1
        topics.append({
            'code': key,
            'name': TOPICS[key],
            'description': ' · '.join(sub_titles)[:600],
            'paragraphs': paragraphs,
            'tasks': tasks,
        })
    data = {'subject': SUBJECT, 'topics': topics}
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print('topics', len(topics), 'paragraphs', sum(len(t['paragraphs']) for t in topics),
          'tasks', sum(len(t['tasks']) for t in topics))
    print('skipped', dict(skipped))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
