#!/usr/bin/env python3
"""Build training-feedback results from the three level reports.

Source: ~/Downloads/andhra material/Training feedback/
  District_Training_Feedback_Report.docx      -> district level      (9 districts)
  District_Constituency Training Feedback.docx-> constituency level (13 districts)
  Master Training_Feedback_Analysis.docx      -> master level        (9 districts)

Same nine-statement instrument at every level, rated 1 (strongly disagree) to
5 (strongly agree); the master report prints the statements in a condensed
wording but in the same order, so they carry the same question numbers.

WHICH DOC IS WHICH LEVEL. Only the master file names its level in its own text.
The other two both head their pages "DISTRICT TRAINING FEEDBACK REPORT" — the
constituency file appears to reuse the district template's header, and its Q2
still reads "as a district official". The filename is not evidence enough on its
own, so the assignment is corroborated against the response counts already held
in assessment_results.json, which are per level and independent of these files:

    Kurnool   district   n=5    vs assessment district endline      n=5
    Kurnool   constituency n=201 vs assessment constituency endline n=193 (203 base)
    Kurnool   master     n=51   vs assessment master endline        n=51

Two exact matches and one within the baseline/endline range. Nothing here is
recomputed: every figure is transcribed as printed, and where a row's response
shares do not sum to 100% the printed total is kept and flagged rather than
rescaled.

Usage:  python3 scripts/build_feedback.py
"""
import json, os, re, sys, zipfile

SRC = os.path.expanduser("~/Downloads/andhra material/Training feedback")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "landing", "assets", "feedback_results.json")

# the report's own short names for each statement, in question order
SHORT = ['Objectives clearly explained', 'Content relevant to district role',
         'Understanding of GVA/GDDP importance', 'Trainer explained concepts clearly',
         'Examples and case studies useful', 'Identified sector-specific GVA opportunities',
         'Encouraged participation and discussion', 'Duration and pace appropriate',
         'Overall usefulness']

SLUG = {
 'srikakulam':'srikakulam', 'vizianagaram':'vizianagaram',
 'parvathipuram manyam':'parvathipuram-manyam', 'parvatipuram manyam':'parvathipuram-manyam',
 'visakhapatnam':'visakhapatnam', 'vishakapatnam':'visakhapatnam',
 'kakinada':'kakinada', 'kakianda':'kakinada',
 'dr.b.r. ambedkar konaseema':'dr-b-r-ambedkar-konaseema',
 'dr br ambedkar konaseema':'dr-b-r-ambedkar-konaseema',
 'dr. b.r. ambedkar konaseema':'dr-b-r-ambedkar-konaseema',
 'east godavari':'east-godavari', 'eluru':'eluru', 'krishna':'krishna', 'ntr':'ntr',
 'guntur':'guntur', 'prakasam':'prakasam', 'spsr nellore':'spsr-nellore', 'nellore':'spsr-nellore',
 'kurnool':'kurnool', 'nandyal':'nandyal', 'ysr kadapa':'ysr-kadapa',
 'chittoor':'chittoor', 'tirupati':'tirupati'}
NAME = {'kakinada':'Kakinada','ysr-kadapa':'YSR Kadapa','ntr':'NTR','spsr-nellore':'SPSR Nellore',
        'parvathipuram-manyam':'Parvathipuram Manyam','dr-b-r-ambedkar-konaseema':'Dr. B.R. Ambedkar Konaseema',
        'east-godavari':'East Godavari','visakhapatnam':'Visakhapatnam'}

LEVELS = [
 ("district",     "District_Training_Feedback_Report.docx",       "District training"),
 ("constituency", "District_Constituency Training Feedback.docx", "Constituency training"),
 ("master",       "Master Training_Feedback_Analysis.docx",       "Master trainer programme"),
]


