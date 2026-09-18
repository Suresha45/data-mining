# Q2 corpus profile

Measured by `q2_experiments.py` from the eight files in `notices/`. Source labels used only from `labelled_pairs.csv`; `_truth/` was not used for evaluation.

- Notices: **12000**
- Portals: **260**
- Corpus bytes excluding generated outputs: **62903659**
- Labelled pairs: **900**; SAME **279**, DIFFERENT **621**
- Label share: SAME **0.310**, DIFFERENT **0.690**
- Null/empty fields: `{}`
- Total text length: `{'n': 12000, 'min': 1542, 'p50': 4562, 'p90': 6287, 'p95': 6790, 'p99': 7507, 'max': 8223, 'mean': 4607.874833333333}`
- Body length: `{'n': 12000, 'min': 1500, 'p50': 4482, 'p90': 6209, 'p95': 6710, 'p99': 7423, 'max': 8127, 'mean': 4527.3000833333335}`
- Estimated value: `{'n': 12000, 'min': 1540000.0, 'p50': 37540000.0, 'p90': 381300000.0, 'p95': 676250000.0, 'p99': 916500000.0, 'max': 999750000.0, 'mean': 133481107.5}`
- Published years: `{'2024': 6623, '2025': 5377}`
- Closing years: `{'2024': 6076, '2025': 5924}`

The portal notes were used as interpretation: P001-P006 are aggregators with repeated preambles, reference numbers are portal-specific, dates and money have multiple renderings, and corrigenda are new notices.

Top portals: P094=1426, P002=800, P006=792, P001=778, P003=772, P005=768, P004=755, P020=384, P240=377, P044=224, P215=153, P181=133, P013=110, P227=107, P088=97.

Likely boilerplate/reference-number patterns were measured in the representation comparison: raw text retains these tokens; the clean representation replaces reference/date/money patterns and known aggregator boilerplate before tokenization.
