import datetime, json, logging, os, random
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger("TestGenerator")

def _make_value(field_type):
    if field_type == "int":
        return random.randint(0, 999_999_999)
    return str(random.randint(10000, 9_999_999))

def _build_doc(required_fields, type_rules, time_field, doc_ts, status):
    doc = {f: _make_value(type_rules.get(f, "str")) for f in required_fields}
    doc[time_field] = doc_ts
    doc["status"] = status
    return doc

def generate_test_data():
    config_path = "schema_check.json"
    if not os.path.exists(config_path):
        logger.error(f"找不到 {config_path}")
        return

    with open(config_path) as f:
        full_cfg = json.load(f)
    cfg = full_cfg["job_config"]
    required_fields = full_cfg["data_schema"]["required_fields"]
    type_rules = full_cfg["data_schema"]["type_rules"]
    time_field = cfg["time_field"]

    p_db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]
    d_db = MongoClient(cfg["dr_uri"])[cfg["dr_db"]]

    start = datetime.datetime.strptime(cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(cfg["end_ts"],   "%Y%m%d%H")

    logger.info(f"=== 測試資料產生器啟動 ===")
    logger.info(f"區間: {cfg['start_ts']} → {cfg['end_ts']} (含)")

    curr = start
    while curr <= end:
        coll_name = f"{curr.strftime('%Y%m%d%H')}_{cfg['coll_prefix']}"
        hour_start_ms = int(curr.timestamp() * 1000)
        step = 36_000  # 3,600,000ms / 100 筆

        p_db[coll_name].drop()
        d_db[coll_name].drop()

        dr_docs   = [_build_doc(required_fields, type_rules, time_field, hour_start_ms + i * step, "VALID_DR_DATA") for i in range(100)]
        prod_docs = [_build_doc(required_fields, type_rules, time_field, hour_start_ms + i * step, "CORRUPTED")     for i in range(50)]

        d_db[coll_name].insert_many(dr_docs)
        d_db[coll_name].create_index([(time_field, 1)])
        p_db[coll_name].insert_many(prod_docs)
        p_db[coll_name].create_index([(time_field, 1)])

        logger.info(f"{coll_name}: DR(100筆), Prod(50筆 CORRUPTED)")
        curr += datetime.timedelta(hours=1)

    logger.info("✅ 所有測試資料建置完成。")

if __name__ == "__main__":
    generate_test_data()
