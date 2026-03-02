import json
from pymongo import MongoClient

with open("schema_check.json", "r") as f:
    cfg = json.load(f)["job_config"]

def check(uri, db_name, label):
    client = MongoClient(uri)
    db = client[db_name]
    print(f"\n=== {label} ({db_name}) ===")
    
    # 根據前綴找出所有相關集合
    colls = [c for c in db.list_collection_names() if cfg['coll_prefix'] in c]
    for c in sorted(colls):
        count = db[c].count_documents({})
        sample = db[c].find_one()
        shk_type = type(sample['shk']).__name__ if sample and 'shk' in sample else "N/A"
        print(f"集合: {c} | 筆數: {count} | shk型別: {shk_type}")

check(cfg["prod_uri"], cfg["prod_db"], "Production")
check(cfg["dr_uri"], cfg["dr_db"], "DR Site")
