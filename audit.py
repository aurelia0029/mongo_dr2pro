from collections import Counter
from pymongo import MongoClient
import utils

_MANDATORY = {"A", "B"}

def _check_doc(doc, schema, t_map, required):
    """Return list of violation reasons for one document. Empty list = pass."""
    reasons = []

    # A and B: must exist and not be null
    for f in _MANDATORY:
        if f not in doc or doc[f] is None:
            reasons.append(f"欄位 {f} 缺失或為 null")
        elif not isinstance(doc[f], t_map[schema["type_rules"].get(f, "str")]):
            reasons.append(f"欄位 {f} 型別錯誤（期望 {schema['type_rules'].get(f)}）")

    # No fields outside the schema are allowed (excluding MongoDB's own _id)
    extra = set(doc.keys()) - required - {"_id"}
    if extra:
        reasons.append(f"含不允許欄位: {sorted(extra)}")

    return reasons

def run_audit(runtime_cfg):
    logger = utils.setup_logger("Audit")
    try:
        schema = runtime_cfg["data_schema"]
        db = MongoClient(runtime_cfg["src_uri"])[runtime_cfg["src_db"]]
        t_map = {"int": int, "str": str, "bytes": bytes}
        required = set(schema["required_fields"])
        colls = utils.get_matching_collections(db, utils.get_hour_prefixes(runtime_cfg),
                                               runtime_cfg.get("subcoll_suffix"))

        logger.info(f"審計來源 [{runtime_cfg['src_db']}]，共 {len(colls)} 個集合")
        logger.info(f"規則：A/B 不可空且型別須正確；不允許 schema 以外的欄位；其餘欄位不檢查")
        for coll_name in colls:
            cursor = db[coll_name].find().limit(1000)
            passed, total = 0, 0
            fail_reasons: Counter = Counter()
            for doc in cursor:
                total += 1
                reasons = _check_doc(doc, schema, t_map, required)
                if reasons:
                    for r in reasons:
                        fail_reasons[r] += 1
                else:
                    passed += 1

            pass_rate = passed / total * 100 if total > 0 else 0
            logger.info(f"{coll_name}: 抽檢 {total} 筆, 通過率: {pass_rate:.2f}%")
            for reason, count in fail_reasons.most_common():
                logger.warning(f"  [{count} 筆] {reason}")
        return True
    except Exception as e:
        logger.error(f"審計失敗: {e}")
        return False

if __name__ == "__main__":
    runtime_cfg = utils.get_runtime_cfg()
    log_handler, log_path = utils.open_session_log("audit")
    try:
        run_audit(runtime_cfg)
    finally:
        utils.close_session_log(log_handler)
