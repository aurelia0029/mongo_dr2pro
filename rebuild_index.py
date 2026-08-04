import datetime, os, subprocess
from pymongo import MongoClient
import utils

JS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rebuild_index.js")

INTENDED_INDEXES = [
    {"name": "B_1_A_1", "keys": "{ B: 1, A: 1 }"},
    {"name": "C_1",     "keys": "{ C: 1 }"},
    {"name": "W_1",     "keys": "{ W: 1 }"},
    {"name": "BV_1",    "keys": "{ BV: 1 }"},
    {"name": "AE_1",    "keys": "{ AE: 1 }"},
]

def show_index_plan(runtime_cfg):
    """Display target host/DB, current indexes per collection, and intended indexes."""
    dst_host = runtime_cfg["dst_host"]
    dst_db   = runtime_cfg["dst_db"]

    print(f"\n重建索引目標：{dst_host}  /  DB: {dst_db}")

    client = MongoClient(runtime_cfg["dst_uri"])
    db = client[dst_db]
    colls = utils.get_matching_collections(db, utils.get_hour_prefixes(runtime_cfg))

    if not colls:
        print("找不到符合時間範圍的集合。")
        return False

    print(f"\n  {'集合名稱':<40}  現有索引（不含 _id）")
    print("  " + "─" * 70)
    for coll_name in colls:
        existing = [idx["name"] for idx in db[coll_name].list_indexes() if idx["name"] != "_id_"]
        existing_str = ", ".join(existing) if existing else "（無）"
        print(f"  {coll_name:<40}  {existing_str}")

    print(f"\n  欲建立索引（已存在者略過）：")
    for idx in INTENDED_INDEXES:
        print(f"    {idx['name']:<12}  {idx['keys']}")

    print(f"\n  共 {len(colls)} 個集合")
    return True

def run_rebuild_index(runtime_cfg, skip_confirm=False):
    logger = utils.setup_logger("RebuildIndex")
    try:
        if not skip_confirm:
            result = show_index_plan(runtime_cfg)
            if not result:
                return False
            confirm = input("\n確認執行重建索引？(y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("使用者取消操作。")
                return False

        dst_host = runtime_cfg["dst_host"]
        dst_db   = runtime_cfg["dst_db"]

        # JS script's endHour is exclusive; our end_ts is inclusive → add 1 hour
        end_dt = datetime.datetime.strptime(runtime_cfg["end_ts"], "%Y%m%d%H") + datetime.timedelta(hours=1)
        end_hour_exclusive = end_dt.strftime("%Y%m%d%H")

        eval_code = (
            f"var startHour='{runtime_cfg['start_ts']}';"
            f"var endHour='{end_hour_exclusive}';"
            f"var dbName='{dst_db}';"
        )

        logger.info(f"重建索引目標：{dst_host} / {dst_db}")
        logger.info(
            f"時間範圍：{runtime_cfg['start_ts']} → {runtime_cfg['end_ts']}（含）"
        )
        logger.info(f"欲建立索引：{', '.join(i['name'] for i in INTENDED_INDEXES)}")

        r = subprocess.run([
            "mongosh",
            runtime_cfg["dst_uri"],
            "--eval", eval_code,
            JS_SCRIPT,
        ])

        if r.returncode != 0:
            raise RuntimeError(f"mongosh 失敗（exitcode={r.returncode}）")

        logger.info("重建索引完成。")
        return True
    except Exception as e:
        logger.error(f"重建索引失敗: {e}")
        return False

if __name__ == "__main__":
    runtime_cfg = utils.get_runtime_cfg()
    log_handler, log_path = utils.open_session_log("rebuild_index")
    try:
        run_rebuild_index(runtime_cfg)
    finally:
        utils.close_session_log(log_handler)
