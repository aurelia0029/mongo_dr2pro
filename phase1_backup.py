import datetime
from pymongo import MongoClient
import utils

def run_backup(runtime_cfg):
    logger = utils.setup_logger("Phase1")
    try:
        client = MongoClient(runtime_cfg["dst_uri"])
        db = client[runtime_cfg["dst_db"]]
        colls = utils.get_matching_collections(db, utils.get_hour_prefixes(runtime_cfg),
                                               runtime_cfg.get("subcoll_suffix"))
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')

        logger.info(f"備份目的地 [{runtime_cfg['dst_db']}]: {runtime_cfg['start_ts']} - {runtime_cfg['end_ts']}，共 {len(colls)} 個集合")
        for coll_name in colls:
            bak_name = f"{coll_name}_bak_{timestamp}"
            client.admin.command(
                "renameCollection",
                f"{runtime_cfg['dst_db']}.{coll_name}",
                to=f"{runtime_cfg['dst_db']}.{bak_name}"
            )
            logger.info(f"{coll_name} → {bak_name}")
        return True
    except Exception as e:
        logger.error(f"Phase 1 失敗: {e}")
        return False

if __name__ == "__main__":
    runtime_cfg = utils.get_runtime_cfg()
    log_handler, log_path = utils.open_session_log("backup")
    try:
        run_backup(runtime_cfg)
    finally:
        utils.close_session_log(log_handler)
