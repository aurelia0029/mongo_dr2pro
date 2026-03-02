from pymongo import MongoClient
import utils

def run_audit():
    logger = utils.setup_logger("Phase2")
    try:
        full_cfg = utils.load_config()
        cfg, schema = full_cfg["job_config"], full_cfg["data_schema"]
        db = MongoClient(cfg["dr_uri"])[cfg["dr_db"]]
        query = utils.get_query(cfg)
        t_map = {"int": int, "str": str, "bytes": bytes}

        for coll_name in utils.get_target_collections(cfg):
            logger.info(f"正在審計 DR 數據區間: {coll_name}")
            cursor = db[coll_name].find(query).limit(1000)
            passed, total = 0, 0
            for doc in cursor:
                total += 1
                is_ok = all(f in doc and isinstance(doc[f], t_map[schema["type_rules"].get(f, "str")]) 
                            for f in schema["required_fields"])
                if is_ok: passed += 1
            logger.info(f"結果: {coll_name} 抽檢 {total} 筆, 通過率: {(passed/total*100 if total>0 else 0):.2f}%")
        return True
    except Exception as e:
        logger.error(f"Phase 2 失敗: {e}")
        return False

if __name__ == "__main__":
    run_audit()