def doc_text(path):
    x = zipfile.ZipFile(path).read('word/document.xml').decode()
    x = re.sub(r'</w:p>', '\n', x)
    x = re.sub(r'</w:tc>', ' | ', x)
    x = re.sub(r'</w:tr>', '\n', x)
    t = re.sub(r'<[^>]+>', '', x)
    # a table row arrives as one line per cell, each opening with "|"; rejoin
    return re.sub(r'\n\s*\|', ' |', t)


def num(s):
    m = re.search(r'-?\d+(?:\.\d+)?', s or '')
    return float(m.group(0)) if m else None


def parse_questions(block):
    """[{n, short, text, avg, dist}] for the nine rows of one block."""
    out = []
    for line in block.split('\n'):
        m = re.match(r'\s*Q(\d)\b[.:]?\s*(.*)$', line)
        if not m:
            continue
        cells = [c.strip() for c in line.split('|')]
        vals = [num(c) for c in cells[1:]]
        vals = [v for v in vals if v is not None]
        if len(vals) < 6:
            continue
        n = int(m.group(1))
        # the master file puts the statement in its own cell, so the first
        # numeric cell is the average in every layout
        avg, dist = vals[0], vals[1:6]
        text = re.sub(r'\s*\|.*$', '', m.group(2)).strip()
        if not text and len(cells) > 1:
            text = cells[1].strip()
        out.append({'n': n, 'short': SHORT[n - 1], 'text': text,
                    'avg': avg, 'dist': dist})
    return sorted(out, key=lambda q: q['n'])[:9]


def parse_summary(block, level):
    """(n, avg, favourable) — the block's headline figures, as printed."""
    n = avg = fav = None
    for line in block.split('\n'):
        L = line.strip()
        if level == 'district':
            if L.startswith('Mean of participant-level averages'):
                n = num(L.split('|')[1]) if '|' in L else None
            elif L.startswith('Complete responses included'):
                fav = num(L.split('|')[1]) if '|' in L else None
            elif re.match(r'^\d+(\.\d+)?\s*/\s*5$', L):
                avg = num(L)
        elif level == 'constituency':
            if L.startswith('Participants') and '|' in L:
                # header row; the values are on the line beneath it
                continue
            m = re.match(r'^(\d{1,4})\s*\|\s*([\d.]+)\s*/\s*5', L)
            if m:
                n, avg = int(m.group(1)), float(m.group(2))
                fm = re.search(r'([\d.]+)\s*%', L)
                if fm:
                    fav = float(fm.group(1))
    if level == 'master':
        # This layout prints each figure BEFORE the label it belongs to, and the
        # cell join then puts them on the same line as the NEXT label:
        #     27
        #     Responses | 39.2
        #     Average total score (out of 45) | 4.36
        #     Average rating (out of 5) | 96.7%
        #     Favorable responses |
        # so reading "label | value" pairs off one line attaches every figure to
        # the wrong label. Walk the tokens instead and take the value that comes
        # immediately before each label.
        head = block.split('Key reading')[0]
        toks = [t.strip() for t in re.split(r'[|\n]', head) if t.strip()]
        want = {'responses': 'n', 'average rating': 'avg', 'favorable responses': 'fav'}
        got = {}
        for i, t in enumerate(toks):
            key = next((v for k, v in want.items() if t.lower().startswith(k)), None)
            if key and i > 0:
                got[key] = num(toks[i - 1])
        n = int(got['n']) if got.get('n') is not None else None
        avg, fav = got.get('avg'), got.get('fav')
    return n, avg, fav


def parse_key(block):
    """The report's own highest/lowest question numbers, or (None, None)."""
    hi = re.search(r'[Hh]ighest[- ]rated(?:\s+item)?(?:\s+is)?:?\s*Q(\d)', block)
    lo = re.search(r'[Ll]owest[- ]rated(?:\s+item)?(?:\s+is)?:?\s*Q(\d)', block)
    return (int(hi.group(1)) if hi else None, int(lo.group(1)) if lo else None)


