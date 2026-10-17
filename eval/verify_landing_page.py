import json
import re
from pathlib import Path

html = Path("docs/index.html").read_text(encoding="utf-8")

# Extract all embedded script data-file blocks
pattern = re.compile(r'<script type="application/json" data-file="([^"]+)">(.*?)</script>', re.DOTALL)
embedded = {m.group(1): json.loads(m.group(2)) for m in pattern.finditer(html)}

print("=== 1. SOURCE FILES vs EMBEDDED IN DOCS/INDEX.HTML ===")

# 1. ablation_memory.json
am_source = json.loads(Path("eval/results/ablation_memory.json").read_text("utf-8"))
am_embed = embedded.get("ablation_memory.json", {})

print("\n--- ablation_memory.json ---")
val_src_caught = am_source["arms"]["full"]["summary"]["caught"]
val_src_n = am_source["arms"]["full"]["summary"]["n"]
val_emb_caught = am_embed.get("arms", {}).get("full", {}).get("summary", {}).get("caught")
val_emb_n = am_embed.get("arms", {}).get("full", {}).get("summary", {}).get("n")
print(f"Full memory caught: source={val_src_caught}/{val_src_n}, embedded={val_emb_caught}/{val_emb_n}")

val_src_f30_caught = am_source["arms"]["forget_30"]["summary"]["caught"]
val_src_f30_n = am_source["arms"]["forget_30"]["summary"]["n"]
val_emb_f30_caught = am_embed.get("arms", {}).get("forget_30", {}).get("summary", {}).get("caught")
val_emb_f30_n = am_embed.get("arms", {}).get("forget_30", {}).get("summary", {}).get("n")
print(f"Memory cut to 30 days caught: source={val_src_f30_caught}/{val_src_f30_n}, embedded={val_emb_f30_caught}/{val_emb_f30_n}")

val_src_full_flag = am_source["arms"]["full"]["clean"]["flagged"]
val_src_full_cleann = am_source["arms"]["full"]["clean"]["n"]
val_emb_full_flag = am_embed.get("arms", {}).get("full", {}).get("clean", {}).get("flagged")
val_emb_full_cleann = am_embed.get("arms", {}).get("full", {}).get("clean", {}).get("n")
print(f"False alarms, full memory: source={val_src_full_flag}/{val_src_full_cleann}, embedded={val_emb_full_flag}/{val_emb_full_cleann}")

val_src_f30_flag = am_source["arms"]["forget_30"]["clean"]["flagged"]
val_src_f30_cleann = am_source["arms"]["forget_30"]["clean"]["n"]
val_emb_f30_flag = am_embed.get("arms", {}).get("forget_30", {}).get("clean", {}).get("flagged")
val_emb_f30_cleann = am_embed.get("arms", {}).get("forget_30", {}).get("clean", {}).get("n")
print(f"False alarms, 30-day memory: source={val_src_f30_flag}/{val_src_f30_cleann}, embedded={val_emb_f30_flag}/{val_emb_f30_cleann}")

# 2. ecosystem_gaps.json
eg_source = json.loads(Path("eval/results/ecosystem_gaps.json").read_text("utf-8"))
eg_embed = embedded.get("ecosystem_gaps.json", {})

print("\n--- ecosystem_gaps.json ---")
val_src_gap_rows = eg_source.get("gap_rows")
val_emb_gap_rows = eg_embed.get("gap_rows")
val_src_dec_comp = eg_source.get("decisions_computed")
val_emb_dec_comp = eg_embed.get("decisions_computed")
print(f"Visibility gaps (gap_rows): source={val_src_gap_rows}, embedded={val_emb_gap_rows}")
print(f"Decisions computed: source={val_src_dec_comp}, embedded={val_emb_dec_comp}")

# 3. xz_replay.json & pressure_vouch_status.json
xr_source = json.loads(Path("eval/results/xz_replay.json").read_text("utf-8"))
xr_embed = embedded.get("xz_replay.json", {})
print("\n--- xz_replay.json ---")
print(f"Messages read (read_so_far): source={xr_source['reader_coverage']['read_so_far']}, embedded={xr_embed['reader_coverage']['read_so_far']}")
print(f"To read: source={xr_source['reader_coverage']['to_read']}, embedded={xr_embed['reader_coverage']['to_read']}")
print(f"Excluded: source={xr_source['reader_coverage']['excluded_human_labelled_test_set']}, embedded={xr_embed['reader_coverage']['excluded_human_labelled_test_set']}")

pv_source = json.loads(Path("eval/results/pressure_vouch_status.json").read_text("utf-8"))
pv_embed = embedded.get("pressure_vouch_status.json", {})
pv_src_win_read = sum(q["window_coverage"]["pressure"]["read"] for q in pv_source["quarters"])
pv_src_win_tot = sum(q["window_coverage"]["pressure"]["messages_in_window"] for q in pv_source["quarters"])
pv_emb_win_read = sum(q["window_coverage"]["pressure"]["read"] for q in pv_embed.get("quarters", []))
pv_emb_win_tot = sum(q["window_coverage"]["pressure"]["messages_in_window"] for q in pv_embed.get("quarters", []))
print("\n--- pressure_vouch_status.json ---")
print(f"Pressure window messages read: source={pv_src_win_read}/{pv_src_win_tot}, embedded={pv_emb_win_read}/{pv_emb_win_tot}")

# 4. Footer commit
m_commit = re.search(r'const COMMIT = "([^"]+)";', html)
print(f"\n--- Footer Commit ---")
print(f"Embedded COMMIT: {m_commit.group(1) if m_commit else 'NOT FOUND'}")
