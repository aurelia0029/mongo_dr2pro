from pymongo import MongoClient
import utils

def _build_backup_plan(runtime_cfg):
    """Returns (client, db, all_colls, restore_plan)."""
    client = MongoClient(runtime_cfg["dst_uri"])
    db = client[runtime_cfg["dst_db"]]
    prefixes = utils.get_hour_prefixes(runtime_cfg)
    all_colls = set(db.list_collection_names())

    backup_map = {}
    for coll in sorted(all_colls):
        bak_idx = coll.rfind("_bak_")
        if bak_idx == -1:
            continue
        original_name = coll[:bak_idx]
        if any(original_name.startswith(p) for p in prefixes):
            backup_map.setdefault(original_name, []).append(coll)

    restore_plan = [(orig, sorted(baks)[-1]) for orig, baks in sorted(backup_map.items())]
    return client, db, all_colls, restore_plan

def _print_backup_table(db, all_colls, restore_plan, dst_db_name):
    print(f"\n從備份還原至目的端 [{dst_db_name}]：")
    print(f"  {'原始集合':<35} {'目前筆數':>8}   {'備份集合（rename 來源）':<40} {'備份筆數':>8}")
    print("  " + "─" * 97)
    for original_name, bak_name in restore_plan:
        orig_cnt = f"{db[original_name].count_documents({}):>8}" if original_name in all_colls else f"{'(不存在)':>8}"
        bak_cnt = db[bak_name].count_documents({})
        print(f"  {original_name:<35} {orig_cnt}   {bak_name:<40} {bak_cnt:>8}")

def show_backup_plan(runtime_cfg):
    """Display backup restore plan without prompting. Returns True if backups found."""
    _, db, all_colls, restore_plan = _build_backup_plan(runtime_cfg)
    if not restore_plan:
        print("找不到符合時間範圍的備份集合。")
        return False
    _print_backup_table(db, all_colls, restore_plan, runtime_cfg["dst_db"])
    return True

def run_restore_from_backup(runtime_cfg, skip_global_confirm=False):
    logger = utils.setup_logger("RestoreBackup")
    try:
        client, db, all_colls, restore_plan = _build_backup_plan(runtime_cfg)

        if not restore_plan:
            logger.info("找不到符合時間範圍的備份集合。")
            return False

        if not skip_global_confirm:
            _print_backup_table(db, all_colls, restore_plan, runtime_cfg["dst_db"])
            confirm = input("\n確認開始從備份還原？(y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("使用者取消操作。")
                return False

        skipped = []
        for original_name, bak_name in restore_plan:
            current_colls = set(db.list_collection_names())

            if original_name in current_colls:
                cnt = db[original_name].count_documents({})
                print(f"\n集合 [{original_name}] 目前已存在，共 {cnt} 筆資料。")
                drop_confirm = input(f"  是否刪除現有集合以還原備份？(y/n): ").strip().lower()
                if drop_confirm != 'y':
                    logger.info(f"跳過 {original_name}（使用者選擇不刪除現有集合）")
                    skipped.append(original_name)
                    continue

                typed = input(f"  請輸入集合名稱確認刪除（{original_name}）: ").strip()
                if typed != original_name:
                    print(f"  名稱不符，跳過 {original_name}。")
                    logger.info(f"跳過 {original_name}（確認名稱輸入錯誤）")
                    skipped.append(original_name)
                    continue

                db[original_name].drop()
                logger.info(f"已 drop {original_name}（{cnt} 筆）")

            client.admin.command(
                "renameCollection",
                f"{runtime_cfg['dst_db']}.{bak_name}",
                to=f"{runtime_cfg['dst_db']}.{original_name}"
            )
            logger.info(f"{bak_name} → {original_name}")

        if skipped:
            logger.warning(f"以下集合已跳過未還原：{skipped}")

        return len(skipped) == 0
    except Exception as e:
        logger.error(f"從備份還原失敗: {e}")
        return False

if __name__ == "__main__":
    run_restore_from_backup(utils.get_runtime_cfg())
