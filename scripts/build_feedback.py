#!/usr/bin/env python3
"""Build the training-feedback results from District_Training_Feedback_Report.docx.

Nine Likert statements, rated 1 (strongly disagree) to 5 (strongly agree), one
block per district. Every figure is transcribed as printed. Rows whose response
shares do not sum to ~100% are flagged rather than corrected: the discrepancy is
in the source, and silently rescaling it would misstate what officers reported.
"""
import json, re, sys, zipfile

SRC = sys.argv[1] if len(sys.argv) > 1 else '/Users/thesinghaa/Downloads/District_Training_Feedback_Report.docx'
OUT = 'landing/assets/feedback_results.json'

# the report's own short names for each statement, taken from its key findings
SHORT = ['Objectives clearly explained', 'Content relevant to district role',
         'Understanding of GVA/GDDP importance', 'Trainer explained concepts clearly',
         'Examples and case studies useful', 'Identified sector-specific GVA opportunities',
         'Encouraged participation and discussion', 'Duration and pace appropriate',
         'Overall usefulness']

# report heading -> the slug used across the site ("Kakianda" is a typo in the source)
SLUG = {'visakhapatnam':'visakhapatnam', 'kakianda':'kakinada', 'kakinada':'kakinada',
        'krishna':'krishna', 'srikakulam':'srikakulam', 'ntr':'ntr', 'ysr kadapa':'ysr-kadapa',
        'kurnool':'kurnool', 'parvathipuram manyam':'parvathipuram-manyam', 'chittoor':'chittoor'}
NAME = {'kakinada':'Kakinada', 'ysr-kadapa':'YSR Kadapa', 'ntr':'NTR',
        'parvathipuram-manyam':'Parvathipuram Manyam'}

x = zipfile.ZipFile(SRC).read('word/document.xml').decode()
x = re.sub(r'</w:p>', '\n', x)
x = re.sub(r'</w:tc>', ' | ', x)
x = re.sub(r'</w:tr>', '\n', x)
text = re.sub(r'<[^>]+>', '', x)
# a table row arrives as one line per cell, each opening with "|"; rejoin them
text = re.sub(r'\n\s*\|', ' |', text)
lines = [l.strip() for l in text.split('\n')]

def num(s):
    m = re.search(r'-?\d+(?:\.\d+)?', s or '')
    return float(m.group(0)) if m else None

districts, cur = {}, None
for i, ln in enumerate(lines):
    m = re.match(r'^(.+?)\s+District$', ln, re.I)
    if m and 'Q' not in ln[:2]:
        key = m.group(1).strip().lower()
        slug = SLUG.get(key)
        if not slug:
            print('!! unmapped district heading:', ln); continue
        cur = {'name': NAME.get(slug, m.group(1).strip().title()), 'questions': []}
        districts[slug] = cur
        continue
    if cur is None:
        continue
    if re.match(r'^\d+(\.\d+)?\s*/\s*5$', ln):
        cur['avg'] = num(ln)
    if ln.startswith('Mean of participant-level averages'):
        cur['n'] = int(num(ln.split('|')[1]))
    if ln.startswith('Complete responses included'):
        cur['favorable'] = num(ln.split('|')[1])
    if ln.startswith('Key finding'):
        b = re.search(r'strongest-rated area was\s*[“"]([^”"]+)[”"]\s*\(([\d.]+)/5\)', ln)
        w = re.search(r'lowest-rated area was\s*[“"]([^”"]+)[”"]\s*\(([\d.]+)/5\)', ln)
        if b: cur['best'] = {'label': b.group(1), 'avg': float(b.group(2))}
        if w: cur['worst'] = {'label': w.group(1), 'avg': float(w.group(2))}
    m = re.match(r'^Q(\d)\.\s*(.+)$', ln)
    if m:
        cells = [c.strip() for c in ln.split('|')]
        vals = [num(c) for c in cells[1:7]]
        if len([v for v in vals if v is not None]) < 6:
            print('!! short row', cur['name'], ln[:60]); continue
        n = int(m.group(1))
        cur['questions'].append({
            'n': n,
            'short': SHORT[n-1],
            'text': re.sub(r'\s*\|.*$', '', m.group(2)).strip(),
            'avg': vals[0],
            'dist': vals[1:],           # strongly agree → strongly disagree
        })

# integrity: flag rows whose shares do not sum to ~100
for slug, d in districts.items():
    assert len(d['questions']) == 9, (slug, len(d['questions']))
    for q in d['questions']:
        s = round(sum(q['dist']), 1)
        if abs(s - 100) > 0.6:
            q['sum_flag'] = s
            print('   note: %s Q%d shares sum to %.1f%%' % (d['name'], q['n'], s))

res = {
 '_source': 'District_Training_Feedback_Report.docx (PIF). Nine Likert statements, 1 to 5. '
            'Figures transcribed as printed; nothing recomputed. Where a row\'s response shares '
            'do not sum to 100%, sum_flag carries the printed total rather than a corrected one.',
 '_scale': ['Strongly agree', 'Agree', 'Neutral', 'Disagree', 'Strongly disagree'],
 '_statements': SHORT,
 'districts': districts,
}
json.dump(res, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('\nwrote %s: %d districts' % (OUT, len(districts)))
for s, d in sorted(districts.items(), key=lambda kv: -kv[1]['avg']):
    print('  %-22s %.2f/5  n=%-3d fav=%.1f%%' % (d['name'], d['avg'], d['n'], d['favorable']))
