from pymongo import MongoClient
import utils

def run_restore_from_backup(runtime_cfg):
    logger = utils.setup_logger("RestoreBackup")
    try:
        client = MongoClient(runtime_cfg["dst_uri"])
        db = client[runtime_cfg["dst_db"]]
        prefixes = utils.get_hour_prefixes(runtime_cfg)
        all_colls = set(db.list_collection_names())

        # Find backup collections and map them to their original names
        backup_map = {}  # original_name → [backup_names]
        for coll in sorted(all_colls):
            bak_idx = coll.rfind("_bak_")
            if bak_idx == -1:
                continue
            original_name = coll[:bak_idx]
            if any(original_name.startswith(p) for p in prefixes):
                backup_map.setdefault(original_name, []).append(coll)

        if not backup_map:
            logger.info("找不到符合時間範圍的備份集合。")
            return False

        # Build restore plan: pick the latest backup per original collection
        restore_plan = []
        for original_name in sorted(backup_map):
            latest_bak = sorted(backup_map[original_name])[-1]
            restore_plan.append((original_name, latest_bak))

        print(f"\n從備份還原至目的端 [{runtime_cfg['dst_db']}]：")
        print(f"  {'原始集合（將被 drop）':<35} {'目前筆數':>8}   {'備份集合（rename 來源）':<40} {'備份筆數':>8}")
        print("  " + "─" * 97)
        for original_name, bak_name in restore_plan:
            if original_name in all_colls:
                orig_cnt = f"{db[original_name].count_documents({}):>8}"
            else:
                orig_cnt = f"{'(不存在)':>8}"
            bak_cnt = db[bak_name].count_documents({})
            print(f"  {original_name:<35} {orig_cnt}   {bak_name:<40} {bak_cnt:>8}")

        confirm = input("\n確認 drop 原始集合並從備份 rename 還原？(y/n): ").strip().lower()
        if confirm != 'y':
            logger.info("使用者取消操作。")
            return False

        for original_name, bak_name in restore_plan:
            if original_name in db.list_collection_names():
                db[original_name].drop()
                logger.info(f"已 drop {original_name}")
            client.admin.command(
                "renameCollection",
                f"{runtime_cfg['dst_db']}.{bak_name}",
                to=f"{runtime_cfg['dst_db']}.{original_name}"
            )
            logger.info(f"{bak_name} → {original_name}")

        return True
    except Exception as e:
        logger.error(f"從備份還原失敗: {e}")
        return False

if __name__ == "__main__":
    run_restore_from_backup(utils.get_runtime_cfg())
