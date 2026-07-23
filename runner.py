import sys
import phase1_evacuation, phase2_data_integrity_audit, phase3_restore

def main():
    steps = {
        "1": ("備份 Production 區間資料", phase1_evacuation.run_evacuation),
        "2": ("審計 DR 資料",             phase2_data_integrity_audit.run_audit),
        "3": ("還原 DR 資料至 Production", phase3_restore.run_restore),
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
