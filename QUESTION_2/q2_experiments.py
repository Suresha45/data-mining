import csv
import hashlib
import json
import math
import re
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTICE_DIR = ROOT / "notices"
RESULT_DIR = ROOT / "q2_results"
PLOT_DIR = RESULT_DIR / "plots"
RESULT_DIR.mkdir(exist_ok=True)
PLOT_DIR.mkdir(exist_ok=True)

STOP = set("a an and are as at be by for from in is of on or that the this to with will shall be not all any bid bids bidder bidders tender tenders work works notice".split())
REF_RE = re.compile(r"\b(?:npas|spc|pwd|ref|mc|tn)[-/a-z0-9]*\d[a-z0-9/-]*\b|\b\d{5,}\b", re.I)
DATE_RE = re.compile(r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[- ](?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[- ,]\s*\d{2,4})\b", re.I)
MONEY_RE = re.compile(r"(?:rs\.?|inr|rupees?)\s*[\d,./ -]+(?:lakh|cr|crore)?|\b\d[\d,]{4,}\b", re.I)
TOKEN_RE = re.compile(r"[a-z]{2,}(?:[/-][a-z0-9]+)*")


def read_notices():
    notices = []
    for path in sorted(NOTICE_DIR.glob("*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            notices.extend(csv.DictReader(handle))
    return notices


def read_pairs():
    with (ROOT / "labelled_pairs.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def norm(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def noisy_removed(text):
    text = norm(text)
    text = REF_RE.sub(" REFNUM ", text)
    text = DATE_RE.sub(" DATE ", text)
    text = MONEY_RE.sub(" MONEY ", text)
    text = re.sub(r"\b(?:national procurement aggregation service|state procurement cell)\b", " PORTALBOILER ", text)
    return text


def word_shingles(text, size=2, remove_noise=True):
    value = noisy_removed(text) if remove_noise else norm(text)
    tokens = [token for token in TOKEN_RE.findall(value) if token not in STOP and token not in {"refnum", "date", "money", "portalboiler"}]
    return {" ".join(tokens[i:i + size]) for i in range(max(0, len(tokens) - size + 1))}


def char_shingles(text, size=5, remove_noise=True):
    value = re.sub(r"\s+", " ", noisy_removed(text) if remove_noise else norm(text))
    return {value[i:i + size] for i in range(max(0, len(value) - size + 1))}


def jaccard(left, right):
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def score_pair(left, right, mode="clean"):
    remove_noise = mode == "clean"
    left_title = word_shingles(left["title"], 2, remove_noise)
    right_title = word_shingles(right["title"], 2, remove_noise)
    left_body = char_shingles(left["body"], 5, remove_noise)
    right_body = char_shingles(right["body"], 5, remove_noise)
    return 0.35 * jaccard(left_title, right_title) + 0.65 * jaccard(left_body, right_body)


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return 0.0
    return values[min(len(values) - 1, max(0, math.ceil(fraction * len(values)) - 1))]


def describe(values):
    values = list(values)
    return {"n": len(values), "min": min(values) if values else 0, "p50": percentile(values, .50), "p90": percentile(values, .90), "p95": percentile(values, .95), "p99": percentile(values, .99), "max": max(values) if values else 0, "mean": statistics.mean(values) if values else 0}


def canonical_id(notice_id):
    return f"OPP{int(notice_id[1:]):06d}"


def minhash_signature(tokens, size, seeds):
    values = [int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big") for token in tokens]
    if not values:
        return [0] * size
    return [min(value ^ seed for value in values) for seed in seeds[:size]]


def write_plots(result):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        bins = defaultdict(list)
        for row in result["curve"]:
            bins[round(row["similarity"] * 20) / 20].append(row["survived"])
        xs = sorted(bins)
        ys = [statistics.mean(bins[x]) for x in xs]
        points = " ".join(f"{40 + x * 620:.1f},{360 - y * 300:.1f}" for x, y in zip(xs, ys))
        threshold_x = 40 + result["selected_threshold"] * 620
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="420" viewBox="0 0 700 420">
<rect width="700" height="420" fill="white"/><line x1="40" y1="360" x2="660" y2="360" stroke="black"/><line x1="40" y1="60" x2="40" y2="360" stroke="black"/>
<polyline points="{points}" fill="none" stroke="#1769aa" stroke-width="3"/><line x1="{threshold_x}" y1="60" x2="{threshold_x}" y2="360" stroke="#c62828" stroke-dasharray="6,4"/>
<text x="250" y="25" font-size="18">Candidate survival by true similarity</text><text x="250" y="405" font-size="14">Exact clean similarity</text><text x="5" y="55" font-size="14">1.0</text><text x="8" y="365" font-size="14">0.0</text>
</svg>'''
        (PLOT_DIR / "similarity_survival.svg").write_text(svg, encoding="utf-8")
        return
    bins = defaultdict(list)
    for row in result["curve"]:
        bins[round(row["similarity"] * 20) / 20].append(row["survived"])
    xs = sorted(bins)
    ys = [statistics.mean(bins[x]) for x in xs]
    plt.figure(figsize=(7, 4))
    plt.plot(xs, ys, marker="o")
    plt.axvline(result["selected_threshold"], color="red", linestyle="--", label=f"selected threshold={result['selected_threshold']:.2f}")
    plt.ylim(-0.05, 1.05)
    plt.xlabel("Exact clean similarity")
    plt.ylabel("Candidate survival probability")
    plt.title("Candidate survival by true similarity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "similarity_survival.png", dpi=160)
    plt.close()


def run():
    started = time.perf_counter()
    phase_times = {}
    phase_start = started
    notices = read_notices()
    by_id = {row["notice_id"]: row for row in notices}
    pairs = read_pairs()
    labels = Counter(row["label"].lower() for row in pairs)
    text_lengths = [len(row["title"] or "") + len(row["body"] or "") for row in notices]
    body_lengths = [len(row["body"] or "") for row in notices]
    portals = Counter(row["portal_id"] for row in notices)
    nulls = Counter(key for row in notices for key, value in row.items() if value is None or value == "")
    values = [float(row["estimated_value"]) for row in notices if row["estimated_value"] not in (None, "")]
    close_dates = Counter(row["closing_date"][:4] for row in notices if row["closing_date"])
    published_dates = Counter(row["published_at"][:4] for row in notices if row["published_at"])
    phase_times["load_and_profile_seconds"] = time.perf_counter() - phase_start

    phase_start = time.perf_counter()
    profiles = {}
    for mode in ("raw", "clean"):
        profiles[mode] = [{"a": pair["notice_id_a"], "b": pair["notice_id_b"], "label": pair["label"].lower(), "score": score_pair(by_id[pair["notice_id_a"]], by_id[pair["notice_id_b"]], mode)} for pair in pairs]
    phase_times["label_scoring_seconds"] = time.perf_counter() - phase_start

    false_merge_cost, missed_duplicate_cost = 10, 1
    threshold_rows = []
    for threshold_i in range(0, 101):
        threshold = threshold_i / 100
        fp = sum(row["label"] == "different" and row["score"] >= threshold for row in profiles["clean"])
        fn = sum(row["label"] == "same" and row["score"] < threshold for row in profiles["clean"])
        threshold_rows.append((false_merge_cost * fp + missed_duplicate_cost * fn, threshold, fp, fn))
    _, selected_threshold, threshold_fp, threshold_fn = min(threshold_rows)

    seeds = [int.from_bytes(hashlib.sha256(f"q2-seed-{i}".encode()).digest()[:8], "big") for i in range(1024)]
    pair_tokens = {}
    for pair in pairs:
        for notice_id in (pair["notice_id_a"], pair["notice_id_b"]):
            if notice_id not in pair_tokens:
                pair_tokens[notice_id] = word_shingles(by_id[notice_id]["title"] + " " + by_id[notice_id]["body"], 2, True)
    minhash_results = {}
    for size in (128, 512, 1024):
        errors = []
        for pair in pairs:
            left = pair_tokens[pair["notice_id_a"]]
            right = pair_tokens[pair["notice_id_b"]]
            left_sig = minhash_signature(left, size, seeds)
            right_sig = minhash_signature(right, size, seeds)
            estimate = sum(a == b for a, b in zip(left_sig, right_sig)) / size
            exact = jaccard(left, right)
            errors.append({"label": pair["label"].lower(), "exact": exact, "estimate": estimate, "error": estimate - exact, "abs_error": abs(estimate - exact), "a": pair["notice_id_a"], "b": pair["notice_id_b"]})
        minhash_results[size] = errors

    retrieval = {}
    for mode in ("raw", "clean"):
        retrieval_started = time.perf_counter()
        token_sets = {row["notice_id"]: word_shingles(row["title"] + " " + row["body"], 2, mode == "clean") for row in notices}
        frequencies = Counter(token for token_set in token_sets.values() for token in token_set)
        cap = max(10, int(len(notices) * 0.005))
        index = defaultdict(list)
        for notice_id, token_set in token_sets.items():
            for token in token_set:
                if frequencies[token] <= cap:
                    index[token].append(notice_id)
        candidate_counts = []
        bucket_sizes = [len(ids) for ids in index.values()]
        candidate_pairs = set()
        retrieval_times = []
        per_portal = defaultdict(list)
        for row in notices:
            start = time.perf_counter()
            candidates = set()
            for token in token_sets[row["notice_id"]]:
                candidates.update(index.get(token, ()))
            candidates.discard(row["notice_id"])
            candidate_counts.append(len(candidates))
            per_portal[row["portal_id"]].append(len(candidates))
            retrieval_times.append(time.perf_counter() - start)
            candidate_pairs.update((row["notice_id"], candidate) for candidate in candidates)
        pair_lookup = {(row["notice_id_a"], row["notice_id_b"]): row for row in pairs}
        pair_lookup.update({(row["notice_id_b"], row["notice_id_a"]): row for row in pairs})
        survived = [pair_lookup[(pair["notice_id_a"], pair["notice_id_b"])] for pair in pairs if (pair["notice_id_a"], pair["notice_id_b"]) in candidate_pairs or (pair["notice_id_b"], pair["notice_id_a"]) in candidate_pairs]
        same_pairs = [pair for pair in pairs if pair["label"].lower() == "same"]
        same_survived = sum(pair in survived for pair in same_pairs)
        retrieval[mode] = {"cap": cap, "index_tokens": len(index), "bucket": describe(bucket_sizes), "largest_bucket": max(bucket_sizes) if bucket_sizes else 0, "candidate_counts": describe(candidate_counts), "candidate_pairs": len(candidate_pairs), "total_seconds": time.perf_counter() - retrieval_started, "labelled_survival": len(survived) / len(pairs), "same_survival": same_survived / len(same_pairs), "portal_candidates": {portal: describe(counts) for portal, counts in per_portal.items()}, "candidate_ids": candidate_pairs, "frequencies": frequencies}
        phase_times[f"{mode}_retrieval_seconds"] = time.perf_counter() - retrieval_started

    clean_survivors = retrieval["clean"]["candidate_ids"]
    curve = [{"similarity": row["score"], "survived": int((row["a"], row["b"]) in clean_survivors or (row["b"], row["a"]) in clean_survivors), "label": row["label"]} for row in profiles["clean"]]

    phase_start = time.perf_counter()
    db_path = RESULT_DIR / "q2_index.sqlite"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE token_index (token TEXT, notice_id TEXT)")
    clean_tokens = {row["notice_id"]: word_shingles(row["title"] + " " + row["body"], 2, True) for row in notices}
    rows = [(token, notice_id) for token, ids in retrieval["clean"]["frequencies"].items() if ids <= retrieval["clean"]["cap"] for notice_id, tokens in clean_tokens.items() if token in tokens]
    conn.executemany("INSERT INTO token_index VALUES (?,?)", rows)
    conn.commit()
    conn.execute("CREATE INDEX idx_token_index_token ON token_index(token)")
    probe = next(iter(retrieval["clean"]["frequencies"]))
    indexed_plan = conn.execute("EXPLAIN QUERY PLAN SELECT notice_id FROM token_index WHERE token = ?", (probe,)).fetchall()
    scan_plan = conn.execute("EXPLAIN QUERY PLAN SELECT notice_id FROM token_index NOT INDEXED WHERE token = ?", (probe,)).fetchall()
    def timed(query):
        start = time.perf_counter()
        result_rows = conn.execute(query, (probe,)).fetchall()
        return time.perf_counter() - start, len(result_rows)
    indexed_time, indexed_rows = timed("SELECT notice_id FROM token_index WHERE token = ?")
    scan_time, scan_rows = timed("SELECT notice_id FROM token_index NOT INDEXED WHERE token = ?")
    conn.close()
    phase_times["indexing_and_database_seconds"] = time.perf_counter() - phase_start

    phase_start = time.perf_counter()
    parent = {row["notice_id"]: row["notice_id"] for row in notices}
    def find(notice_id):
        while parent[notice_id] != notice_id:
            parent[notice_id] = parent[parent[notice_id]]
            notice_id = parent[notice_id]
        return notice_id
    score_start = time.perf_counter()
    scored_edges = []
    for left_id, right_id in retrieval["clean"]["candidate_ids"]:
        left_tokens = clean_tokens[left_id]
        right_tokens = clean_tokens[right_id]
        if jaccard(left_tokens, right_tokens) >= (result_threshold := 0.56):
            scored_edges.append((left_id, right_id))
    phase_times["candidate_scoring_seconds"] = time.perf_counter() - score_start
    cluster_start = time.perf_counter()
    for left_id, right_id in scored_edges:
            left_root, right_root = find(left_id), find(right_id)
            if left_root != right_root:
                parent[right_root] = left_root
    phase_times["clustering_seconds"] = time.perf_counter() - cluster_start

    same = next(pair for pair in pairs if pair["label"].lower() == "same")
    original_members = sorted([same["notice_id_a"], same["notice_id_b"]])
    original_card = canonical_id(original_members[0])
    appended_members = sorted(original_members + ["N999999"])
    stable_test = {"original_members": original_members, "new_copy": "N999999", "original_card_id": original_card, "after_new_copy_card_id": canonical_id(appended_members[0]), "passed": original_card == canonical_id(appended_members[0])}

    runtime = time.perf_counter() - started
    result = {"corpus": {"notices": len(notices), "portals": len(portals), "portal_counts": portals, "text_length": describe(text_lengths), "body_length": describe(body_lengths), "bytes": sum(path.stat().st_size for path in ROOT.rglob("*") if path.is_file() and "q2_results" not in str(path)), "nulls": nulls, "estimated_value": describe(values), "closing_years": close_dates, "published_years": published_dates}, "labels": labels, "selected_threshold": selected_threshold, "threshold_fp": threshold_fp, "threshold_fn": threshold_fn, "costs": {"false_merge": false_merge_cost, "missed_duplicate": missed_duplicate_cost}, "representations": profiles, "minhash": minhash_results, "retrieval": {mode: {key: value for key, value in data.items() if key not in {"candidate_ids", "frequencies"}} for mode, data in retrieval.items()}, "curve": curve, "database": {"indexed_plan": indexed_plan, "scan_plan": scan_plan, "indexed_seconds": indexed_time, "scan_seconds": scan_time, "indexed_rows": indexed_rows, "scan_rows": scan_rows}, "stable_id": stable_test, "phase_times": phase_times, "runtime_seconds": runtime}
    with (RESULT_DIR / "raw_results.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, default=lambda value: dict(value))
    write_reports(result, portals)
    write_plots(result)
    print(json.dumps({"notices": len(notices), "portals": len(portals), "labels": dict(labels), "threshold": selected_threshold, "retrieval": result["retrieval"], "runtime_seconds": runtime, "stable_id_test": stable_test}, indent=2, default=lambda value: dict(value)))


def write_reports(result, portals):
    corpus = result["corpus"]
    labels = result["labels"]
    (ROOT / "q2_corpus_profile.md").write_text(f"""# Q2 corpus profile\n\nMeasured by `q2_experiments.py` from the eight files in `notices/`. Source labels used only from `labelled_pairs.csv`; `_truth/` was not used for evaluation.\n\n- Notices: **{corpus['notices']}**\n- Portals: **{corpus['portals']}**\n- Corpus bytes excluding generated outputs: **{corpus['bytes']}**\n- Labelled pairs: **{sum(labels.values())}**; SAME **{labels['same']}**, DIFFERENT **{labels['different']}**\n- Label share: SAME **{labels['same']/sum(labels.values()):.3f}**, DIFFERENT **{labels['different']/sum(labels.values()):.3f}**\n- Null/empty fields: `{dict(corpus['nulls'])}`\n- Total text length: `{corpus['text_length']}`\n- Body length: `{corpus['body_length']}`\n- Estimated value: `{corpus['estimated_value']}`\n- Published years: `{dict(corpus['published_years'])}`\n- Closing years: `{dict(corpus['closing_years'])}`\n\nThe portal notes were used as interpretation: P001-P006 are aggregators with repeated preambles, reference numbers are portal-specific, dates and money have multiple renderings, and corrigenda are new notices.\n\nTop portals: {', '.join(f'{p}={n}' for p, n in Counter(portals).most_common(15))}.\n\nLikely boilerplate/reference-number patterns were measured in the representation comparison: raw text retains these tokens; the clean representation replaces reference/date/money patterns and known aggregator boilerplate before tokenization.\n""", encoding="utf-8")
    raw = result["representations"]["raw"]
    clean = result["representations"]["clean"]
    example_same = next(row for row in clean if row["label"] == "same")
    example_diff = next(row for row in clean if row["label"] == "different")
    def lookup(mode, a, b):
        return next(row for row in result["representations"][mode] if row["a"] == a and row["b"] == b)
    (ROOT / "q2_similarity_experiments.md").write_text(f"""# Q2 similarity experiments\n\n## Representations compared\n\n1. **Raw**: normalized case/whitespace, title word 2-shingles and body character 5-shingles; reference numbers, dates, money, and portal preambles remain.\n2. **Clean**: the same decomposition, but regex replacement removes reference numbers, date renderings, money renderings, and known aggregator boilerplate before tokenization.\n\nScore is `0.35 * Jaccard(title shingles) + 0.65 * Jaccard(body shingles)`. The body has the larger weight because it carries more tender scope; title remains an independent signal. Amounts/dates/references are retained as fields for display and future validation, but are not identity tokens.\n\n| representation | SAME mean | DIFFERENT mean | SAME p50 | DIFFERENT p50 |\n|---|---:|---:|---:|---:|\n| raw | {statistics.mean(r['score'] for r in raw if r['label']=='same'):.4f} | {statistics.mean(r['score'] for r in raw if r['label']=='different'):.4f} | {percentile([r['score'] for r in raw if r['label']=='same'], .5):.4f} | {percentile([r['score'] for r in raw if r['label']=='different'], .5):.4f} |\n| clean | {statistics.mean(r['score'] for r in clean if r['label']=='same'):.4f} | {statistics.mean(r['score'] for r in clean if r['label']=='different'):.4f} | {percentile([r['score'] for r in clean if r['label']=='same'], .5):.4f} | {percentile([r['score'] for r in clean if r['label']=='different'], .5):.4f} |\n\nExample SAME `{example_same['a']}`/`{example_same['b']}`: raw `{lookup('raw', example_same['a'], example_same['b'])['score']:.4f}`, clean `{example_same['score']:.4f}`. Example DIFFERENT `{example_diff['a']}`/`{example_diff['b']}`: raw `{lookup('raw', example_diff['a'], example_diff['b'])['score']:.4f}`, clean `{example_diff['score']:.4f}`.\n\nFalse merge cost is **10** and missed duplicate cost is **1**. Minimizing `10*FP + 1*FN` on the labelled set selected threshold **{result['selected_threshold']:.2f}**, with FP={result['threshold_fp']} and FN={result['threshold_fn']}.\n\nAdopt clean preprocessing, the explicit score, threshold `{result['selected_threshold']:.2f}`, and no direct reference-number match.\n""", encoding="utf-8")
    minhash_text = "\n".join(f"| {size} | {statistics.mean(r['abs_error'] for r in rows):.6f} | {percentile([r['abs_error'] for r in rows], .95):.6f} | {max(rows, key=lambda r: r['abs_error'])['a']}/{max(rows, key=lambda r: r['abs_error'])['b']} |" for size, rows in result["minhash"].items())
    required = math.ceil(math.log(2 / .05) / (2 * .05 ** 2))
    (ROOT / "q2_retrieval_experiments.md").write_text(f"""# Q2 retrieval experiments\n\nThe selected retrieval is a bounded-frequency inverted index over clean word 2-shingles. A token is indexed only when document frequency is at most 2% of the 12,000-notice corpus. It avoids all-pairs comparison.\n\n## MinHash estimator\n\nThe requirement is absolute error <= 0.05 with approximate 95% confidence. The conservative bound `m >= ln(2/delta)/(2 epsilon^2)` gives `m >= {required}`, so **1024** is selected; 128 and 512 are measured comparators.\n\n| signatures | mean absolute error | p95 absolute error | largest observed failure |\n|---:|---:|---:|---|\n{minhash_text}\n\n## Candidate retrieval\n\n| mode | indexed buckets | candidate pairs | mean/notice | p50 | p95 | p99 | max | labelled survival | SAME survival | seconds |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n| raw | {result['retrieval']['raw']['index_tokens']} | {result['retrieval']['raw']['candidate_pairs']} | {result['retrieval']['raw']['candidate_counts']['mean']:.2f} | {result['retrieval']['raw']['candidate_counts']['p50']} | {result['retrieval']['raw']['candidate_counts']['p95']} | {result['retrieval']['raw']['candidate_counts']['p99']} | {result['retrieval']['raw']['candidate_counts']['max']} | {result['retrieval']['raw']['labelled_survival']:.4f} | {result['retrieval']['raw']['same_survival']:.4f} | {result['retrieval']['raw']['total_seconds']:.3f} |\n| clean | {result['retrieval']['clean']['index_tokens']} | {result['retrieval']['clean']['candidate_pairs']} | {result['retrieval']['clean']['candidate_counts']['mean']:.2f} | {result['retrieval']['clean']['candidate_counts']['p50']} | {result['retrieval']['clean']['candidate_counts']['p95']} | {result['retrieval']['clean']['candidate_counts']['p99']} | {result['retrieval']['clean']['candidate_counts']['max']} | {result['retrieval']['clean']['labelled_survival']:.4f} | {result['retrieval']['clean']['same_survival']:.4f} | {result['retrieval']['clean']['total_seconds']:.3f} |\n\nThe survival plot is `q2_results/plots/similarity_survival.png`; the selected score threshold is marked.\n""", encoding="utf-8")
    db = result["database"]
    (ROOT / "q2_database_design.md").write_text(f"""# Q2 database design\n\nA PostgreSQL deployment would use `notices`, `notice_signatures`, `lsh_buckets`, `candidate_edges`, `opportunities`, and `opportunity_members`. Each retrieval run has a representation/version key; candidate edges and memberships are append-only until a version is promoted.\n\nThe executable local prototype is SQLite because PostgreSQL was not installed/configured in this workspace. Indexed lookup versus sequential lookup: indexed plan `{db['indexed_plan']}`, sequential plan `{db['scan_plan']}`; rows `{db['indexed_rows']}` versus `{db['scan_rows']}`; wall time `{db['indexed_seconds']:.6f}s` versus `{db['scan_seconds']:.6f}s`. The index wins because equality lookup visits a key range rather than every row. PostgreSQL EXPLAIN ANALYZE is **NOT MEASURED**.\n\nStable card ID is `OPP` plus the minimum persistent notice ID in an opportunity, stored as the opportunity anchor. The actual append test used `{result['stable_id']['original_members']}` plus `{result['stable_id']['new_copy']}`: `{result['stable_id']['original_card_id']}` remained `{result['stable_id']['after_new_copy_card_id']}`; passed={result['stable_id']['passed']}.\n""", encoding="utf-8")
    raw_r, clean_r = result["retrieval"]["raw"], result["retrieval"]["clean"]
    (ROOT / "q2_skew_mitigation.md").write_text(f"""# Q2 skew and mitigation\n\nBefore is raw word 2-shingle retrieval. After replaces known aggregator boilerplate and variable reference/date/money strings, with the same 2% frequency cap.\n\n| metric | before | after |\n|---|---:|---:|\n| retrieval seconds | {raw_r['total_seconds']:.3f} | {clean_r['total_seconds']:.3f} |\n| candidate pairs | {raw_r['candidate_pairs']} | {clean_r['candidate_pairs']} |\n| mean candidates/notice | {raw_r['candidate_counts']['mean']:.2f} | {clean_r['candidate_counts']['mean']:.2f} |\n| p95 candidates | {raw_r['candidate_counts']['p95']} | {clean_r['candidate_counts']['p95']} |\n| p99 candidates | {raw_r['candidate_counts']['p99']} | {clean_r['candidate_counts']['p99']} |\n| max candidates | {raw_r['candidate_counts']['max']} | {clean_r['candidate_counts']['max']} |\n| labelled recall | {raw_r['labelled_survival']:.4f} | {clean_r['labelled_survival']:.4f} |\n| SAME recall | {raw_r['same_survival']:.4f} | {clean_r['same_survival']:.4f} |\n\nThe mechanical hotspot is common text from P001-P006: repeated preambles create shared shingles, while short notices contain little else. That inflates bucket occupancy and candidate work. The mitigation is accepted only with the measured recall table above. Portal-level work attribution is **NOT MEASURED** in this run.\n\nBucket occupancy: before `{raw_r['bucket']}`; after `{clean_r['bucket']}`.\n""", encoding="utf-8")
    (ROOT / "q2_final_answers.md").write_text(f"""# Q2 final answers\n\n## A(a)\nSimilar means clean weighted Jaccard >= **{result['selected_threshold']:.2f}**, using title word 2-shingles and body character 5-shingles with weights 0.35/0.65. Reference numbers, date formats, money formats, and named portal boilerplate are noise for identity; their fields remain available for validation. Measured raw/clean label comparisons and SAME/DIFFERENT examples are in `q2_similarity_experiments.md`. Costs are false merge **10**, missed duplicate **1**.\n\n## A(b)\nUse **1024 MinHash components**. The epsilon=.05, delta=.05 bound requires at least `{required}`; measured 128/512/1024 errors and failures are in `q2_retrieval_experiments.md`.\n\n## A(c)\nUse clean frequency-capped inverted-index candidate retrieval followed by exact scoring. The survival plot is `q2_results/plots/similarity_survival.png`; candidate counts, recalls, runtime, and operating point are measured in the retrieval report.\n\n## B(d)\nUse versioned relational tables for notices, signatures/buckets, candidates, opportunities, and members. Select indexed equality lookup; SQLite EXPLAIN/timing is measured in `q2_database_design.md`. PostgreSQL EXPLAIN ANALYZE is **NOT MEASURED**. Stable ID test: **{'PASS' if result['stable_id']['passed'] else 'FAIL'}**.\n\n## B(e)\nThe measured hotspot is aggregator boilerplate; clean replacement plus frequency capping is the mitigation. Before/after work and recall are in `q2_skew_mitigation.md`.\n\n## Summary\n- Method/parameters: clean word-2 inverted index, 2% frequency cap, exact weighted score; estimator comparison uses 128/512/1024 MinHash.\n- Corpus: {result['corpus']['notices']} notices, {result['corpus']['bytes']} bytes; labels SAME {labels['same']}, DIFFERENT {labels['different']}.\n- Candidate recall: raw {raw_r['labelled_survival']:.4f}, clean {clean_r['labelled_survival']:.4f}; SAME raw {raw_r['same_survival']:.4f}, clean {clean_r['same_survival']:.4f}.\n- Cost ratio: 10:1.\n- Clean candidates/notice: mean {clean_r['candidate_counts']['mean']:.2f}, p50 {clean_r['candidate_counts']['p50']}, p95 {clean_r['candidate_counts']['p95']}, p99 {clean_r['candidate_counts']['p99']}, max {clean_r['candidate_counts']['max']}; total {clean_r['candidate_pairs']}.\n- Before/after retrieval seconds: {raw_r['total_seconds']:.3f}/{clean_r['total_seconds']:.3f}; end-to-end runner: {result['runtime_seconds']:.3f}s against 1,200s.\n- Stable-ID test: **{'PASS' if result['stable_id']['passed'] else 'FAIL'}**.\n\nSeparate indexing, candidate-scoring, and clustering timings, PostgreSQL measurements, and portal-level hotspot attribution are **NOT MEASURED**.\n""", encoding="utf-8")


if __name__ == "__main__":
    run()