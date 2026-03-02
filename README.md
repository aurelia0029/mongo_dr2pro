# IPDR MongoDB DR Recovery Tool

針對 MongoDB 分片叢集的 IPDR 資料災難復原工具，透過四階段流程將 DR Site 資料安全地回填至 Production 環境。

## 架構概覽

```
DR Site (來源) ─────────────────────────► Production (目標)
  └─ DR_DB                                  └─ PROD_DB
       └─ {YYYYMMDDHH}_{prefix}                  └─ {YYYYMMDDHH}_{prefix}
```

資料流向：`DR Site → (審計) → Staging → (合併) → Production`

## 四階段流程

| 階段 | 腳本 | 說明 |
|------|------|------|
| Phase 1 | `phase1_evacuation.py` | 備份並清空 Production 指定時間區間的資料 |
| Phase 2 | `phase2_data_integrity_audit.py` | 審計 DR Site 資料完整性（抽樣驗證） |
| Phase 3 | `phase3_load_to_staging.py` | 將 DR 資料搬運至 Production 暫存集合並建立索引 |
| Phase 4 | `phase4_final_merge_restore.py` | 使用 `$merge` 原子合併暫存集合回填正式集合 |

## 目錄結構

```
dr2pro/
├── runner.py                        # 互動式選單入口
├── utils.py                         # 共用工具（Logger、Config、集合名稱計算）
├── phase1_evacuation.py
├── phase2_data_integrity_audit.py
├── phase3_load_to_staging.py
├── phase4_final_merge_restore.py
├── schema_check.json                # 任務設定（連線資訊、時間範圍、Schema）
├── generate_test_data.py            # 產生測試資料（驗證用）
├── check_data.py                    # 查詢各集合筆數與欄位型別
└── logs/                            # 執行日誌（自動建立，不納入版控）
```

## 前置需求

- Python 3.9+
- pymongo
- 可連線至 Production 與 DR Site 的 MongoDB 主機

安裝依賴：

```bash
python -m venv .venv
source .venv/bin/activate
pip install pymongo
```

## 設定

複製範本並依實際環境修改：

```bash
cp schema_check.json.example schema_check.json
```

`schema_check.json` 結構說明：

```json
{
  "job_config": {
    "start_ts": 1772251200000,      // 起始時間戳（毫秒 epoch）
    "end_ts":   1772337600000,      // 結束時間戳（毫秒 epoch）
    "time_field": "B",              // MongoDB 文件中的時間欄位名稱
    "prod_uri": "mongodb://<PROD_HOST>:27017",
    "dr_uri":   "mongodb://<DR_HOST>:27017",
    "prod_db":  "PROD_DB",
    "dr_db":    "DR_DB",
    "coll_prefix": "encColl"        // 集合名稱後綴，格式：{YYYYMMDDHH}_{coll_prefix}
  },
  "data_schema": {
    "required_fields": ["B", "flowStart", "shk"],
    "type_rules": {
      "B": "int",
      "flowStart": "str",
      "shk": "bytes"
    }
  }
}
```

## 使用方式

### 互動式選單（建議）

```bash
python runner.py
```

```
=== IPDR 修復流程 (Shard Key: _id) ===
 [1] 備份並清空主表
 [2] 審計 DR 資料
 [3] 搬運至暫存並建索引
 [4] 最後合併回填

請選擇步驟 (Q退出):
```

### 單獨執行各階段

```bash
python phase1_evacuation.py
python phase2_data_integrity_audit.py
python phase3_load_to_staging.py
python phase4_final_merge_restore.py
```

### 測試與驗證

```bash
# 產生測試資料（需 Production 與 DR 均可連線）
python generate_test_data.py

# 查詢各集合狀態
python check_data.py
```

## 日誌

執行後日誌自動寫入 `logs/recovery_YYYYMMDD.log`，同時輸出至終端。

## 注意事項

- **Phase 1 會刪除 Production 資料**，請確認備份集合（`*_bak_HHMM`）已正確建立後再繼續
- **Phase 4** 使用 `$merge` 的 `whenMatched: keepExisting` 策略，既有資料不會被覆蓋
- `schema_check.json` 含有連線資訊，**請勿提交至版控**，使用 `.gitignore` 排除