def blocks_for(level, text):
    if level == 'district':
        return [b for b in re.split(r'(?=\n[A-Z][A-Za-z .]+ District\s*\n)', text) if 'Q1' in b]
    if level == 'constituency':
        return [b for b in re.split(r'(?=DISTRICT TRAINING FEEDBACK REPORT)', text) if 'Q1' in b]
    return [b for b in re.split(r'(?=TRAINING FEEDBACK ANALYSIS)', text) if 'Q1' in b]


def district_of(level, block):
    for line in block.split('\n'):
        L = line.strip(' |')
        if not L:
            continue
        if level == 'district':
            m = re.match(r'^([A-Za-z .]+?)\s+District$', L)
            if m:
                return m.group(1).strip()
        elif level == 'constituency':
            if re.match(r'^DISTRICT TRAINING FEEDBACK REPORT', L) or re.match(r'^\d{2}\s*/\s*\d{2}$', L):
                continue
            if re.match(r'^[A-Za-z][A-Za-z .]{2,40}$', L):
                return L
        else:
            if re.match(r'^TRAINING FEEDBACK ANALYSIS', L):
                continue
            if re.match(r'^[A-Za-z][A-Za-z .]{2,40}$', L):
                return L
    return None


def main():
    districts, notes = {}, []
    for level, fname, label in LEVELS:
        path = os.path.join(SRC, fname)
        if not os.path.exists(path):
            print('  ! missing:', path, file=sys.stderr); continue
        text = doc_text(path)
        seen = 0
        for block in blocks_for(level, text):
            raw = district_of(level, block)
            slug = SLUG.get((raw or '').strip().lower().rstrip('.'))
            if not slug:
                print('  ! unmapped district %r in %s' % (raw, fname), file=sys.stderr)
                continue
            qs = parse_questions(block)
            if len(qs) != 9:
                print('  ! %s/%s: %d questions parsed' % (slug, level, len(qs)), file=sys.stderr)
                continue
            n, avg, fav = parse_summary(block, level)
            hi, lo = parse_key(block)
            for q in qs:
                s = round(sum(q['dist']), 1)
                if abs(s - 100) > 0.6:
                    q['sum_flag'] = s
                    notes.append('%s %s Q%d shares sum to %.1f%%' % (slug, level, q['n'], s))
            rec = districts.setdefault(slug, {'name': NAME.get(slug, (raw or '').title()), 'levels': {}})
            rec['levels'][level] = {'label': label, 'n': n, 'avg': avg, 'favorable': fav,
                                    'best_q': hi, 'worst_q': lo, 'questions': qs}
            seen += 1
        print('%-14s %2d districts' % (level, seen))

    out = {
     '_source': 'Training feedback reports (PIF): District_Training_Feedback_Report.docx, '
                'District_Constituency Training Feedback.docx, Master Training_Feedback_Analysis.docx. '
                'Nine statements rated 1 to 5. Figures transcribed as printed; nothing recomputed. '
                'The constituency file heads its pages "DISTRICT TRAINING FEEDBACK REPORT" and its Q2 '
                'still reads "as a district official"; it is treated as constituency-level because its '
                'response counts match the constituency round in assessment_results.json, not the '
                'district round. Where a row\'s shares do not sum to 100%, sum_flag carries the printed total.',
     '_scale': ['Strongly agree', 'Agree', 'Neutral', 'Disagree', 'Strongly disagree'],
     '_statements': SHORT,
     '_levels': [{'key': k, 'label': lbl} for k, _, lbl in LEVELS],
     'districts': districts,
    }
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('\nwrote %s: %d districts' % (OUT, len(districts)))
    for note in notes:
        print('   note:', note)
    print()
    print('%-28s %-22s %-22s %s' % ('district', 'district', 'constituency', 'master'))
    for slug in sorted(districts):
        r = districts[slug]['levels']
        cell = lambda k: ('%.2f/5 n=%s' % (r[k]['avg'], r[k]['n'])) if k in r else '—'
        print('%-28s %-22s %-22s %s' % (slug, cell('district'), cell('constituency'), cell('master')))


if __name__ == '__main__':
    main()
