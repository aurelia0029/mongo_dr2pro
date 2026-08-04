import datetime, logging, random
from pymongo import MongoClient
import utils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger("TestGenerator")

def _make_value(field_type):
    if field_type == "int":
        return random.randint(0, 999_999_999)
    return str(random.randint(10000, 9_999_999))

def _build_doc(required_fields, type_rules, time_field, doc_ts):
    doc = {f: _make_value(type_rules.get(f, "str")) for f in required_fields}
    doc[time_field] = doc_ts
    return doc

def _prompt_test_time_range(cfg):
    """年份限制 ≤ 2025 的時間範圍輸入，僅供測試腳本使用。"""
    while True:
        print()
        start_ts = input("起始小時 (YYYYMMDDHH，含): ").strip()
        end_ts   = input("結束小時 (YYYYMMDDHH，含): ").strip()
        try:
            start_dt = datetime.datetime.strptime(start_ts, "%Y%m%d%H")
            end_dt   = datetime.datetime.strptime(end_ts,   "%Y%m%d%H")
        except ValueError:
            print("格式錯誤，請輸入 YYYYMMDDHH（例如：2025071808）")
            continue
        if start_dt.year > 2025 or end_dt.year > 2025:
            print("測試資料年份限制在 2025 以前，請重新輸入。")
            continue
        if end_dt < start_dt:
            print("結束時間不能早於起始時間")
            continue
        temp_cfg = {**cfg, "start_ts": start_ts, "end_ts": end_ts}
        prefixes = utils.get_hour_prefixes(temp_cfg)
        print(f"\n將處理以下 {len(prefixes)} 個小時的集合：")
        for p in prefixes:
            print(f"  {p}*")
        confirm = input("\n確認範圍？(y/n): ").strip().lower()
        if confirm == 'y':
            return temp_cfg
        print("重新輸入時間範圍。")

def generate_test_data(runtime_cfg):
    required_fields = runtime_cfg["data_schema"]["required_fields"]
    type_rules      = runtime_cfg["data_schema"]["type_rules"]
    time_field      = runtime_cfg["time_field"]

    p_db = MongoClient(runtime_cfg["prod_uri"])[runtime_cfg["prod_db"]]
    d_db = MongoClient(runtime_cfg["dr_uri"])[runtime_cfg["dr_db"]]

    start = datetime.datetime.strptime(runtime_cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(runtime_cfg["end_ts"],   "%Y%m%d%H")

    logger.info("=== 測試資料產生器啟動 ===")
    logger.info(f"區間: {runtime_cfg['start_ts']} → {runtime_cfg['end_ts']} (含)")

    prod_existing = set(p_db.list_collection_names())
    dr_existing   = set(d_db.list_collection_names())

    curr = start
    while curr <= end:
        coll_name = f"{curr.strftime('%Y%m%d%H')}_{runtime_cfg['coll_prefix']}"
        hour_start_ms = int(curr.timestamp() * 1000)
        step = 36_000

        prod_cnt = p_db[coll_name].count_documents({}) if coll_name in prod_existing else 0
        dr_cnt   = d_db[coll_name].count_documents({}) if coll_name in dr_existing   else 0
        if prod_cnt > 0 or dr_cnt > 0:
            logger.info(f"{coll_name}: 發現現有資料（Prod={prod_cnt} 筆, DR={dr_cnt} 筆），自動清除")

        p_db[coll_name].drop()
        d_db[coll_name].drop()

        dr_docs   = [_build_doc(required_fields, type_rules, time_field, hour_start_ms + i * step) for i in range(100)]
        prod_docs = [_build_doc(required_fields, type_rules, time_field, hour_start_ms + i * step) for i in range(50)]

        d_db[coll_name].insert_many(dr_docs)
        d_db[coll_name].create_index([(time_field, 1)])
        p_db[coll_name].insert_many(prod_docs)
        p_db[coll_name].create_index([(time_field, 1)])

        logger.info(f"{coll_name}: DR(100 筆), Prod(50 筆)")
        curr += datetime.timedelta(hours=1)

    logger.info("✅ 所有測試資料建置完成。")

if __name__ == "__main__":
    full_cfg = utils.load_config()
    base_cfg = full_cfg["job_config"]
    direction = utils.prompt_direction(base_cfg)
    cfg = utils.prompt_credentials_and_connect(base_cfg, direction)
    cfg = _prompt_test_time_range(cfg)
    cfg["data_schema"] = full_cfg["data_schema"]
    generate_test_data(cfg)
