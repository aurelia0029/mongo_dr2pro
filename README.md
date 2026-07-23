# IPDR MongoDB DR Recovery Tool

針對 MongoDB 分片叢集的 IPDR 資料災難復原工具，透過三階段流程將 DR Site 資料還原至 Production 環境。

## 架構概覽

```
DR Site (來源) ─────────────────────────► Production (目標)
  └─ DR_DB                                  └─ PROD_DB
       └─ {YYYYMMDDHH}_{prefix}                  └─ {YYYYMMDDHH}_{prefix}
```

資料流向：`DR Site → (審計) → Production`

## 三階段流程

| 階段 | 腳本 | 說明 |
|------|------|------|
| Phase 1 | `phase1_evacuation.py` | `mongodump` 備份 Production 指定時間區間的資料至 `backups/bak_{YYYYMMDD_HHMM}/` |
| Phase 2 | `phase2_data_integrity_audit.py` | 審計 DR Site 資料完整性（抽樣驗證） |
| Phase 3 | `phase3_restore.py` | `mongodump` DR 資料並 `mongorestore --drop` 直接覆蓋 Production 集合 |

## 目錄結構

```
dr2pro/
├── runner.py                        # 互動式選單入口
├── utils.py                         # 共用工具（Logger、Config、集合名稱計算）
├── phase1_evacuation.py
├── phase2_data_integrity_audit.py
├── phase3_restore.py
├── schema_check.json                # 任務設定（連線資訊、時間範圍、Schema）
├── generate_test_data.py            # 產生測試資料（快速版）
├── generate_test_data_pro.py        # 產生測試資料（精準版，含 Logger）
├── check_data.py                    # 查詢各集合筆數與欄位型別
├── validate_scenarios.py            # 端對端情境驗證（四種時間邊界）
├── backups/                         # mongodump 備份（自動建立，不納入版控）
└── logs/                            # 執行日誌（自動建立，不納入版控）
```

## 前置需求

- Python 3.9+
- pymongo
- MongoDB Database Tools（`mongodump` / `mongorestore`）
- 可連線至 Production 與 DR Site 的 MongoDB 主機

安裝依賴：

```bash
python -m venv .venv
source .venv/bin/activate
pip install pymongo

brew install mongodb-database-tools  # macOS
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
    "start_ts": "2026071808",       // 起始小時（YYYYMMDDHH，包含）
    "end_ts":   "2026071810",       // 結束小時（YYYYMMDDHH，包含）
    "time_field": "B",              // MongoDB 文件中的時間欄位名稱
    "prod_uri": "mongodb://<PROD_HOST>:27017",
    "dr_uri":   "mongodb://<DR_HOST>:27017",
    "prod_db":  "PROD_DB",
    "dr_db":    "DR_DB",
    "coll_prefix": "encColl"        // 集合名稱前綴，格式：{YYYYMMDDHH}_{coll_prefix}*
  },
  "data_schema": {
    "required_fields": ["A", "B", "G", "M", "J", "N", "H1", "H2", "K1", "K2", "P", "Q", "R", "S", "O", "W", "BV", "T", "C", "D", "E", "V", "U", "F", "AE"],
    "type_rules": {
      "A": "int", "B": "int", "G": "int", "J": "int",
      "H1": "int", "H2": "int", "K1": "int", "K2": "int",
      "P": "int", "Q": "int", "R": "int", "S": "int", "AE": "int",
      "M": "str", "N": "str", "O": "str", "W": "str", "BV": "str",
      "T": "str", "C": "str", "D": "str", "E": "str", "V": "str", "U": "str", "F": "str"
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
 [1] 備份 Production 區間資料
 [2] 審計 DR 資料
 [3] 還原 DR 資料至 Production

請選擇步驟 (Q退出):
```

### 單獨執行各階段

```bash
python phase1_evacuation.py
python phase2_data_integrity_audit.py
python phase3_restore.py
```

### 測試與驗證

提供兩支測試資料產生器，均需 Production 與 DR 均可連線：

| 腳本 | 說明 |
|------|------|
| `generate_test_data.py` | 快速版，用 `print` 輸出，適合臨時驗證 |
| `generate_test_data_pro.py` | 精準版，建議使用 |

**`generate_test_data_pro.py` 改善項目：**
- 使用 Logger，輸出格式一致
- 啟動前驗證 `schema_check.json` 是否存在
- 根據 `data_schema` 動態產生欄位，不硬寫欄位名稱
- Production 資料標記 `status: "CORRUPTED"`，DR 資料標記 `status: "VALID_DR_DATA"`，便於修復後比對
- 額外建立 `time_field` 索引，更貼近正式環境

```bash
# 產生測試資料（精準版）
python generate_test_data_pro.py

# 查詢各集合狀態
python check_data.py

# 端對端情境驗證
python validate_scenarios.py
```

## 日誌

執行後日誌自動寫入 `logs/recovery_YYYYMMDD.log`，同時輸出至終端。

## 注意事項

- **Phase 3 會直接 drop Production 集合**，`mongorestore --drop` 會覆蓋整個集合而非僅時間區間內的資料，Phase 1 備份的 BSON 檔案（`backups/bak_{YYYYMMDD_HHMM}/`）是唯一的安全網
- **Phase 2 不會自動阻擋流程**，審計通過率偏低時需人工判斷是否繼續執行 Phase 3
- `schema_check.json` 含有連線資訊，**請勿提交至版控**，使用 `.gitignore` 排除
