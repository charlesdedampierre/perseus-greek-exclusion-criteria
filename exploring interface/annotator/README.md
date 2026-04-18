# Rule annotator

A zero-dependency HTML tool to validate the rule-level polity + time-reference
classifications produced by
`scripts/classifiers/classify_work_polity.py`.

## How to use

1. (Re)build the stratified sample:

   ```bash
   python scripts/sample_building/build_annotation_sample.py
   ```

   Writes `data.js` (loaded by the HTML) and `sample.tsv`. Default quotas:

   | rule_time_reference | target | pool   |
   |---------------------|--------|--------|
   | contemporary        | 50     | 1,067  |
   | timeless            | 40     |   441  |
   | past                | 25     |    68  |
   | future              | all    |    17  |
   | mixed               | all    |     1  |

   Within each stratum, rules are picked round-robin across author × criterion
   pairs so the sample also spans ~19 authors and ~13 criteria.

2. Open `index.html` directly in a browser (no server needed).

3. For each rule, read the features table + verbatim quote on the right. Rate:
   - **👍 Valid** — the `rule_polity` and `rule_time_reference` annotations
     look correct.
   - **👎 Invalid** — one or both are wrong.
   - **Skip** — unsure / not relevant.

   Use the comment field to note why, especially for 👎.

   Keyboard: <kbd>↑</kbd> 👍 · <kbd>↓</kbd> 👎 · <kbd>→</kbd> next ·
   <kbd>←</kbd> prev · <kbd>s</kbd> skip.

4. Annotations persist in `localStorage` of your browser. Click **Export** to
   download `annotations_<timestamp>.json` and `.csv`.

5. **Stats** shows the distribution of your ratings per time-reference
   category so you can verify coverage.

## Notes

- To expand the sample, edit the `QUOTAS` dict at the top of
  `build_annotation_sample.py` and rebuild.
- To reset all ratings, click **Clear** (or clear your browser's
  localStorage for this file).
