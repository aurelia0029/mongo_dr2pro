import datetime, json, random
from pymongo import MongoClient

def generate_test_data():
    with open("schema_check.json") as f:
        full_cfg = json.load(f)
    cfg = full_cfg["job_config"]
    required_fields = full_cfg["data_schema"]["required_fields"]
    type_rules = full_cfg["data_schema"]["type_rules"]
    time_field = cfg["time_field"]

    p_db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]
    d_db = MongoClient(cfg["dr_uri"])[cfg["dr_db"]]

    def make_doc(ts, status):
        doc = {f: (random.randint(0, 999_999_999) if type_rules.get(f) == "int" else str(random.randint(10000, 9_999_999))) for f in required_fields}
        doc[time_field] = ts
        doc["status"] = status
        return doc

    start = datetime.datetime.strptime(cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(cfg["end_ts"],   "%Y%m%d%H")
    curr = start
    while curr <= end:
        coll_name = f"{curr.strftime('%Y%m%d%H')}_{cfg['coll_prefix']}"
        hour_start_ms = int(curr.timestamp() * 1000)
        p_db[coll_name].drop()
        d_db[coll_name].drop()
        d_db[coll_name].insert_many([make_doc(hour_start_ms + i * 36_000, "VALID_DR_DATA") for i in range(100)])
        p_db[coll_name].insert_many([make_doc(hour_start_ms + i * 36_000, "CORRUPTED")     for i in range(50)])
        print(f"{coll_name}: DR(100筆), Prod(50筆)")
        curr += datetime.timedelta(hours=1)

    print("✅ 測試環境就緒。")

if __name__ == "__main__":
    generate_test_data()
