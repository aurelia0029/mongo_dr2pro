import time
import utils
import phase1_backup, audit, phase2_restore, restore_from_backup

def main():
    runtime_cfg = utils.get_runtime_cfg()

    # (label, preview_fn, exec_fn)
    # preview_fn: called before timer — shows info and returns None (always proceed to confirm)
    #             or returns False (nothing to do, skip)
    # exec_fn:    called after confirmation, inside the timer
    steps = {
        "1": ("備份原始資料",
              None,
              lambda: phase1_backup.run_backup(runtime_cfg)),
        "2": ("開始轉移資料",
              lambda: phase2_restore.show_drop_preview(runtime_cfg),
              lambda: phase2_restore.run_restore(runtime_cfg, auto_confirm=True)),
        "R": ("還原備份資料",
              lambda: restore_from_backup.show_backup_plan(runtime_cfg),
              lambda: restore_from_backup.run_restore_from_backup(runtime_cfg, skip_global_confirm=True)),
        "A": ("檢查欲轉移資料格式",
              None,
              lambda: audit.run_audit(runtime_cfg)),
    }

    while True:
        print("\n=== IPDR 修復流程 ===")
        for k, (label, _, _) in steps.items():
            print(f"  [{k}] {label}")
        choice = input("\n請選擇步驟 (Q退出): ").upper()
        if choice == 'Q':
            break
        if choice not in steps:
            continue

        label, preview_fn, exec_fn = steps[choice]

        if preview_fn is not None:
            result = preview_fn()
            if result is False:
                print("沒有可執行的項目，請確認備份集合是否存在。")
                continue
            if input("\n確認繼續？(y/n): ").strip().lower() != 'y':
                print("操作已取消。")
                continue

        t0 = time.perf_counter()
        exec_fn()
        elapsed = time.perf_counter() - t0
        print(f"\n✅ {label} 已執行完畢。（耗時 {elapsed:.1f} 秒）")

if __name__ == "__main__":
    main()
