# IPDR MongoDB DR Recovery Tool

針對 MongoDB 分片叢集的 IPDR 資料災難復原工具，支援 Production ↔ DR Site 雙向搬移。

## 架構概覽

```
DR Site ──────────────────────────────► Production
  └─ DR_DB                                └─ PROD_DB
       └─ {YYYYMMDDHH}_{prefix}*               └─ {YYYYMMDDHH}_{prefix}*

Production ───────────────────────────► DR Site
```

## 功能一覽

| 功能 | 腳本 | 說明 |
|------|------|------|
| Phase 1：備份 | `phase1_backup.py` | 對目的端集合執行 `renameCollection`，重命名為 `{coll}_bak_{YYYYMMDD_HHMM}`（O(1)） |
| Phase 2：還原 | `phase2_restore.py` | 審計 → 顯示搬移前資訊（筆數／大小／磁碟空間）→ 確認 → `mongodump` + `mongorestore --drop` → 搬移後筆數核對 |
| 從備份還原 | `restore_from_backup.py` | 顯示 backup 集合筆數並詢問確認後，drop 目的端原集合，將 backup 集合 rename 回原名 |
| 審計 | `audit.py` | 抽樣來源端最多 1000 筆/集合，驗證欄位存在與型別；非阻斷式，亦嵌入 Phase 2 |

## 目錄結構

```
mongo_dr2pro/
├── runner.py                        # 互動式選單入口
├── utils.py                         # 共用工具（Logger、Config、集合前綴計算）
├── phase1_backup.py
├── phase2_restore.py
├── restore_from_backup.py
├── audit.py
├── schema_check.json                # 靜態設定（主機、DB 名、Schema），不含帳密與時間
├── schema_check.json.example        # 設定範本（納入版控）
├── generate_test_data.py            # 快速測試資料產生器
├── generate_test_data_pro.py        # 精準測試資料產生器（Schema 驅動）
├── check_data.py                    # 查詢各集合筆數與欄位型別
├── validate_scenarios.py            # 端對端情境驗證（四種時間邊界）
└── logs/                            # 執行日誌（自動建立，不納入版控）
```

## 前置需求

- Python 3.9+
- pymongo
- MongoDB Database Tools（`mongodump` / `mongorestore`）
- 目的端 MongoDB 4.4+（磁碟空間查詢需 `dbStats.fsTotalSize`）

```bash
python -m venv .venv
source .venv/bin/activate
pip install pymongo

brew install mongodb-database-tools  # macOS
```

## 設定

`schema_check.json` 僅存放靜態設定（主機 IP、DB 名稱、Schema），**不存放帳密或時間範圍**，兩者皆在執行時透過互動輸入。

```bash
cp schema_check.json.example schema_check.json
# 填入實際主機與 DB 名稱
```

`schema_check.json` 結構：

```json
{
  "job_config": {
    "prod_host":   "<PROD_HOST>:27017",
    "dr_host":     "<DR_HOST>:27017",
    "prod_db":     "PROD_DB",
    "dr_db":       "DR_DB",
    "coll_prefix": "encColl"
  },
  "data_schema": {
    "required_fields": ["A","B","G","M","J","N","H1","H2","K1","K2","P","Q","R","S","O","W","BV","T","C","D","E","V","U","F","AE"],
    "type_rules": {
      "A":"int","B":"int","G":"int","M":"str","J":"int","N":"str",
      "H1":"int","H2":"int","K1":"int","K2":"int","P":"int","Q":"int",
      "R":"int","S":"int","O":"str","W":"str","BV":"str","T":"str",
      "C":"str","D":"str","E":"str","V":"str","U":"str","F":"str","AE":"int"
    }
  }
}
```

## 使用方式

### 互動式選單（建議）

```bash
python runner.py
```

執行後依序互動：

1. **選擇搬移方向**（同時顯示兩端 IP，y/n 確認）
2. **輸入帳號密碼**（最多三次；以 pymongo `ping` 同時驗證兩端 MongoDB 連線，失敗則結束）
3. **輸入時間範圍**（格式 `YYYYMMDDHH`；確認後列出將處理的集合前綴，y/n 確認）
4. **選擇分表範圍**（`0` = 所有分表，`N` = 僅搬移第 N 號分表，例如輸入 `1` 則只處理 `*_encColl_1`）

```
=== IPDR 修復流程 ===
  [1] 備份原始資料
  [2] 開始轉移資料
  [R] 還原備份資料
  [A] 檢查欲轉移資料格式

請選擇步驟 (Q退出):
```

每個步驟執行完畢後會顯示實際耗時（不含使用者操作時間），例如：`✅ 開始轉移資料 已執行完畢。（耗時 47.3 秒）`

### 單獨執行各功能

```bash
python phase1_backup.py
python phase2_restore.py
python restore_from_backup.py
python audit.py
```

單獨執行時同樣觸發完整互動流程（方向 → 登入 → 時間範圍 → 分表選擇）。

## 集合命名規則

集合名稱格式：`{YYYYMMDDHH}_{coll_prefix}[_{N}]`

例如 `start_ts=2026071808`、`end_ts=2026071810`，選擇所有分表時，將處理所有名稱以以下前綴開頭的集合：

```
2026071808_encColl*   （含 _1、_2 等分表）
2026071809_encColl*
2026071810_encColl*
```

若選擇單一分表（例如輸入 `1`），則只處理：

```
2026071808_encColl_1
2026071809_encColl_1
2026071810_encColl_1
```

## Phase 1 備份機制

