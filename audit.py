from pymongo import MongoClient
import utils

def run_audit(runtime_cfg):
    logger = utils.setup_logger("Audit")
    try:
        schema = runtime_cfg["data_schema"]
        db = MongoClient(runtime_cfg["src_uri"])[runtime_cfg["src_db"]]
        t_map = {"int": int, "str": str, "bytes": bytes}
        colls = utils.get_matching_collections(db, utils.get_hour_prefixes(runtime_cfg))

        logger.info(f"審計來源 [{runtime_cfg['src_db']}]，共 {len(colls)} 個集合")
        for coll_name in colls:
            cursor = db[coll_name].find().limit(1000)
            passed, total = 0, 0
            for doc in cursor:
                total += 1
                is_ok = all(f in doc and isinstance(doc[f], t_map[schema["type_rules"].get(f, "str")])
                            for f in schema["required_fields"])
                if is_ok: passed += 1
            logger.info(f"{coll_name}: 抽檢 {total} 筆, 通過率: {(passed/total*100 if total>0 else 0):.2f}%")
        return True
    except Exception as e:
        logger.error(f"審計失敗: {e}")
        return False

if __name__ == "__main__":
    run_audit(utils.get_runtime_cfg())
