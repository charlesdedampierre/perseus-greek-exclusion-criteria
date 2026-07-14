"""Build the single-file HTML annotation app at `annotation/index.html`.

Pulls the Archaic + Classical Greek slice from
`data/clean/final/rules_with_criteria.tsv`, computes (a) every distinct
`group` label with its LLM-inferred criterion vector, and (b) every
distinct raw `resource_meta` with its LLM-inferred orthogonal-resource
bucket. The data is inlined as JSON into a single static HTML page that
runs locally (no server, no fetches) — the user opens it in a browser,
clicks dropdowns to set the manual mappings, and clicks "Download TSV"
to export the annotated tables.

Run with:
    python scripts/build_annotation_app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RULES_SRC = ROOT / "data/clean/final/rules_with_criteria.tsv"
OUT_HTML  = ROOT / "annotation/index.html"

AXES = ['c_sex','c_age','c_ownership_status','c_ancestry','c_residence','c_wealth']
AXIS_VALS = {
    'c_sex':              ['Male', 'Female', '*'],
    'c_age':              ['Adult', 'Minor', '*'],
    'c_ownership_status': ['Free', 'Enslaved', '*'],
    'c_ancestry':         ['Native', 'Foreign', '*'],
    'c_residence':        ['Resident', 'Non resident', '*'],
    'c_wealth':           ['High', 'Low', '*'],
}
RESOURCES = [
    'Eligibility for public office',
    'Political power',
    'Right to a legal trial',
    'Right to vote in the Ekklesia',
    'Right to dispose / inherit property',
    'Right to retain property',
    'Right to public speech',
    'Right to marriage / dowry',
    'Protection from capital / corporal punishment',
]
RESOURCE_BUCKET = {
    'Right to own land':                              'Right to retain property',
    'Right to retain own earnings':                   'Right to retain property',
    'Right to own property':                          'Right to retain property',
    'Right to retain property':                       'Right to retain property',
    'Right to dispose of property':                   'Right to dispose / inherit property',
    'Right to inherit property':                      'Right to dispose / inherit property',
    'Right to dispose / inherit property':            'Right to dispose / inherit property',
    'Right to address the assembly':                  'Right to public speech',
    'Right to speak first in assembly':               'Right to public speech',
    'Right to free speech':                           'Right to public speech',
    'Right to public speech':                         'Right to public speech',
    'Right to remuneration for office':               'Eligibility for public office',
    'Eligibility for public office':                  'Eligibility for public office',
    'Right to a dowry':                               'Right to marriage / dowry',
    'Right to marry':                                 'Right to marriage / dowry',
    'Right to marriage / dowry':                      'Right to marriage / dowry',
    'Right to professional judgement':                'Right to a legal trial',
    'Right to valid professional opinion':            'Right to a legal trial',
    'Right to a legal trial':                         'Right to a legal trial',
    'Protection from capital punishment':             'Protection from capital / corporal punishment',
    'Protection from corporal punishment':            'Protection from capital / corporal punishment',
    'Protection from capital / corporal punishment':  'Protection from capital / corporal punishment',
    'Right to vote in the Ekklesia':                  'Right to vote in the Ekklesia',
    'Political power':                                'Political power',
}


def _t(v):
    if pd.isna(v): return '*'
    s = str(v)
    if s in ('any', 'unspecified'): return '*'
    return s.replace('_', ' ').capitalize()


def build_dataset():
    df = pd.read_csv(RULES_SRC, sep='\t')
    polities = sorted({p for p in df['rule_polity'].dropna().unique()
                       if 'Archaic' in p or 'Classical' in p})
    df = df[df['rule_polity'].isin(polities)]
    df = df[(df['requires_rights_definition'] != True) & (df['tautology'] != 1)]
    df = df[df['directionality'].isin(['MORE','LESS'])]
    df = df.copy()
    df['bucket_llm'] = df['resource_meta'].map(RESOURCE_BUCKET)

    # --- Groups ---
    def axis_value(series):
        s = series.dropna().map(_t)
        if not len(s): return '*'
        return s.mode().iloc[0]

    def _first_verbatim(s):
        v = s
        if pd.isna(v): return ''
        if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
            try:
                arr = json.loads(v)
                if isinstance(arr, list) and arr: v = arr[0]
            except Exception:
                pass
        return str(v).replace('\t', ' ').replace('\n', ' ').strip()[:220]

    g_rows = []
    for grp, sub in df.groupby('group'):
        more = (sub['directionality'] == 'MORE').sum()
        less = (sub['directionality'] == 'LESS').sum()
        polities_set = sorted(set(sub['rule_polity'].dropna()))
        example_rule = ''
        example_verb = ''
        for _, r in sub.iterrows():
            if isinstance(r.get('rule'), str) and r['rule'].strip() and not example_rule:
                example_rule = r['rule'][:160]
            if not example_verb:
                example_verb = _first_verbatim(r.get('verbatim'))
            if example_rule and example_verb:
                break
        row = {
            'group': grp,
            'n_rules': int(len(sub)),
            'n_more': int(more),
            'n_less': int(less),
            'polities': '; '.join(polities_set[:4]),
            'example': example_rule,
            'verbatim': example_verb,
        }
        for ax in AXES:
            row[f'llm_{ax}'] = axis_value(sub[ax])
        g_rows.append(row)
    g_rows.sort(key=lambda r: -r['n_rules'])

    # --- Resources: use the raw `resource` field (much richer than the 42 buckets) ---
    r_rows = []
    for rname, sub in df.groupby('resource'):
        more = (sub['directionality'] == 'MORE').sum()
        less = (sub['directionality'] == 'LESS').sum()
        # LLM bucket = the most-frequent meta-bucket among rules carrying this raw resource
        bucket_counts = sub['bucket_llm'].dropna().value_counts()
        bucket = bucket_counts.index[0] if len(bucket_counts) else ''
        # Also record the raw resource_meta (the corpus's first-level grouping)
        rm_counts = sub['resource_meta'].dropna().value_counts()
        resource_meta = rm_counts.index[0] if len(rm_counts) else ''
        example_rule = ''
        example_verb = ''
        for _, r in sub.iterrows():
            if isinstance(r.get('rule'), str) and r['rule'].strip() and not example_rule:
                example_rule = r['rule'][:160]
            if not example_verb:
                example_verb = _first_verbatim(r.get('verbatim'))
            if example_rule and example_verb:
                break
        r_rows.append({
            'resource': rname,
            'resource_meta': resource_meta,
            'n_rules': int(len(sub)),
            'n_more': int(more),
            'n_less': int(less),
            'llm_bucket': bucket,
            'example': example_rule,
            'verbatim': example_verb,
        })
    r_rows.sort(key=lambda r: -r['n_rules'])

    return g_rows, r_rows, len(df)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Greek Rights Corpus — Annotation</title>
<style>
  :root {
    --bg: #fafaf7;
    --panel: #ffffff;
    --border: #d8d3c8;
    --ink: #1d2126;
    --ink-soft: #5b6470;
    --accent: #1a4280;
    --warn: #b15623;
    --ok: #2c7a4b;
    --row-alt: #f4f1e9;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--ink);
    font-size: 14px;
  }
  header {
    background: linear-gradient(180deg, #ffffff 0%, #f6f3eb 100%);
    border-bottom: 2px solid var(--border);
    padding: 22px 32px 18px;
    display: flex; align-items: flex-end; justify-content: space-between;
    flex-wrap: wrap; gap: 16px;
  }
  header .title-block { display: flex; flex-direction: column; gap: 4px; }
  header .eyebrow {
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--accent); font-weight: 700;
  }
  h1 { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.01em; }
  .meta { color: var(--ink-soft); font-size: 12.5px; margin-top: 6px; }
  .meta strong { color: var(--ink); font-weight: 600; }
  .meta .dot { color: var(--border); margin: 0 8px; }
  nav { display: flex; gap: 4px; }
  nav button {
    background: transparent;
    border: 1px solid var(--border);
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: var(--ink);
  }
  nav button.active {
    background: var(--accent); color: white; border-color: var(--accent);
  }
  .toolbar {
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    padding: 10px 24px;
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    position: sticky; top: 0;
    z-index: 9;
  }
  .toolbar + .toolbar { top: 51px; }
  .toolbar input[type="text"] {
    border: 1px solid var(--border);
    padding: 6px 10px;
    border-radius: 4px;
    min-width: 240px;
  }
  .toolbar button {
    background: var(--accent); color: white;
    border: none; padding: 7px 16px;
    border-radius: 4px; cursor: pointer; font-weight: 500;
  }
  .toolbar button.secondary {
    background: var(--panel); color: var(--ink); border: 1px solid var(--border);
  }
  .toolbar .count { color: var(--ink-soft); margin-left: auto; }
  main { padding: 16px 24px; }
  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border: 1px solid var(--border);
    font-size: 13px;
    /* NB: no overflow:hidden here — that would break position:sticky on thead */
  }
  thead th {
    background: #ede7d8;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 2px solid var(--border);
    font-weight: 600;
    color: var(--ink);
    position: sticky; top: 51px;
    z-index: 5;
  }
  body.resources-mode thead th { top: 102px; }
  tbody tr:nth-child(even) { background: var(--row-alt); }
  tbody td {
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  td.label { font-weight: 600; min-width: 160px; }
  td.example { color: var(--ink-soft); max-width: 380px; font-size: 12px; line-height: 1.4; }
  td.example .rule { font-style: italic; color: #4d5560; }
  td.example .verbatim { display: block; margin-top: 4px; color: #5b6470; font-family: Georgia, serif; font-size: 11.5px; border-left: 2px solid var(--border); padding-left: 6px; }
  td.polities { color: var(--ink-soft); font-size: 12px; max-width: 200px; }
  td.numeric { font-variant-numeric: tabular-nums; text-align: right; width: 60px; }
  td.row-index {
    color: var(--ink-soft); font-variant-numeric: tabular-nums;
    text-align: right; width: 44px; font-size: 11px; padding-right: 6px;
  }
  td.llm { color: var(--ink-soft); font-size: 12px; }
  td.meta { color: var(--ink-soft); font-size: 11px; }
  select {
    border: 1px solid var(--border);
    background: var(--panel);
    padding: 4px 6px;
    border-radius: 3px;
    font-size: 12px;
    min-width: 96px;
  }
  select.modified { background: #fff7e6; border-color: var(--warn); }
  select.dropped { background: #fbe9e7; border-color: var(--warn); color: var(--warn); }
  .hidden { display: none !important; }
  .footer {
    text-align: center;
    padding: 16px;
    color: var(--ink-soft);
    font-size: 12px;
  }
  .badge {
    display: inline-block;
    background: #e8f5e9;
    color: var(--ok);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
  }
</style>
</head>
<body>
<header>
  <div class="title-block">
    <span class="eyebrow">Manual annotation</span>
    <h1>Greek Rights Corpus</h1>
    <div class="meta">
      <strong>Archaic + Classical Greek</strong> slice
      <span class="dot">·</span> <strong>__N_RULES__</strong> rules
      <span class="dot">·</span> <strong>__N_GROUPS__</strong> distinct groups
      <span class="dot">·</span> <strong>__N_RESOURCES__</strong> distinct raw resources
    </div>
  </div>
  <nav>
    <button id="tab-groups" class="active">Groups (__N_GROUPS__)</button>
    <button id="tab-resources">Resources (__N_RESOURCES__)</button>
  </nav>
</header>

<div class="toolbar">
  <input type="text" id="search" placeholder="Filter rows…">
  <button id="download" data-mode="groups">Download manual_groups.tsv</button>
  <button id="reset" class="secondary">Reset to LLM defaults</button>
  <span class="count" id="count"></span>
</div>

<div class="toolbar" id="resource-extra-toolbar" style="display:none; border-top:none;">
  <input type="text" id="new-bucket" placeholder="Add a new resource bucket name…">
  <button id="add-bucket" class="secondary">+ Add bucket</button>
  <span class="meta" style="color:var(--ink-soft); font-size:12px;">
    New buckets become selectable in every row's dropdown and persist in your browser.
  </span>
</div>

<main>
  <section id="groups-panel">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>group</th>
          <th>n</th>
          <th>+</th>
          <th>−</th>
          <th>sex</th>
          <th>age</th>
          <th>ownership</th>
          <th>ancestry</th>
          <th>residence</th>
          <th>wealth</th>
          <th>action</th>
          <th>example rule</th>
        </tr>
      </thead>
      <tbody id="groups-tbody"></tbody>
    </table>
  </section>

  <section id="resources-panel" class="hidden">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>resource (raw)</th>
          <th>resource_meta</th>
          <th>n</th>
          <th>+</th>
          <th>−</th>
          <th>LLM bucket</th>
          <th>manual bucket</th>
          <th>example rule</th>
        </tr>
      </thead>
      <tbody id="resources-tbody"></tbody>
    </table>
  </section>
</main>

<div class="footer">
  Edits are saved to your browser's localStorage as you make them. Click "Download" to export a tab-separated file.
</div>

<script>
const AXES = __AXES_JSON__;
const AXIS_VALS = __AXIS_VALS_JSON__;
const RESOURCES = __RESOURCES_JSON__;
const GROUPS_DATA = __GROUPS_DATA_JSON__;
const RESOURCES_DATA = __RESOURCES_DATA_JSON__;

const LS_GROUPS_KEY    = 'annot.groups.v1';
const LS_RESOURCES_KEY = 'annot.resources.v1';
const LS_BUCKETS_KEY   = 'annot.custom_buckets.v1';

function loadCustomBuckets() {
  try { return JSON.parse(localStorage.getItem(LS_BUCKETS_KEY) || '[]'); }
  catch (e) { return []; }
}
function saveCustomBuckets(arr) { localStorage.setItem(LS_BUCKETS_KEY, JSON.stringify(arr)); }
let customBuckets = loadCustomBuckets();
function allBucketOptions() {
  return RESOURCES.concat(customBuckets).concat(['(drop)']);
}

function loadOverrides(key) {
  try { return JSON.parse(localStorage.getItem(key) || '{}'); }
  catch (e) { return {}; }
}
function saveOverrides(key, obj) { localStorage.setItem(key, JSON.stringify(obj)); }

let groupOverrides    = loadOverrides(LS_GROUPS_KEY);
let resourceOverrides = loadOverrides(LS_RESOURCES_KEY);

function makeSelect(options, value, dataAttrs, modifiedClass) {
  const sel = document.createElement('select');
  options.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o; opt.textContent = o;
    if (o === value) opt.selected = true;
    sel.appendChild(opt);
  });
  Object.entries(dataAttrs).forEach(([k, v]) => sel.dataset[k] = v);
  if (modifiedClass) sel.classList.add(modifiedClass);
  return sel;
}

function makeCell(content, cls) {
  const td = document.createElement('td');
  if (cls) td.className = cls;
  if (content instanceof Node) td.appendChild(content);
  else td.textContent = content == null ? '' : content;
  return td;
}

function makeExampleCell(rule, verbatim) {
  const td = document.createElement('td');
  td.className = 'example';
  if (rule) {
    const r = document.createElement('div');
    r.className = 'rule';
    r.textContent = rule;
    td.appendChild(r);
  }
  if (verbatim) {
    const v = document.createElement('span');
    v.className = 'verbatim';
    v.textContent = '“' + verbatim + '”';
    td.appendChild(v);
  }
  return td;
}

function renderGroups() {
  const tbody = document.getElementById('groups-tbody');
  tbody.innerHTML = '';
  GROUPS_DATA.forEach((row, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.searchText = (row.group + ' ' + (row.example || '') + ' ' + (row.verbatim || '')).toLowerCase();
    const ovr = groupOverrides[row.group] || {};

    tr.appendChild(makeCell(idx + 1, 'row-index'));
    tr.appendChild(makeCell(row.group, 'label'));
    tr.appendChild(makeCell(row.n_rules, 'numeric'));
    tr.appendChild(makeCell(row.n_more, 'numeric'));
    tr.appendChild(makeCell(row.n_less, 'numeric'));

    AXES.forEach(ax => {
      const llm = row['llm_' + ax];
      const manual = ovr[ax] != null ? ovr[ax] : llm;
      const modified = manual !== llm;
      const sel = makeSelect(
        AXIS_VALS[ax],
        manual,
        { group: row.group, axis: ax, llm: llm },
        modified ? 'modified' : null
      );
      sel.addEventListener('change', e => {
        const g = e.target.dataset.group;
        if (!groupOverrides[g]) groupOverrides[g] = {};
        groupOverrides[g][e.target.dataset.axis] = e.target.value;
        const llmVal = e.target.dataset.llm;
        e.target.classList.toggle('modified', e.target.value !== llmVal);
        saveOverrides(LS_GROUPS_KEY, groupOverrides);
        updateCount();
      });
      tr.appendChild(makeCell(sel));
    });

    const actVal = ovr['__action'] || 'keep';
    const actSel = makeSelect(['keep', 'DROP'], actVal,
      { group: row.group, axis: '__action', llm: 'keep' },
      actVal === 'DROP' ? 'dropped' : null);
    actSel.addEventListener('change', e => {
      const g = e.target.dataset.group;
      if (!groupOverrides[g]) groupOverrides[g] = {};
      groupOverrides[g]['__action'] = e.target.value;
      e.target.classList.toggle('dropped', e.target.value === 'DROP');
      saveOverrides(LS_GROUPS_KEY, groupOverrides);
      updateCount();
    });
    tr.appendChild(makeCell(actSel));

    tr.appendChild(makeExampleCell(row.example, row.verbatim));
    tbody.appendChild(tr);
  });
  updateCount();
}

function renderResources() {
  const tbody = document.getElementById('resources-tbody');
  tbody.innerHTML = '';
  const options = allBucketOptions();
  RESOURCES_DATA.forEach((row, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.searchText = (row.resource + ' ' + (row.resource_meta || '') + ' ' + (row.example || '') + ' ' + (row.verbatim || '')).toLowerCase();
    const ovr = resourceOverrides[row.resource];
    const llm = row.llm_bucket || '(drop)';
    const manual = ovr != null ? ovr : llm;
    const modified = manual !== llm;

    tr.appendChild(makeCell(idx + 1, 'row-index'));
    tr.appendChild(makeCell(row.resource, 'label'));
    tr.appendChild(makeCell(row.resource_meta || '—', 'meta'));
    tr.appendChild(makeCell(row.n_rules, 'numeric'));
    tr.appendChild(makeCell(row.n_more, 'numeric'));
    tr.appendChild(makeCell(row.n_less, 'numeric'));
    tr.appendChild(makeCell(row.llm_bucket || '—', 'llm'));

    const sel = makeSelect(options, manual,
      { resource: row.resource, llm: llm },
      modified ? (manual === '(drop)' ? 'dropped' : 'modified') : null);
    sel.addEventListener('change', e => {
      resourceOverrides[e.target.dataset.resource] = e.target.value;
      const llmVal = e.target.dataset.llm;
      sel.classList.remove('modified', 'dropped');
      if (e.target.value !== llmVal) {
        sel.classList.add(e.target.value === '(drop)' ? 'dropped' : 'modified');
      }
      saveOverrides(LS_RESOURCES_KEY, resourceOverrides);
      updateCount();
    });
    tr.appendChild(makeCell(sel));
    tr.appendChild(makeExampleCell(row.example, row.verbatim));
    tbody.appendChild(tr);
  });
  updateCount();
}

function addCustomBucket() {
  const input = document.getElementById('new-bucket');
  const name = input.value.trim();
  if (!name) return;
  if (RESOURCES.includes(name) || customBuckets.includes(name)) {
    alert('Bucket "' + name + '" already exists.');
    return;
  }
  customBuckets.push(name);
  saveCustomBuckets(customBuckets);
  input.value = '';
  renderResources();
}

function showTab(name) {
  const isGroups = (name === 'groups');
  document.getElementById('groups-panel').classList.toggle('hidden', !isGroups);
  document.getElementById('resources-panel').classList.toggle('hidden', isGroups);
  document.getElementById('tab-groups').classList.toggle('active', isGroups);
  document.getElementById('tab-resources').classList.toggle('active', !isGroups);
  document.getElementById('download').dataset.mode = isGroups ? 'groups' : 'resources';
  document.getElementById('download').textContent = isGroups
    ? 'Download manual_groups.tsv'
    : 'Download manual_resources.tsv';
  document.getElementById('resource-extra-toolbar').style.display = isGroups ? 'none' : 'flex';
  document.body.classList.toggle('resources-mode', !isGroups);
  document.getElementById('search').value = '';
  applyFilter('');
  updateCount();
}

function applyFilter(q) {
  q = q.toLowerCase();
  document.querySelectorAll('tbody tr').forEach(tr => {
    tr.style.display = (!q || tr.dataset.searchText.includes(q)) ? '' : 'none';
  });
}

function updateCount() {
  const isGroups = !document.getElementById('groups-panel').classList.contains('hidden');
  if (isGroups) {
    const total = GROUPS_DATA.length;
    const modified = Object.keys(groupOverrides).filter(g => {
      const o = groupOverrides[g];
      return Object.keys(o || {}).length > 0;
    }).length;
    document.getElementById('count').textContent = modified + ' / ' + total + ' groups touched';
  } else {
    const total = RESOURCES_DATA.length;
    const modified = Object.keys(resourceOverrides).length;
    document.getElementById('count').textContent = modified + ' / ' + total + ' resources touched';
  }
}

function downloadTSV() {
  const mode = document.getElementById('download').dataset.mode;
  let rows;
  if (mode === 'groups') {
    const header = ['group','n_rules','n_more','n_less']
      .concat(AXES.map(a => 'llm_' + a))
      .concat(AXES.map(a => 'manual_' + a))
      .concat(['manual_action','polities','example_rule','example_verbatim']);
    rows = [header];
    GROUPS_DATA.forEach(row => {
      const ovr = groupOverrides[row.group] || {};
      const rec = [row.group, row.n_rules, row.n_more, row.n_less];
      AXES.forEach(ax => rec.push(row['llm_' + ax]));
      AXES.forEach(ax => rec.push(ovr[ax] != null ? ovr[ax] : row['llm_' + ax]));
      rec.push(ovr['__action'] || 'keep');
      rec.push(row.polities || '');
      rec.push(row.example || '');
      rec.push(row.verbatim || '');
      rows.push(rec);
    });
  } else {
    const header = ['resource','resource_meta','n_rules','n_more','n_less','llm_bucket','manual_bucket','example_rule','example_verbatim'];
    rows = [header];
    RESOURCES_DATA.forEach(row => {
      const ovr = resourceOverrides[row.resource];
      const manual = ovr != null ? ovr : (row.llm_bucket || '(drop)');
      rows.push([row.resource, row.resource_meta || '', row.n_rules, row.n_more, row.n_less,
                 row.llm_bucket || '', manual, row.example || '', row.verbatim || '']);
    });
  }
  const tsv = rows.map(r => r.map(c => String(c).replace(/\t/g, ' ').replace(/\n/g, ' ')).join('\t')).join('\n');
  const blob = new Blob([tsv], {type: 'text/tab-separated-values'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = mode === 'groups' ? 'manual_groups.tsv' : 'manual_resources.tsv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function resetOverrides() {
  const mode = document.getElementById('download').dataset.mode;
  if (!confirm('Reset all manual overrides for the ' + mode + ' tab to LLM defaults?')) return;
  if (mode === 'groups') {
    groupOverrides = {};
    saveOverrides(LS_GROUPS_KEY, groupOverrides);
    renderGroups();
  } else {
    resourceOverrides = {};
    saveOverrides(LS_RESOURCES_KEY, resourceOverrides);
    renderResources();
  }
}

document.getElementById('tab-groups').addEventListener('click', () => showTab('groups'));
document.getElementById('tab-resources').addEventListener('click', () => showTab('resources'));
document.getElementById('search').addEventListener('input', e => applyFilter(e.target.value));
document.getElementById('download').addEventListener('click', downloadTSV);
document.getElementById('reset').addEventListener('click', resetOverrides);
document.getElementById('add-bucket').addEventListener('click', addCustomBucket);
document.getElementById('new-bucket').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); addCustomBucket(); }
});

renderGroups();
renderResources();
showTab('groups');
</script>
</body>
</html>
"""


def main():
    g_rows, r_rows, n_rules = build_dataset()
    html = (HTML_TEMPLATE
            .replace('__N_RULES__',     str(n_rules))
            .replace('__N_GROUPS__',    str(len(g_rows)))
            .replace('__N_RESOURCES__', str(len(r_rows)))
            .replace('__AXES_JSON__',          json.dumps(AXES))
            .replace('__AXIS_VALS_JSON__',     json.dumps(AXIS_VALS))
            .replace('__RESOURCES_JSON__',     json.dumps(RESOURCES))
            .replace('__GROUPS_DATA_JSON__',   json.dumps(g_rows))
            .replace('__RESOURCES_DATA_JSON__', json.dumps(r_rows)))
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding='utf-8')
    print(f'Wrote {OUT_HTML.relative_to(ROOT)}  ({OUT_HTML.stat().st_size:,} bytes)')
    print(f'   {len(g_rows)} distinct groups, {len(r_rows)} distinct resources, {n_rules} rules in scope.')
    print(f'\nOpen the app:')
    print(f'   open {OUT_HTML}')


if __name__ == '__main__':
    main()
