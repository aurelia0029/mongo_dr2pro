import utils
from pymongo import MongoClient

runtime_cfg = utils.get_runtime_cfg()
required_fields = runtime_cfg["data_schema"]["required_fields"]

def check(uri, db_name, label):
    db = MongoClient(uri)[db_name]
    print(f"\n=== {label} ({db_name}) ===")
    colls = [c for c in db.list_collection_names() if runtime_cfg["coll_prefix"] in c]
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

check(runtime_cfg["prod_uri"], runtime_cfg["prod_db"], "Production")
check(runtime_cfg["dr_uri"],   runtime_cfg["dr_db"],   "DR Site")
