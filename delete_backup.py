from pymongo import MongoClient
import utils

def _find_backup_collections(runtime_cfg):
    """Return sorted list of (bak_coll_name, doc_count) for all matching backup collections."""
    db = MongoClient(runtime_cfg["dst_uri"])[runtime_cfg["dst_db"]]
    prefixes = utils.get_hour_prefixes(runtime_cfg)
    subcoll_suffix = runtime_cfg.get("subcoll_suffix")
    all_colls = set(db.list_collection_names())

    results = []
    for coll in sorted(all_colls):
        bak_idx = coll.rfind("_bak_")
        if bak_idx == -1:
            continue
        original_name = coll[:bak_idx]
        if subcoll_suffix is None:
            matches = any(original_name.startswith(p) for p in prefixes)
        else:
            matches = any(original_name == f"{p}_{subcoll_suffix}" for p in prefixes)
        if matches:
            results.append((coll, db[coll].count_documents({})))

    return db, results

def show_delete_plan(runtime_cfg):
    """Display backup collections to be deleted. Returns True if any found, False otherwise."""
    db, items = _find_backup_collections(runtime_cfg)
    if not items:
        print("找不到符合時間範圍的備份集合。")
        return False

    print(f"\n以下備份集合將從目的端 [{runtime_cfg['dst_db']}] 永久刪除：")
    print(f"  {'備份集合名稱':<50} {'筆數':>8}")
    print("  " + "─" * 62)
    for bak_name, cnt in items:
        print(f"  {bak_name:<50} {cnt:>8}")
    print(f"\n  共 {len(items)} 個備份集合")
    return True

def run_delete_backup(runtime_cfg, skip_confirm=False):
    logger = utils.setup_logger("DeleteBackup")
    try:
        db, items = _find_backup_collections(runtime_cfg)

        if not items:
            logger.info("找不到符合時間範圍的備份集合。")
            return False

        if not skip_confirm:
            show_delete_plan(runtime_cfg)
            confirm = input("\n確認永久刪除以上備份集合？(y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("使用者取消操作。")
                return False

        for bak_name, cnt in items:
            db[bak_name].drop()
            logger.info(f"已刪除備份集合 {bak_name}（{cnt} 筆）")

        logger.info(f"備份清除完成，共刪除 {len(items)} 個集合。")
        return True
    except Exception as e:
        logger.error(f"刪除備份失敗: {e}")
        return False

if __name__ == "__main__":
    runtime_cfg = utils.get_runtime_cfg()
    log_handler, log_path = utils.open_session_log("delete_backup")
    try:
        run_delete_backup(runtime_cfg)
    finally:
        utils.close_session_log(log_handler)
