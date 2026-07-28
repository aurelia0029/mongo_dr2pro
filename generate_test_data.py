import datetime, random
from pymongo import MongoClient
import utils

def generate_test_data(runtime_cfg=None):
    if runtime_cfg is None:
        runtime_cfg = utils.get_runtime_cfg()

    required_fields = runtime_cfg["data_schema"]["required_fields"]
    type_rules      = runtime_cfg["data_schema"]["type_rules"]
    time_field      = runtime_cfg["time_field"]

    p_db = MongoClient(runtime_cfg["prod_uri"])[runtime_cfg["prod_db"]]
    d_db = MongoClient(runtime_cfg["dr_uri"])[runtime_cfg["dr_db"]]

    def make_doc(ts, status):
        doc = {f: (random.randint(0, 999_999_999) if type_rules.get(f) == "int" else str(random.randint(10000, 9_999_999))) for f in required_fields}
        doc[time_field] = ts
        doc["status"] = status
        return doc

    start = datetime.datetime.strptime(runtime_cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(runtime_cfg["end_ts"],   "%Y%m%d%H")
    curr = start
    while curr <= end:
        coll_name = f"{curr.strftime('%Y%m%d%H')}_{runtime_cfg['coll_prefix']}"
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
