"""Extract the objective (MCQ) questions from the six assessment papers.

The reports name only the best- and least-answered topics per round, so the
paper is shown as the paper: every question with its options, in order. No
answer key is asserted and no per-question accuracy is invented.
"""
import re, json, os

SRC = 'corpus_files/training/'

def clean(t):
    t = t.replace('\\~', '~').replace('\\*', '*').strip()
    return re.sub(r'\s+', ' ', t)

def parse(path, sections):
    """sections: list of (regex marking section start, section label) in order.
    Returns [{section, n, text, options[]}] over the whole file."""
    lines = open(SRC + path).read().split('\n')
    # section boundaries
    bounds = []
    for i, ln in enumerate(lines):
        for pat, label in sections:
            if re.match(pat, ln.strip()):
                bounds.append((i, label))
    def label_for(i):
        cur = sections[0][1]
        for at, lab in bounds:
            if at <= i: cur = lab
        return cur

    out, cur = [], None
    for i, raw in enumerate(lines):
        ln = raw.strip()
        if not ln:
            continue
        if re.match(r'^Subjective Question', ln, re.I):
            cur = None
            continue
        # a question: "Q1. …", "1. …", or a bare "…?" line inside an objective block
        m = re.match(r'^(?:Q\s*)?(\d{1,2})[\.\)]\s*(.{12,})$', ln)
        if m and not re.match(r'^\|', ln):
            cur = {'section': label_for(i), 'text': clean(m.group(2)), 'options': []}
            out.append(cur)
            continue
        # options, plain lines: "A. …" / "○ a) …"
        m = re.match(r'^(?:○\s*)?([A-Da-d])[\.\)]\s+(.+)$', ln)
        if m and cur is not None:
            cur['options'].append(clean(m.group(2)))
            continue
        # options in a 2-cell markdown row: "| A. x | B. y |"
        if ln.startswith('|') and cur is not None:
            cells = [c.strip() for c in ln.strip('|').split('|')]
            got = False
            for c in cells:
                mm = re.match(r'^([A-D])[\.\)]\s+(.+)$', c)
                if mm:
                    cur['options'].append(clean(mm.group(2))); got = True
            if got: continue
        # an unnumbered question line inside an objective block
        if ln.endswith('?') and not ln.startswith('|') and len(ln) > 18 and not ln.startswith('○'):
            cur = {'section': label_for(i), 'text': clean(ln), 'options': []}
            out.append(cur)
    # keep only real MCQs, renumber
    out = [q for q in out if len(q['options']) >= 3]
    for i, q in enumerate(out): q['n'] = i + 1
    return out

PAPERS = {
 'district_baseline': ('Pre_Training_Assessment_District.txt', [
    (r'^Section A', 'AP & Swarna Andhra: general awareness'),
    (r'^Section B', 'KPI framework & monitoring'),
    (r'^Section C', 'Economic concepts')]),
 'district_endline': ('Post_Training_Assessment_District.txt', [
    (r'^Section A', 'GDP / GVA / GDDP'),
    (r'^Section B', 'Strategies for boosting district GVA')]),
 'constituency': ('Post_Training_Assessment_Constituency.txt', [
    (r'^Section A', 'Improving GVA at constituency and mandal level')]),
 'master': ('Post_Training_Assessment_Master_Trainer.txt', [
    (r'^Section A', 'Estimation of GDP / GSDP / GDDP'),
    (r'^Section B', 'Swarna Andhra 2047, KPIs and boosting GVA')]),
}

res = {'_source': 'corpus_files/training/*Assessment*.txt — the objective questions as administered. No answer key and no per-question accuracy are asserted here; the reports name only the best- and least-answered topics.', 'papers': {}}
for key, (path, secs) in PAPERS.items():
    qs = parse(path, secs)
    res['papers'][key] = qs
    print(key, len(qs), 'questions')
    for q in qs: print('   ', q['n'], q['section'][:28], '|', q['text'][:70], '|', len(q['options']))

json.dump(res, open('landing/assets/assessment_questions.json', 'w'), indent=1, ensure_ascii=False)
