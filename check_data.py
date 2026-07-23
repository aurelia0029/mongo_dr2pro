import json
from pymongo import MongoClient

with open("schema_check.json", "r") as f:
    full_cfg = json.load(f)

cfg = full_cfg["job_config"]
required_fields = full_cfg["data_schema"]["required_fields"]

def check(uri, db_name, label):
    db = MongoClient(uri)[db_name]
    print(f"\n=== {label} ({db_name}) ===")
    colls = [c for c in db.list_collection_names() if cfg["coll_prefix"] in c]
    for c in sorted(colls):
        count = db[c].count_documents({})
        sample = db[c].find_one()
        if sample:
            types = {f: type(sample[f]).__name__ for f in required_fields if f in sample}
            missing = [f for f in required_fields if f not in sample]
            print(f"集合: {c} | 筆數: {count} | 型別: {types}")
            if missing:
                print(f"  ⚠ 缺少欄位: {missing}")
        else:
            print(f"集合: {c} | 筆數: {count} | (空集合)")

check(cfg["prod_uri"], cfg["prod_db"], "Production")
check(cfg["dr_uri"], cfg["dr_db"], "DR Site")