Phase 1 對目的端現有集合執行 `renameCollection`（O(1)，僅更新 metadata，不複製資料）。備份後集合命名為 `{原集合名}_bak_{YYYYMMDD_HHMM}`，仍存在於同一個 DB 內。這是 Phase 2 `--drop` 失敗後唯一的安全網。

## Phase 2 還原機制

Phase 2 流程：

1. 執行審計（抽樣來源端，驗證欄位與型別，非阻斷式）
2. **搬移前資訊確認**（在計時器啟動前顯示，不計入耗時）：
   - 來源端各集合筆數與儲存大小（`collStats.storageSize`）
   - 目的端各集合目前筆數
   - 目的端磁碟空間（透過 `dbStats.fsTotalSize`／`fsUsedSize` 查詢目的端伺服器，等同於在目的端執行 `df -h /var/lib/mongo`）
3. y/n 確認後才執行 drop
4. 對每個集合執行 `mongodump`（來源端）→ `mongorestore --drop`（目的端），`mongorestore` 進度即時顯示於終端
5. **搬移後筆數核對**：逐集合比對來源筆數與目的筆數，並顯示合計是否一致

## 從備份還原機制

當 Phase 2 失敗或需要回滾時，使用 `restore_from_backup.py`：

1. 根據時間範圍在目的端找出對應的 backup 集合（若同一集合有多份備份，取最新一份）
2. 顯示彙總表格（原始集合目前筆數 vs. 備份集合筆數），詢問整體是否開始（y/n）
3. 逐集合處理：
   - **原集合不存在**：直接將備份 rename 回原名，無需額外確認
   - **原集合已存在**：
     1. 顯示原集合目前筆數
     2. 詢問是否刪除現有集合（y/n）
     3. 若選擇刪除，需再輸入一次集合名稱作為 double-check；名稱不符則跳過
     4. 確認無誤後 drop 原集合，再執行 `renameCollection` 還原備份
4. 若有任何集合被跳過，記錄 warning 並回傳失敗狀態

## 審計機制

`audit.py` 連線至來源端，對每個目標集合抽樣最多 1000 筆文件，逐筆驗證：

1. **欄位存在**：`data_schema.required_fields` 中所有欄位必須存在於文件內
2. **型別正確**：每個欄位的 Python 型別須符合 `data_schema.type_rules`（`"int"` → `int`、`"str"` → `str`）

結果以通過率記錄（例：`抽檢 1000 筆, 通過率: 100.00%`）。不自動中止 Phase 2，通過率偏低時需人工決策。

## 測試資料

```bash
python generate_test_data_pro.py   # 產生測試資料（互動式輸入時間範圍）
python check_data.py               # 查詢各集合筆數與欄位
python validate_scenarios.py       # 四種時間邊界情境端對端驗證
```

### generate_test_data_pro.py

執行後依序互動：

1. **選擇搬移方向**（DR→Central 或 Central→DR）
2. **登入**（同主工具，最多三次）
3. **輸入時間範圍**（格式 `YYYYMMDDHH`；**年份限制在 2025 以前**，超過會要求重新輸入）

產生器根據 `data_schema` 動態產生欄位，每個小時建立一個 collection：
- **DR**：100 筆，`status: "VALID_DR_DATA"`
- **Production**：50 筆，`status: "CORRUPTED"`

若目標 collection 已存在資料，會自動清除後再建立，並於 log 中記錄清除筆數。

時間欄位（`B`）以該小時起點（毫秒）為基準，每筆間隔 36 秒，100 筆剛好填滿一小時。

### validate_scenarios.py

執行後**先選擇搬移方向**，接著自動依序執行四個預設情境（無需手動輸入時間）：

| 情境 | 時間範圍 | 測試目的 |
|------|----------|----------|
| 1. 同日跨 collection | 2025-03-10 02:00 → 05:00 | 驗證同一天內連續多個小時集合均正確處理 |
| 2. 跨日 | 2025-03-10 20:00 → 2025-03-11 03:00 | 驗證跨越午夜日期邊界時，日期遞進邏輯正確 |
| 3. 跨 00:00 | 2025-03-10 23:00 → 2025-03-11 00:00 | 驗證恰好跨過 00:00 的最小跨日情境（邊界值測試） |
| 4. 跨年 | 2024-12-31 22:00 → 2025-01-01 01:00 | 驗證跨越年份邊界時，年份與月份同步遞進正確 |

每個情境驗證：集合數量、集合名稱、每集合 100 筆有效資料、備份集合已建立。

## 注意事項

- **Phase 2** 有兩道確認：① 搬移前顯示來源筆數／大小與目的端磁碟空間（y/n）；② 審計完成後再次詢問是否繼續 drop 並還原（y/n）
- **從備份還原**對每個已存在的原集合單獨確認：y/n + 輸入集合名稱 double-check，避免誤刪
- `schema_check.json` 含有主機資訊，**請勿提交至版控**（已列入 `.gitignore`）
- 帳密不存在任何檔案中，每次執行皆透過互動輸入
- 所有腳本需從專案根目錄執行

## 日誌

每次執行一個步驟，自動於 `logs/` 下產生獨立日誌檔：

| 步驟 | 日誌檔命名範例 |
|------|----------------|
| [1] 備份 | `logs/backup_20260728_143022.log` |
| [2] 轉移 | `logs/restore_20260728_143500.log` |
| [R] 從備份還原 | `logs/restore_from_backup_20260728_150012.log` |
| [A] 審計 | `logs/audit_20260728_143200.log` |

日誌同時輸出至終端。計時器與日誌皆在使用者確認後才開始，不含使用者操作等待時間。
