#!/usr/bin/env bash
# End-to-end pipeline on the 100-work random sample:
#   (1) core extraction   (2) dimension scoring   (3) rule polity/time
# Then applies the strict filter and writes a filter report.
set -e
set -o pipefail

ROOT="/Users/charlesdedampierre/Desktop/Rsearch Folder/Human Rights"
cd "$ROOT"
PY=".venv/bin/python"
LOG="/tmp/random100_pipeline.log"
echo "=== pipeline started at $(date) ===" > "$LOG"

# --- Pass 1: core extraction ---
echo ""                                                                   | tee -a "$LOG"
echo "================ PASS 1: core extraction (669 chunks) ================"| tee -a "$LOG"
SAMPLE_TSV=data/processed_data/final_dataset_for_criteria_random100.tsv \
OUT_DIR=data/llm_results/core_v1_random100 \
  $PY scripts/classifiers/classify_core_v1.py 2>&1 | tee -a "$LOG"

# --- Pass 2: dimension scoring ---
echo ""                                                                        | tee -a "$LOG"
echo "================ PASS 2: dimension scoring ================"             | tee -a "$LOG"
CORE_DIR=data/llm_results/core_v1_random100 \
OUT_DIR=data/llm_results/core_v1_random100_dimensions \
  $PY scripts/classifiers/classify_dimensions_v1.py 2>&1 | tee -a "$LOG"

# --- Merge work-level polity/time into the 100-work rules TSV ---
echo ""                                                                        | tee -a "$LOG"
echo "================ MERGE: attach work-level polity/time priors ================"| tee -a "$LOG"
$PY - <<'PY' 2>&1 | tee -a "$LOG"
import pandas as pd
rules = pd.read_csv('data/llm_results/core_v1_random100_dimensions/rules_scored.tsv', sep='\t')
wpt   = pd.read_csv('data/processed_data/works_polity_time_dataset.tsv', sep='\t')
wpt = wpt[['file_id','cliopatria_polity','mentioned_polities_in_work',
           'mentioned_polity_reasoning','mentioned_time_reference',
           'mentioned_time_start_in_work','mentioned_time_end_in_work',
           'mentioned_time_reasoning']].rename(columns={
    'cliopatria_polity': 'work_author_polity_cliopatria',
    'mentioned_polities_in_work': 'work_polity',
    'mentioned_polity_reasoning': 'work_polity_reasoning',
    'mentioned_time_reference': 'work_time_reference',
    'mentioned_time_start_in_work': 'work_time_start',
    'mentioned_time_end_in_work': 'work_time_end',
    'mentioned_time_reasoning': 'work_time_reasoning',
})
merged = rules.merge(wpt, on='file_id', how='left')
out = 'data/processed_data/rules_random100_scored.tsv'
merged.to_csv(out, sep='\t', index=False)
print(f'{len(merged)} rules → {out}')
print(f'historian rules (work_polity filled): {merged["work_polity"].notna().sum()}')
PY

# --- Pass 3: rule-level polity/time (uses new work-priors prompt) ---
echo ""                                                                        | tee -a "$LOG"
echo "================ PASS 3: rule polity + time ================"            | tee -a "$LOG"
SRC=data/processed_data/rules_random100_scored.tsv \
OUT_DIR=data/llm_results/rule_polity_time_random100 \
OUT_TSV=data/processed_data/rules_random100_with_polity_time.tsv \
  $PY scripts/classifiers/classify_rule_polity_time.py 2>&1 | tee -a "$LOG"

# --- Filter report ---
echo ""                                                                        | tee -a "$LOG"
echo "================ FILTER REPORT ================"                         | tee -a "$LOG"
$PY - <<'PY' 2>&1 | tee -a "$LOG"
import pandas as pd
df = pd.read_csv('data/processed_data/rules_random100_with_polity_time.tsv', sep='\t')
print(f'Total rules: {len(df)}')

# Apply the requested filter
mask = (
    (df['resource_materiality'] >= 3)
    & (df['resource_generality']  >= 3)
    & (df['group_immutability']   >= 2)
    & (df['opinion_vs_fact']      >= 4)
)
kept = df[mask].copy()
print(f'\nPass `mat>=3 AND gen>=3 AND imm>=2 AND fact>=4`: {len(kept)} ({len(kept)/len(df):.1%})')

# By period / author distribution of kept
if len(kept):
    print('\nKept rules by period:')
    print(kept['period'].value_counts(dropna=False).to_string())
    print('\nKept rules by author:')
    print(kept['perseus_author'].value_counts().to_string())
    print('\nKept rules per work (top 15):')
    print(kept.groupby(['perseus_author','perseus_title']).size()
            .sort_values(ascending=False).head(15).to_string())
    print('\nPolity distribution (top 15):')
    print(kept['rule_polity'].value_counts().head(15).to_string())
    print('\nrule_contemporarity distribution on kept set:')
    print(kept['rule_contemporarity'].value_counts(dropna=False).to_string())

# Save the filtered subset
out = 'data/processed_data/rules_random100_filtered.tsv'
kept.to_csv(out, sep='\t', index=False)
print(f'\nFiltered subset saved: {out}')
PY

echo ""                                                                        | tee -a "$LOG"
echo "=== pipeline finished at $(date) ==="                                    | tee -a "$LOG"
