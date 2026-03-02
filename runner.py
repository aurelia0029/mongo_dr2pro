import sys
import phase1_evacuation, phase2_data_integrity_audit
import phase3_load_to_staging, phase4_final_merge_restore

def main():
    steps = {
        "1": ("備份並清空主表", phase1_evacuation.run_evacuation),
        "2": ("審計 DR 資料", phase2_data_integrity_audit.run_audit),
        "3": ("搬運至暫存並建索引", phase3_load_to_staging.run_staging),
        "4": ("最後合併回填", phase4_final_merge_restore.run_final_merge)
    }

    while True:
        print("\n=== IPDR 修復流程 (Shard Key: _id) ===")
        for k, v in steps.items(): print(f" [{k}] {v[0]}")
        choice = input("\n請選擇步驟 (Q退出): ").upper()
        if choice == 'Q': break
        if choice in steps:
            steps[choice][1]()
            print(f"\n✅ {steps[choice][0]} 已執行完畢。")

if __name__ == "__main__": main()
