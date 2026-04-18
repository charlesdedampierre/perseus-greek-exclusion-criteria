#!/usr/bin/env python3
"""
Exclusion Criteria Explorer - Interactive reviewer for LLM extraction results.

Run: python run_explorer.py
Then open: http://localhost:8766

Features:
- Displays criteria extracted by the LLM
- Allows adding comments/feedback on each criterion
- Saves feedback to user_feedback_v3.csv
"""

import csv
import json
import os
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8766
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Input: LLM extraction results
LLM_RESULTS_CSV = os.path.join(
    DATA_DIR, "llm_results", "exclusion_criteria_verbatims_v7.csv"
)

# Output: User comments
FEEDBACK_CSV = os.path.join(DATA_DIR, "user_comments", "user_comments_v7.csv")

# Generated HTML file
HTML_FILE = os.path.join(BASE_DIR, "exclusion_explorer.html")


def load_csv_data():
    """Load data from LLM results CSV."""
    data = []
    with open(LLM_RESULTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def get_unique_values(data, key):
    """Get sorted unique values for a field."""
    return sorted(set(row.get(key, "") for row in data if row.get(key)))


def compute_stratified_sample(data):
    """Compute stratified sample indices from data."""
    import pandas as pd

    df = pd.DataFrame(data)
    allocation = {
        "MORAL_CONDUCT": 3,
        "BIRTH_LINEAGE": 3,
        "ACHIEVEMENTS": 3,
        "CITIZENSHIP": 2,
        "PROPERTY_WEALTH": 2,
        "AGE": 2,
        "GENDER": 2,
        "FREEDOM_STATUS": 2,
        "OCCUPATION": 1,
        "LEGAL_STANDING": 1,
        "PHYSICAL_STATUS": 1,
    }

    sample_indices = []
    for cat, n in allocation.items():
        cat_df = df[df["criterion_category"] == cat]
        if len(cat_df) == 0:
            continue
        if len(cat_df) <= n:
            selected = cat_df
        else:
            cat_df = cat_df.sort_values(["author", "polity"])
            step = len(cat_df) / n
            indices = [int(i * step) for i in range(n)]
            selected = cat_df.iloc[indices]
        sample_indices.extend(selected.index.tolist())

    return sample_indices


def generate_html(data):
    """Generate the HTML explorer."""
    categories = get_unique_values(data, "criterion_category")
    authors = get_unique_values(data, "author")
    polities = get_unique_values(data, "polity")

    total_criteria = len(data)
    unique_works = len(set(row["work_name"] for row in data))

    sample_indices = compute_stratified_sample(data)
    sample_size = len(sample_indices)

    cat_options = "".join(f'<option value="{c}">{c}</option>' for c in categories)
    author_options = "".join(f'<option value="{a}">{a}</option>' for a in authors)
    polity_options = "".join(f'<option value="{p}">{p}</option>' for p in polities)

    data_json = json.dumps(data, ensure_ascii=False)
    sample_json = json.dumps(sample_indices)

    # Run metadata for export
    run_meta = {
        "prompt_version": "V7",
        "llm_model": "claude-opus-4-20250514",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "extraction_method": "hybrid (keywords 0.7 + embeddings 0.3)",
        "total_criteria": total_criteria,
        "total_works": unique_works,
        "sample_size": sample_size,
    }
    run_meta_json = json.dumps(run_meta)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exclusion Criteria Explorer</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚖️</text></svg>">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #333; line-height: 1.6; }}
        header {{ background: linear-gradient(135deg, #1a5276 0%, #2874a6 100%); color: white; padding: 1.5rem 2rem; }}
        header h1 {{ font-size: 1.5rem; font-weight: 500; }}
        header p {{ opacity: 0.85; font-size: 0.9rem; margin-top: 0.25rem; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
        .filters {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; background: white; padding: 1rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); align-items: flex-end; }}
        .filter-group {{ display: flex; flex-direction: column; gap: 0.25rem; }}
        .filter-group label {{ font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: #666; }}
        .filter-group select, .filter-group input {{ padding: 0.5rem 0.75rem; border: 1px solid #ddd; border-radius: 4px; font-size: 0.85rem; min-width: 150px; }}
        .clear-btn {{ padding: 0.5rem 1rem; background: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        .clear-btn:hover {{ background: #7f8c8d; }}
        .stats {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; font-size: 0.85rem; color: #666; flex-wrap: wrap; }}
        .stats span {{ background: white; padding: 0.5rem 1rem; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stats strong {{ color: #2c3e50; }}
        .results {{ display: flex; flex-direction: column; gap: 1rem; }}
        .card {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
        .card-header {{ padding: 1rem; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem; }}
        .card-title {{ font-size: 1rem; font-weight: 600; color: #2c3e50; }}
        .card-meta {{ display: flex; gap: 0.75rem; font-size: 0.8rem; color: #666; flex-wrap: wrap; }}
        .card-body {{ padding: 1rem; }}
        .badges {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }}
        .badge {{ display: inline-block; padding: 0.3rem 0.7rem; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }}
        .badge-category {{ background: #1a5276; color: white; }}
        .badge-label {{ background: #34495e; color: white; }}
        .badge-speaker {{ background: #e67e22; color: white; }}
        .badge-method {{ background: #8e44ad; color: white; }}
        .groups-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }}
        .group-box {{ padding: 0.75rem; border-radius: 6px; font-size: 0.9rem; }}
        .in-group {{ background: #e8f5e9; border-left: 4px solid #4caf50; }}
        .out-group {{ background: #ffebee; border-left: 4px solid #e53935; }}
        .group-label {{ font-size: 0.65rem; font-weight: 600; text-transform: uppercase; color: #666; margin-bottom: 0.25rem; }}
        .group-value {{ color: #333; font-weight: 500; }}
        .std-tag {{ display: inline-block; padding: 0.15rem 0.5rem; margin-left: 0.5rem; background: #eceff1; color: #546e7a; border-radius: 3px; font-size: 0.7rem; font-weight: 600; vertical-align: middle; }}
        .resource-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; }}
        .verbatim {{ font-style: italic; color: #555; padding: 1rem; background: #fafafa; border-left: 3px solid #9c27b0; margin-bottom: 1rem; border-radius: 0 4px 4px 0; }}
        .keywords-box {{ background: #f3e5f5; border-left: 4px solid #9c27b0; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; }}
        .keywords-box .group-label {{ color: #6a1b9a; }}
        .keyword-tag {{ display: inline-block; padding: 0.15rem 0.5rem; margin: 0.15rem; background: #ce93d8; color: white; border-radius: 3px; font-size: 0.75rem; }}

        /* Standardized labels */
        .std-row {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem; }}
        .std-box {{ padding: 0.5rem 0.75rem; border-radius: 6px; font-size: 0.8rem; background: #f0f4f8; border: 1px dashed #b0bec5; }}
        .std-box .std-label {{ font-size: 0.6rem; font-weight: 600; text-transform: uppercase; color: #78909c; margin-bottom: 0.2rem; }}
        .std-box .std-value {{ color: #263238; font-weight: 600; }}

        /* Annotation results dashboard */
        .annotation-dashboard {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1.5rem; margin-bottom: 1.5rem; }}
        .annotation-dashboard h2 {{ font-size: 1.1rem; font-weight: 600; color: #2c3e50; margin-bottom: 1rem; }}
        .ann-cat-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }}
        .ann-cat-name {{ min-width: 160px; font-size: 0.85rem; font-weight: 500; }}
        .ann-cat-counts {{ display: flex; gap: 0.5rem; font-size: 0.8rem; }}
        .ann-up {{ color: #2e7d32; font-weight: 600; }}
        .ann-down {{ color: #c62828; font-weight: 600; }}
        .ann-pending {{ color: #999; }}
        .ann-bar {{ flex: 1; height: 16px; background: #eee; border-radius: 4px; overflow: hidden; display: flex; }}
        .ann-bar-up {{ background: #4caf50; height: 100%; }}
        .ann-bar-down {{ background: #e53935; height: 100%; }}
        .ann-bar-pending {{ background: #e0e0e0; height: 100%; }}

        /* Export button */
        .export-section {{ display: flex; gap: 1rem; align-items: center; margin-bottom: 1.5rem; }}
        .export-btn {{ padding: 0.6rem 1.5rem; background: #1a5276; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 500; }}
        .export-btn:hover {{ background: #154360; }}
        .export-info {{ font-size: 0.8rem; color: #666; }}

        /* Thumbs up/down */
        .vote-section {{ display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.75rem; border-bottom: 1px solid #eee; }}
        .vote-btn {{ padding: 0.5rem 1rem; border: 2px solid #ddd; border-radius: 8px; cursor: pointer; font-size: 1.2rem; background: white; transition: all 0.2s; }}
        .vote-btn:hover {{ background: #f5f5f5; }}
        .vote-btn.selected-up {{ background: #e8f5e9; border-color: #4caf50; }}
        .vote-btn.selected-down {{ background: #ffebee; border-color: #e53935; }}
        .vote-label {{ font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: #666; }}
        .comment-section {{ padding-top: 1rem; border-top: 1px solid #eee; }}
        .comment-section label {{ font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: #666; display: block; margin-bottom: 0.5rem; }}
        .comment-input {{ width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9rem; font-family: inherit; resize: vertical; min-height: 50px; }}
        .comment-input:focus {{ outline: none; border-color: #27ae60; }}
        .comment-actions {{ display: flex; gap: 0.5rem; margin-top: 0.5rem; align-items: center; }}
        .save-btn {{ padding: 0.4rem 1rem; background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }}
        .save-btn:hover {{ background: #219a52; }}
        .save-status {{ font-size: 0.8rem; color: #27ae60; }}
        .no-results {{ text-align: center; padding: 3rem; color: #666; }}

        /* Dashboard styles */
        .dashboard {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1.5rem; margin-bottom: 1.5rem; }}
        .dashboard h2 {{ font-size: 1.1rem; font-weight: 600; color: #2c3e50; margin-bottom: 1rem; }}
        .chart-bar-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }}
        .chart-bar-label {{ min-width: 160px; font-size: 0.8rem; font-weight: 500; color: #333; text-align: right; }}
        .chart-bar-track {{ flex: 1; background: #eee; border-radius: 4px; height: 24px; position: relative; cursor: pointer; }}
        .chart-bar-fill {{ height: 100%; border-radius: 4px; background: #1a5276; display: flex; align-items: center; padding-left: 8px; min-width: 28px; transition: background 0.2s; }}
        .chart-bar-fill:hover {{ filter: brightness(1.15); }}
        .chart-bar-count {{ font-size: 0.75rem; color: white; font-weight: 600; }}

        .category-details {{ margin-top: 1.5rem; }}
        .category-section {{ border: 1px solid #eee; border-radius: 8px; margin-bottom: 1rem; overflow: hidden; }}
        .category-section-header {{ padding: 0.75rem 1rem; background: #f8f9fa; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 0.9rem; color: #2c3e50; }}
        .category-section-header:hover {{ background: #eef2f7; }}
        .category-section-header .toggle {{ font-size: 0.8rem; color: #888; }}
        .category-section-body {{ display: none; padding: 1rem; }}
        .category-section-body.open {{ display: block; }}
        .detail-columns {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }}
        .detail-col h4 {{ font-size: 0.7rem; text-transform: uppercase; color: #888; margin-bottom: 0.5rem; font-weight: 600; }}
        .detail-col ul {{ list-style: none; }}
        .detail-col li {{ font-size: 0.85rem; padding: 0.2rem 0; color: #444; }}
        .detail-col li .count {{ color: #999; font-size: 0.75rem; margin-left: 0.25rem; }}
        .detail-col.col-in li {{ border-left: 3px solid #4caf50; padding-left: 0.5rem; margin-bottom: 0.25rem; }}
        .detail-col.col-out li {{ border-left: 3px solid #e53935; padding-left: 0.5rem; margin-bottom: 0.25rem; }}
        .detail-col.col-res li {{ border-left: 3px solid #2196f3; padding-left: 0.5rem; margin-bottom: 0.25rem; }}

        /* Tabs */
        .tabs {{ display: flex; gap: 0; margin-bottom: 1.5rem; }}
        .tab {{ padding: 0.75rem 1.5rem; background: white; border: 1px solid #ddd; cursor: pointer; font-size: 0.9rem; font-weight: 500; color: #666; transition: all 0.2s; }}
        .tab:first-child {{ border-radius: 8px 0 0 8px; }}
        .tab:last-child {{ border-radius: 0 8px 8px 0; }}
        .tab.active {{ background: #1a5276; color: white; border-color: #1a5276; }}
        .tab .tab-count {{ font-size: 0.75rem; opacity: 0.7; margin-left: 0.25rem; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}

        /* Annotation progress */
        .annotation-progress {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 1rem 1.5rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 1rem; }}
        .progress-bar-track {{ flex: 1; background: #eee; border-radius: 4px; height: 8px; }}
        .progress-bar-fill {{ height: 100%; background: #27ae60; border-radius: 4px; transition: width 0.3s; }}
        .progress-text {{ font-size: 0.85rem; color: #666; white-space: nowrap; }}

        /* Sample card annotation extras */
        .annotation-status {{ display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }}
        .status-pending {{ background: #fff3e0; color: #e65100; }}
        .status-done {{ background: #e8f5e9; color: #2e7d32; }}

        @media (max-width: 768px) {{
            .groups-row {{ grid-template-columns: 1fr; }}
            .filters {{ flex-direction: column; }}
            .detail-columns {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>Exclusion Criteria Explorer</h1>
        <p>{total_criteria} criteria from {unique_works} works</p>
    </header>
    <div class="container">
        <div class="tabs">
            <div class="tab active" onclick="switchTab('explore')">All Criteria <span class="tab-count">({total_criteria})</span></div>
            <div class="tab" onclick="switchTab('annotate')">Annotation Sample <span class="tab-count">({sample_size})</span></div>
        </div>

        <div class="tab-content active" id="tab-explore">
            <div class="filters">
                <div class="filter-group">
                    <label>Category</label>
                    <select id="filterCategory"><option value="">All</option>{cat_options}</select>
                </div>
                <div class="filter-group">
                    <label>Author</label>
                    <select id="filterAuthor"><option value="">All</option>{author_options}</select>
                </div>
                <div class="filter-group">
                    <label>Polity</label>
                    <select id="filterPolity"><option value="">All</option>{polity_options}</select>
                </div>
                <div class="filter-group">
                    <label>Search</label>
                    <input type="text" id="filterSearch" placeholder="Search...">
                </div>
                <button class="clear-btn" onclick="clearFilters()">Clear</button>
            </div>
            <div class="stats" id="stats"></div>
            <div class="dashboard" id="dashboard"></div>
            <div class="results" id="results"></div>
        </div>

        <div class="tab-content" id="tab-annotate">
            <div class="annotation-progress">
                <span class="progress-text" id="annotation-count">0 / {sample_size} annotated</span>
                <div class="progress-bar-track"><div class="progress-bar-fill" id="annotation-bar" style="width:0%"></div></div>
            </div>
            <div class="export-section">
                <button class="export-btn" onclick="exportAnnotations()">Export Annotations</button>
                <span class="export-info" id="export-info"></span>
            </div>
            <div class="annotation-dashboard" id="annotation-dashboard"></div>
            <div class="results" id="sample-results"></div>
        </div>
    </div>
<script>
const DATA = {data_json};
const SAMPLE_INDICES = {sample_json};
const RUN_META = {run_meta_json};
const annotationState = {{}};  // index -> comment text

function switchTab(tab) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    if (tab === 'explore') {{
        document.querySelectorAll('.tab')[0].classList.add('active');
        document.getElementById('tab-explore').classList.add('active');
    }} else {{
        document.querySelectorAll('.tab')[1].classList.add('active');
        document.getElementById('tab-annotate').classList.add('active');
        renderSample();
        renderAnnotationDashboard();
    }}
}}

function updateAnnotationProgress() {{
    const commented = Object.keys(annotationState).length;
    const voted = Object.keys(voteState).length;
    const done = Math.max(commented, voted);
    const total = SAMPLE_INDICES.length;
    const pct = total > 0 ? (done / total) * 100 : 0;
    document.getElementById('annotation-count').textContent = `${{done}} / ${{total}} annotated`;
    document.getElementById('annotation-bar').style.width = `${{pct}}%`;
}}

function saveSampleComment(dataIndex) {{
    const comment = document.getElementById(`sample-comment-${{dataIndex}}`).value;
    if (!comment.trim()) return;

    annotationState[dataIndex] = comment;
    const d = DATA[dataIndex];

    fetch('/save_comment', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ ...d, comment, sample: 'stratified_v4' }})
    }}).then(r => {{
        if (r.ok) {{
            const statusEl = document.getElementById(`sample-status-${{dataIndex}}`);
            statusEl.textContent = '✓ Saved';
            setTimeout(() => statusEl.textContent = '', 2000);
            const badgeEl = document.getElementById(`sample-badge-${{dataIndex}}`);
            if (badgeEl) {{
                badgeEl.className = 'annotation-status status-done';
                badgeEl.textContent = 'done';
            }}
            updateAnnotationProgress();
        }}
    }});
}}

function renderSample() {{
    const container = document.getElementById('sample-results');
    updateAnnotationProgress();

    container.innerHTML = SAMPLE_INDICES.map(idx => {{
        const d = DATA[idx];
        const isDone = annotationState[idx];
        const statusClass = isDone ? 'status-done' : 'status-pending';
        const statusText = isDone ? 'done' : 'pending';

        return `
        <div class="card" style="border-left: 4px solid ${{CAT_COLORS[d.criterion_category] || '#1a5276'}}">
            <div class="card-header">
                <div class="card-title">${{d.work_name}}</div>
                <div class="card-meta">
                    <span>${{d.author}}</span>
                    <span>${{d.impact_year}}</span>
                    <span>${{d.polity}}</span>
                    <span class="annotation-status ${{statusClass}}" id="sample-badge-${{idx}}">${{statusText}}</span>
                </div>
            </div>
            <div class="card-body">
                <div class="badges">
                    <span class="badge badge-category">${{d.criterion_category}}</span>
                    <span class="badge badge-label">${{d.criterion_label}}</span>
                    ${{d.speaker ? `<span class="badge badge-speaker">${{d.speaker}}</span>` : ''}}
                </div>
                <div class="groups-row">
                    <div class="group-box in-group">
                        <div class="group-label">In-Group</div>
                        <div class="group-value">${{d.in_group}}${{stdTag(d.in_group_std)}}</div>
                    </div>
                    <div class="group-box out-group">
                        <div class="group-label">Out-Group</div>
                        <div class="group-value">${{d.out_group}}${{stdTag(d.out_group_std)}}</div>
                    </div>
                </div>
                <div class="resource-box">
                    <div class="group-label">Resource</div>
                    <div class="group-value">${{d.resource}}${{stdTag(d.resource_std)}}</div>
                </div>
                <div class="verbatim">"${{d.verbatim}}"</div>
                ${{renderKeywords(d)}}

                <div class="comment-section">
                    <div class="vote-section">
                        <span class="vote-label">Valid?</span>
                        <button class="vote-btn ${{voteState[idx]==='up' ? 'selected-up' : ''}}" id="vote-up-${{idx}}" onclick="vote(${{idx}}, 'up')">&#128077;</button>
                        <button class="vote-btn ${{voteState[idx]==='down' ? 'selected-down' : ''}}" id="vote-down-${{idx}}" onclick="vote(${{idx}}, 'down')">&#128078;</button>
                    </div>
                    <label>Annotation</label>
                    <textarea class="comment-input" id="sample-comment-${{idx}}" placeholder="Optional comment...">${{annotationState[idx] || ''}}</textarea>
                    <div class="comment-actions">
                        <button class="save-btn" onclick="saveSampleComment(${{idx}})">Save Comment</button>
                        <span class="save-status" id="sample-status-${{idx}}"></span>
                    </div>
                </div>
            </div>
        </div>`;
    }}).join('');
}}

const voteState = {{}};  // index -> 'up' or 'down'

function stdTag(val) {{
    if (!val) return '';
    return `<span class="std-tag">${{val}}</span>`;
}}

function vote(idx, direction) {{
    voteState[idx] = direction;
    const upBtn = document.getElementById(`vote-up-${{idx}}`);
    const downBtn = document.getElementById(`vote-down-${{idx}}`);
    upBtn.className = 'vote-btn' + (direction === 'up' ? ' selected-up' : '');
    downBtn.className = 'vote-btn' + (direction === 'down' ? ' selected-down' : '');

    const d = DATA[idx];
    fetch('/save_comment', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ ...d, comment: document.getElementById(`sample-comment-${{idx}}`)?.value || '', vote: direction, sample: 'stratified_v7' }})
    }});

    const badgeEl = document.getElementById(`sample-badge-${{idx}}`);
    if (badgeEl) {{
        badgeEl.className = 'annotation-status status-done';
        badgeEl.textContent = 'done';
    }}
    updateAnnotationProgress();
    renderAnnotationDashboard();
}}

function renderAnnotationDashboard() {{
    const dashboard = document.getElementById('annotation-dashboard');
    if (!dashboard) return;

    // Group sample items by category
    const catData = {{}};
    SAMPLE_INDICES.forEach(idx => {{
        const d = DATA[idx];
        const cat = d.criterion_category || 'UNKNOWN';
        if (!catData[cat]) catData[cat] = [];
        catData[cat].push(idx);
    }});

    // Count votes per category
    const cats = Object.keys(catData).sort();
    let totalUp = 0, totalDown = 0, totalPending = 0;

    const rows = cats.map(cat => {{
        const indices = catData[cat];
        let up = 0, down = 0, pending = 0;
        indices.forEach(idx => {{
            if (voteState[idx] === 'up') up++;
            else if (voteState[idx] === 'down') down++;
            else pending++;
        }});
        totalUp += up; totalDown += down; totalPending += pending;
        const total = indices.length;
        const upPct = (up / total) * 100;
        const downPct = (down / total) * 100;
        const pendingPct = (pending / total) * 100;

        return `<div class="ann-cat-row">
            <div class="ann-cat-name">${{cat}} (${{total}})</div>
            <div class="ann-bar">
                <div class="ann-bar-up" style="width:${{upPct}}%"></div>
                <div class="ann-bar-down" style="width:${{downPct}}%"></div>
                <div class="ann-bar-pending" style="width:${{pendingPct}}%"></div>
            </div>
            <div class="ann-cat-counts">
                <span class="ann-up">&#128077; ${{up}}</span>
                <span class="ann-down">&#128078; ${{down}}</span>
                <span class="ann-pending">? ${{pending}}</span>
            </div>
        </div>`;
    }}).join('');

    const totalAll = totalUp + totalDown + totalPending;
    const accuracy = totalAll - totalPending > 0 ? ((totalUp / (totalUp + totalDown)) * 100).toFixed(0) : '-';

    dashboard.innerHTML = `
        <h2>Annotation Results by Category</h2>
        ${{rows}}
        <div class="ann-cat-row" style="border-top: 2px solid #333; margin-top: 0.5rem; padding-top: 0.75rem; font-weight: 600;">
            <div class="ann-cat-name">TOTAL (${{totalAll}})</div>
            <div class="ann-bar">
                <div class="ann-bar-up" style="width:${{totalUp/totalAll*100}}%"></div>
                <div class="ann-bar-down" style="width:${{totalDown/totalAll*100}}%"></div>
                <div class="ann-bar-pending" style="width:${{totalPending/totalAll*100}}%"></div>
            </div>
            <div class="ann-cat-counts">
                <span class="ann-up">&#128077; ${{totalUp}}</span>
                <span class="ann-down">&#128078; ${{totalDown}}</span>
                <span class="ann-pending">? ${{totalPending}}</span>
            </div>
        </div>
        <div style="margin-top:1rem; font-size:0.85rem; color:#555;">
            Accuracy (valid / annotated): <strong>${{accuracy}}%</strong>
        </div>
    `;
}}

function exportAnnotations() {{
    const rows = [['work_name','author','impact_year','polity','criterion_category','criterion_label',
                   'in_group','in_group_std','out_group','out_group_std','resource','resource_std',
                   'speaker','verbatim','matched_keywords','vote','comment',
                   'prompt_version','llm_model','embedding_model','extraction_method',
                   'total_criteria','total_works','sample_size']];

    let annotated = 0;
    SAMPLE_INDICES.forEach(idx => {{
        const d = DATA[idx];
        const v = voteState[idx] || '';
        const c = annotationState[idx] || '';
        if (v || c) annotated++;
        rows.push([
            d.work_name, d.author, d.impact_year, d.polity,
            d.criterion_category, d.criterion_label,
            d.in_group, d.in_group_std || '', d.out_group, d.out_group_std || '',
            d.resource, d.resource_std || '',
            d.speaker, d.verbatim, d.matched_keywords || '',
            v, c,
            RUN_META.prompt_version, RUN_META.llm_model, RUN_META.embedding_model,
            RUN_META.extraction_method, RUN_META.total_criteria,
            RUN_META.total_works, RUN_META.sample_size
        ]);
    }});

    // CSV encode
    const csvContent = rows.map(row =>
        row.map(cell => {{
            const s = String(cell).replace(/"/g, '""');
            return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${{s}}"` : s;
        }}).join(',')
    ).join('\n');

    const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `annotation_export_${{RUN_META.prompt_version}}_${{new Date().toISOString().slice(0,10)}}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    document.getElementById('export-info').textContent = `Exported ${{annotated}} annotated / ${{SAMPLE_INDICES.length}} total`;
}}

function renderKeywords(d) {{
    if (!d.matched_keywords || d.matched_keywords.trim() === '') return '';
    const tags = d.matched_keywords.split(', ').map(k => `<span class="keyword-tag">${{k}}</span>`).join('');
    return `<div class="keywords-box">
        <div class="group-label">Matched Keywords</div>
        ${{tags}}
    </div>`;
}}

function countBy(arr, key) {{
    const counts = {{}};
    arr.forEach(d => {{
        const val = d[key] || 'Unknown';
        counts[val] = (counts[val] || 0) + 1;
    }});
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}}

const CAT_COLORS = {{
    'MORAL_CONDUCT': '#e74c3c', 'BIRTH_LINEAGE': '#9b59b6', 'ACHIEVEMENTS': '#f39c12',
    'CITIZENSHIP': '#3498db', 'PROPERTY_WEALTH': '#2ecc71', 'AGE': '#1abc9c',
    'GENDER': '#e91e63', 'FREEDOM_STATUS': '#ff9800', 'OCCUPATION': '#607d8b',
    'PHYSICAL_STATUS': '#795548', 'LEGAL_STANDING': '#00bcd4'
}};

function renderDashboard(filtered) {{
    const dashboard = document.getElementById('dashboard');
    const catCounts = countBy(filtered, 'criterion_category');
    const maxCount = catCounts.length > 0 ? catCounts[0][1] : 1;

    // Bar chart
    const bars = catCounts.map(([cat, count]) => {{
        const pct = (count / maxCount) * 100;
        const color = CAT_COLORS[cat] || '#1a5276';
        return `<div class="chart-bar-row">
            <div class="chart-bar-label">${{cat}}</div>
            <div class="chart-bar-track" onclick="document.getElementById('filterCategory').value='${{cat}}'; applyFilters();">
                <div class="chart-bar-fill" style="width:${{pct}}%; background:${{color}}">
                    <span class="chart-bar-count">${{count}}</span>
                </div>
            </div>
        </div>`;
    }}).join('');

    // Per-category details
    const details = catCounts.map(([cat, count]) => {{
        const catData = filtered.filter(d => d.criterion_category === cat);
        const inGroups = countBy(catData, 'in_group');
        const outGroups = countBy(catData, 'out_group');
        const resources = countBy(catData, 'resource');
        const color = CAT_COLORS[cat] || '#1a5276';

        const renderList = (items) => items.map(([val, c]) =>
            `<li>${{val}}<span class="count">(${{c}})</span></li>`
        ).join('');

        return `<div class="category-section">
            <div class="category-section-header" onclick="this.nextElementSibling.classList.toggle('open'); this.querySelector('.toggle').textContent = this.nextElementSibling.classList.contains('open') ? '&#9660;' : '&#9654;';" style="border-left: 4px solid ${{color}}">
                <span>${{cat}} <span style="color:#888; font-weight:400">(${{count}})</span></span>
                <span class="toggle">&#9654;</span>
            </div>
            <div class="category-section-body">
                <div class="detail-columns">
                    <div class="detail-col col-in">
                        <h4>In-Groups</h4>
                        <ul>${{renderList(inGroups)}}</ul>
                    </div>
                    <div class="detail-col col-out">
                        <h4>Out-Groups</h4>
                        <ul>${{renderList(outGroups)}}</ul>
                    </div>
                    <div class="detail-col col-res">
                        <h4>Resources</h4>
                        <ul>${{renderList(resources)}}</ul>
                    </div>
                </div>
            </div>
        </div>`;
    }}).join('');

    dashboard.innerHTML = `
        <h2>Category Distribution</h2>
        ${{bars}}
        <div class="category-details">
            <h2 style="margin-top:1.5rem">Details by Category</h2>
            ${{details}}
        </div>
    `;
}}

function renderCards(filtered) {{
    const container = document.getElementById('results');
    const stats = document.getElementById('stats');

    renderDashboard(filtered);

    stats.innerHTML = `
        <span>Showing <strong>${{filtered.length}}</strong> of <strong>${{DATA.length}}</strong></span>
        <span>Works: <strong>${{new Set(filtered.map(d => d.work_name)).size}}</strong></span>
    `;

    if (filtered.length === 0) {{
        container.innerHTML = '<div class="no-results">No criteria match your filters.</div>';
        return;
    }}

    container.innerHTML = filtered.map((d, i) => `
        <div class="card">
            <div class="card-header">
                <div class="card-title">${{d.work_name}}</div>
                <div class="card-meta">
                    <span>${{d.author}}</span>
                    <span>${{d.impact_year}}</span>
                    <span>${{d.polity}}</span>
                </div>
            </div>
            <div class="card-body">
                <div class="badges">
                    <span class="badge badge-category">${{d.criterion_category}}</span>
                    <span class="badge badge-label">${{d.criterion_label}}</span>
                    ${{d.speaker ? `<span class="badge badge-speaker">${{d.speaker}}</span>` : ''}}
                    <span class="badge badge-method">${{d.extraction_method}}</span>
                </div>
                <div class="groups-row">
                    <div class="group-box in-group">
                        <div class="group-label">In-Group</div>
                        <div class="group-value">${{d.in_group}}${{stdTag(d.in_group_std)}}</div>
                    </div>
                    <div class="group-box out-group">
                        <div class="group-label">Out-Group</div>
                        <div class="group-value">${{d.out_group}}${{stdTag(d.out_group_std)}}</div>
                    </div>
                </div>
                <div class="resource-box">
                    <div class="group-label">Resource</div>
                    <div class="group-value">${{d.resource}}${{stdTag(d.resource_std)}}</div>
                </div>
                <div class="verbatim">"${{d.verbatim}}"</div>
                ${{renderKeywords(d)}}

                <div class="comment-section">
                    <label>Your Feedback</label>
                    <textarea class="comment-input" id="comment-${{i}}" placeholder="Add feedback..."></textarea>
                    <div class="comment-actions">
                        <button class="save-btn" onclick="saveComment(${{i}})">Save</button>
                        <span class="save-status" id="status-${{i}}"></span>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}}

function applyFilters() {{
    const category = document.getElementById('filterCategory').value;
    const author = document.getElementById('filterAuthor').value;
    const polity = document.getElementById('filterPolity').value;
    const search = document.getElementById('filterSearch').value.toLowerCase();

    const filtered = DATA.filter(d => {{
        if (category && d.criterion_category !== category) return false;
        if (author && d.author !== author) return false;
        if (polity && d.polity !== polity) return false;
        if (search && !d.verbatim.toLowerCase().includes(search) && !d.criterion_label.toLowerCase().includes(search)) return false;
        return true;
    }});

    renderCards(filtered);
}}

function clearFilters() {{
    document.getElementById('filterCategory').value = '';
    document.getElementById('filterAuthor').value = '';
    document.getElementById('filterPolity').value = '';
    document.getElementById('filterSearch').value = '';
    applyFilters();
}}

async function saveComment(index) {{
    const comment = document.getElementById(`comment-${{index}}`).value;
    if (!comment.trim()) return;

    const d = DATA[index];
    try {{
        const response = await fetch('/save_comment', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ ...d, comment }})
        }});
        if (response.ok) {{
            document.getElementById(`status-${{index}}`).textContent = '✓ Saved';
            setTimeout(() => document.getElementById(`status-${{index}}`).textContent = '', 2000);
        }}
    }} catch (e) {{
        document.getElementById(`status-${{index}}`).textContent = 'Error';
    }}
}}

document.getElementById('filterCategory').addEventListener('change', applyFilters);
document.getElementById('filterAuthor').addEventListener('change', applyFilters);
document.getElementById('filterPolity').addEventListener('change', applyFilters);
document.getElementById('filterSearch').addEventListener('input', applyFilters);

applyFilters();
renderAnnotationDashboard();
</script>
</body>
</html>"""


def ensure_feedback_csv():
    """Create feedback CSV with headers if it doesn't exist."""
    if not os.path.exists(FEEDBACK_CSV):
        with open(FEEDBACK_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "work_name",
                    "author",
                    "impact_year",
                    "polity",
                    "criterion_category",
                    "criterion_label",
                    "in_group",
                    "out_group",
                    "resource",
                    "speaker",
                    "verbatim",
                    "extraction_method",
                    "vote",
                    "comment",
                ]
            )


class ExplorerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_POST(self):
        if self.path == "/save_comment":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            fieldnames = [
                "work_name",
                "author",
                "impact_year",
                "polity",
                "criterion_category",
                "criterion_label",
                "in_group",
                "out_group",
                "resource",
                "speaker",
                "verbatim",
                "extraction_method",
                "vote",
                "comment",
            ]

            new_row = [data.get(f, "") for f in fieldnames]
            # Use work_name + verbatim[:100] as unique key
            key_work = data.get("work_name", "")
            key_verb = data.get("verbatim", "")[:100]

            # Read existing rows, replace if key matches, else append
            existing_rows = []
            if os.path.exists(FEEDBACK_CSV):
                with open(FEEDBACK_CSV, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        existing_rows.append(row)

            # Find and replace or append
            replaced = False
            for i, row in enumerate(existing_rows):
                if len(row) >= 11 and row[0] == key_work and row[10][:100] == key_verb:
                    existing_rows[i] = new_row
                    replaced = True
                    break

            if not replaced:
                existing_rows.append(new_row)

            # Write back
            with open(FEEDBACK_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(fieldnames)
                writer.writerows(existing_rows)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    # Check if LLM results exist
    if not os.path.exists(LLM_RESULTS_CSV):
        print(f"ERROR: LLM results not found at {LLM_RESULTS_CSV}")
        print("Run extract_exclusion_criteria_v3.py first.")
        return

    # Generate HTML
    print("Loading LLM results...")
    data = load_csv_data()
    print(f"Found {len(data)} criteria")

    print("Generating HTML explorer...")
    html = generate_html(data)
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    # Ensure feedback CSV exists
    ensure_feedback_csv()

    print(f"\nStarting server on http://localhost:{PORT}")
    print(f"Feedback will be saved to: {FEEDBACK_CSV}")
    print("Press Ctrl+C to stop\n")

    webbrowser.open(f"http://localhost:{PORT}/exclusion_explorer.html")

    server = HTTPServer(("localhost", PORT), ExplorerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
