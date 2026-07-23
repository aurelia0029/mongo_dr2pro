#!/usr/bin/env python3
"""
validate_scenarios.py

端到端驗證四種時間邊界情境的 DR 修復流程正確性：
  1. 同日跨 collection
  2. 跨日
  3. 跨 00:00
  4. 跨年
"""
import json, os, sys
from pymongo import MongoClient

import generate_test_data_pro
import phase1_evacuation, phase2_data_integrity_audit, phase3_restore
import utils

CONFIG_PATH = "schema_check.json"
GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

SCENARIOS = [
    {
        "id": 1,
        "name": "同日跨 collection",
        "desc": "2026-03-10 02:00 → 05:00",
        "start_ts": "2026031002",
        "end_ts":   "2026031005",
        "expected_colls": 4,
        "expected_colls_list": [
            "2026031002_encColl", "2026031003_encColl",
            "2026031004_encColl", "2026031005_encColl",
        ],
    },
    {
        "id": 2,
        "name": "跨日",
        "desc": "2026-03-10 20:00 → 2026-03-11 03:00",
        "start_ts": "2026031020",
        "end_ts":   "2026031103",
        "expected_colls": 8,
        "expected_colls_list": [
            "2026031020_encColl", "2026031021_encColl",
            "2026031022_encColl", "2026031023_encColl",
            "2026031100_encColl", "2026031101_encColl",
            "2026031102_encColl", "2026031103_encColl",
        ],
    },
    {
        "id": 3,
        "name": "跨 00:00",
        "desc": "2026-03-10 23:00 → 2026-03-11 00:00",
        "start_ts": "2026031023",
        "end_ts":   "2026031100",
        "expected_colls": 2,
        "expected_colls_list": [
            "2026031023_encColl",
            "2026031100_encColl",
        ],
    },
    {
        "id": 4,
        "name": "跨年",
        "desc": "2025-12-31 22:00 → 2026-01-01 01:00",
        "start_ts": "2025123122",
        "end_ts":   "2026010101",
        "expected_colls": 4,
        "expected_colls_list": [
            "2025123122_encColl", "2025123123_encColl",
            "2026010100_encColl", "2026010101_encColl",
        ],
    },
]

# ─────────────────────────────────────────────
def write_config(base_cfg, start_ts, end_ts):
    cfg = json.loads(json.dumps(base_cfg))
    cfg["job_config"]["start_ts"] = start_ts
    cfg["job_config"]["end_ts"]   = end_ts
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

def restore_config(base_cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(base_cfg, f, indent=2)

def ok_str(b):
    return f"{GREEN}OK{RESET}" if b else f"{RED}FAIL{RESET}"

def _bak_exists(prod_db, coll_name):
    bak_root = "backups"
    if not os.path.isdir(bak_root):
        return False
    return any(
        os.path.exists(os.path.join(bak_root, d, prod_db, f"{coll_name}.bson"))
        for d in os.listdir(bak_root) if d.startswith("bak_")
    )

# ─────────────────────────────────────────────
def verify(job_cfg, scenario):
    p_db = MongoClient(job_cfg["prod_uri"])[job_cfg["prod_db"]]
    prefixes = utils.get_hour_prefixes(job_cfg)
    actual_colls = utils.get_matching_collections(p_db, prefixes)

    coll_count_ok = len(actual_colls) == scenario["expected_colls"]
    coll_names_ok = actual_colls == scenario["expected_colls_list"]

    rows, all_ok = [], coll_count_ok and coll_names_ok

    for coll in actual_colls:
        prod_cnt    = p_db[coll].count_documents({})
        corrupt_cnt = p_db[coll].count_documents({"status": "CORRUPTED"})
        valid_cnt   = p_db[coll].count_documents({"status": "VALID_DR_DATA"})
        bak_created = _bak_exists(job_cfg["prod_db"], coll)

        row_ok = (prod_cnt == 100 and corrupt_cnt == 0
                  and valid_cnt == 100 and bak_created)
        if not row_ok:
            all_ok = False

        rows.append({
            "coll": coll, "prod": prod_cnt, "corrupt": corrupt_cnt,
            "valid": valid_cnt, "bak": bak_created, "ok": row_ok,
        })

    return all_ok, coll_count_ok, coll_names_ok, actual_colls, rows

# ─────────────────────────────────────────────
def run_scenario(base_cfg, scenario):
    SEP = "=" * 65
    print(f"\n{SEP}")
    print(f"Scenario {scenario['id']}: {scenario['name']}  ({scenario['desc']})")
    print(SEP)

    write_config(base_cfg, scenario["start_ts"], scenario["end_ts"])

    job_cfg = json.loads(json.dumps(base_cfg["job_config"]))
    job_cfg["start_ts"] = scenario["start_ts"]
    job_cfg["end_ts"]   = scenario["end_ts"]

    print("\n[Setup] 產生測試資料...")
    generate_test_data_pro.generate_test_data()

    phase_results = {}
    for label, func in [
        ("Phase1 備份 Prod",   phase1_evacuation.run_evacuation),
        ("Phase2 審計 DR",     phase2_data_integrity_audit.run_audit),
        ("Phase3 還原至 Prod", phase3_restore.run_restore),
    ]:
        print(f"\n[{label}] 執行中...")
        phase_results[label] = func()

    phases_ok = all(phase_results.values())

    all_ok, coll_count_ok, coll_names_ok, actual_colls, rows = verify(job_cfg, scenario)

    print(f"\n{'─'*65}")
    print(f"集合數量 : 預期 {scenario['expected_colls']}，實際 {len(actual_colls)} → {ok_str(coll_count_ok)}")
    print(f"集合名稱 : {ok_str(coll_names_ok)}")
    if not coll_names_ok:
        print(f"  預期: {scenario['expected_colls_list']}")
        print(f"  實際: {actual_colls}")

    hdr = f"  {'集合名稱':<28} {'prod':>5} {'corrupt':>7} {'valid_dr':>8} {'bak':>4}  結果"
    print(f"\n{hdr}")
    print("  " + "─" * 57)
    for r in rows:
        bak_str = "Y" if r["bak"] else f"{RED}N{RESET}"
        print(f"  {r['coll']:<28} {r['prod']:>5} {r['corrupt']:>7} {r['valid']:>8}"
              f"  {bak_str:>4}  {ok_str(r['ok'])}")

    overall = phases_ok and all_ok
    verdict = f"{GREEN}PASS{RESET}" if overall else f"{RED}FAIL{RESET}"
    print(f"\n>>> Scenario {scenario['id']} {verdict} <<<")
    return overall

# ─────────────────────────────────────────────
def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: 找不到 {CONFIG_PATH}，請先從 schema_check.json.example 建立設定檔。")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        base_cfg = json.load(f)

    results = []
    try:
        for scenario in SCENARIOS:
            ok = run_scenario(base_cfg, scenario)
            results.append((scenario["id"], scenario["name"], ok))
    finally:
        restore_config(base_cfg)

    print(f"\n{'='*65}")
    print("最終摘要")
    print("─" * 65)
    for sid, name, ok in results:
        verdict = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {verdict}  Scenario {sid}: {name}")

    all_pass = all(ok for _, _, ok in results)
    print(f"\n整體結果: {'全部通過 ✓' if all_pass else '有情境失敗，請檢查上方輸出'}")
    sys.exit(0 if all_pass else 1)

if __name__ == "__main__":
    main()
