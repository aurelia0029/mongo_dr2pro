import time
import utils
import phase1_backup, audit, phase2_restore, restore_from_backup, delete_backup, rebuild_index

def main():
    runtime_cfg = utils.get_runtime_cfg()

    # (label, log_name, preview_fn, exec_fn)
    # preview_fn: called before timer and session log — shows info, returns None (proceed) or False (nothing to do)
    # exec_fn:    called after confirmation, inside the timer and session log
    steps = {
        "1": ("備份原始資料",       "backup",
              None,
              lambda: phase1_backup.run_backup(runtime_cfg)),
        "2": ("開始轉移資料",       "restore",
              lambda: phase2_restore.show_transfer_info(runtime_cfg),
              lambda: phase2_restore.run_restore(runtime_cfg, skip_drop_confirm=True)),
        "R": ("還原備份資料",       "restore_from_backup",
              lambda: restore_from_backup.show_backup_plan(runtime_cfg),
              lambda: restore_from_backup.run_restore_from_backup(runtime_cfg, skip_global_confirm=True)),
        "A": ("檢查欲轉移資料格式", "audit",
              None,
              lambda: audit.run_audit(runtime_cfg)),
        "D": ("刪除備份資料",       "delete_backup",
              lambda: delete_backup.show_delete_plan(runtime_cfg),
              lambda: delete_backup.run_delete_backup(runtime_cfg, skip_confirm=True)),
        "I": ("重建索引",           "rebuild_index",
              lambda: rebuild_index.show_index_plan(runtime_cfg),
              lambda: rebuild_index.run_rebuild_index(runtime_cfg, skip_confirm=True)),
    }

    while True:
        print("\n=== IPDR 修復流程 ===")
        print("  正常流程：[1] 備份 → [2] 搬移 → [I] 重建索引 → [D] 刪除備份；[R][A] 為輔助功能")
        for k, (label, _, _, _) in steps.items():
            print(f"  [{k}] {label}")
        choice = input("\n請選擇步驟 (Q退出): ").upper()
        if choice == 'Q':
            break
        if choice not in steps:
            continue

        label, log_name, preview_fn, exec_fn = steps[choice]

        if preview_fn is not None:
            result = preview_fn()
            if result is False:
                print("沒有可執行的項目，請確認備份集合是否存在。")
                continue
            if input("\n確認繼續？(y/n): ").strip().lower() != 'y':
                print("操作已取消。")
                continue

        log_handler, log_path = utils.open_session_log(log_name)
        t0 = time.perf_counter()
        try:
            exec_fn()
        finally:
            elapsed = time.perf_counter() - t0
            utils.close_session_log(log_handler)
        print(f"\n✅ {label} 已執行完畢。（耗時 {elapsed:.1f} 秒）")

if __name__ == "__main__":
    main()
