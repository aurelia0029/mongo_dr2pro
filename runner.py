import time
import utils
import phase1_backup, audit, phase2_restore, restore_from_backup

def main():
    runtime_cfg = utils.get_runtime_cfg()

    steps = {
        "1": ("備份原始資料",         lambda: phase1_backup.run_backup(runtime_cfg)),
        "2": ("開始轉移資料",         lambda: phase2_restore.run_restore(runtime_cfg)),
        "R": ("還原備份資料",         lambda: restore_from_backup.run_restore_from_backup(runtime_cfg)),
        "A": ("檢查欲轉移資料格式",   lambda: audit.run_audit(runtime_cfg)),
    }

    while True:
        print("\n=== IPDR 修復流程 ===")
        for k, (label, _) in steps.items():
            print(f"  [{k}] {label}")
        choice = input("\n請選擇步驟 (Q退出): ").upper()
        if choice == 'Q':
            break
        if choice in steps:
            label, func = steps[choice]
            t0 = time.time()
            func()
            elapsed = time.time() - t0
            print(f"\n✅ {label} 已執行完畢。（耗時 {elapsed:.1f} 秒）")

if __name__ == "__main__":
    main()
