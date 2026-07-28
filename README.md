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
| Phase 2：還原 | `phase2_restore.py` | 內含審計；顯示目的端各集合筆數並詢問確認後，`mongodump` 來源端 → `mongorestore --drop` 覆蓋目的端 |
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
2. **輸入帳號密碼**（最多三次；會同時 ping 兩端 MongoDB，失敗則結束）
3. **輸入時間範圍**（格式 `YYYYMMDDHH`；確認後列出將處理的集合前綴，y/n 確認）

```
=== IPDR 修復流程 ===
  [1] Phase 1：備份目的端集合（renameCollection）
  [2] Phase 2：還原來源端資料至目的端（含審計）
  [3] 從備份還原（rename backup 集合 → 原集合名）
  [A] 審計（單獨執行，不還原）

請選擇步驟 (Q退出):
```

### 單獨執行各功能

```bash
python phase1_backup.py
python phase2_restore.py
python restore_from_backup.py
python audit.py
```

單獨執行時同樣觸發完整互動流程（方向 → 登入 → 時間範圍）。

## 集合命名規則

集合名稱格式：`{YYYYMMDDHH}_{coll_prefix}*`

例如 `start_ts=2026071808`、`end_ts=2026071810`，將處理所有名稱以以下前綴開頭的集合：

```
2026071808_encColl*
2026071809_encColl*
2026071810_encColl*
```

支援子集合（如 `2026071808_encColl_1`、`2026071808_encColl_2`）——只要名稱以對應前綴開頭均納入。

## Phase 1 備份機制

Phase 1 對目的端現有集合執行 `renameCollection`（O(1)，僅更新 metadata，不複製資料）。備份後集合命名為 `{原集合名}_bak_{YYYYMMDD_HHMM}`，仍存在於同一個 DB 內。這是 Phase 2 `--drop` 失敗後唯一的安全網。

## Phase 2 還原機制

Phase 2 流程：

1. 執行審計（抽樣來源端，驗證欄位與型別，非阻斷式）
2. **顯示目的端各集合目前筆數，詢問使用者確認（y/n）後才執行 drop**
3. 對每個集合執行 `mongodump`（來源端）→ `mongorestore --drop`（目的端）

## 從備份還原機制

當 Phase 2 失敗或需要回滾時，使用 `restore_from_backup.py`：

1. 根據時間範圍在目的端找出對應的 backup 集合（若同一集合有多份備份，取最新一份）
2. **顯示各集合原始筆數與備份筆數，詢問使用者確認（y/n）後才執行**
3. Drop 目的端現有集合（若存在）
4. 執行 `renameCollection`：`{coll}_bak_{timestamp}` → `{coll}`（O(1)）

## 審計機制

`audit.py` 連線至來源端，對每個目標集合抽樣最多 1000 筆文件，逐筆驗證：

1. **欄位存在**：`data_schema.required_fields` 中所有欄位必須存在於文件內
2. **型別正確**：每個欄位的 Python 型別須符合 `data_schema.type_rules`（`"int"` → `int`、`"str"` → `str`）

結果以通過率記錄（例：`抽檢 1000 筆, 通過率: 100.00%`）。不自動中止 Phase 2，通過率偏低時需人工決策。

## 測試資料

```bash
python generate_test_data_pro.py   # 產生測試資料（Schema 驅動）
python check_data.py               # 查詢各集合筆數與欄位
python validate_scenarios.py       # 四種時間邊界情境端對端驗證
```

`generate_test_data_pro.py` 根據 `data_schema` 動態產生欄位，Production 文件標記 `status: "CORRUPTED"`，DR 文件標記 `status: "VALID_DR_DATA"`。

### validate_scenarios.py 四種情境

| 情境 | 時間範圍 | 測試目的 |
|------|----------|----------|
| 1. 同日跨 collection | 2026-03-10 02:00 → 05:00 | 驗證同一天內連續多個小時集合均正確處理 |
| 2. 跨日 | 2026-03-10 20:00 → 2026-03-11 03:00 | 驗證跨越午夜日期邊界時，日期遞進邏輯正確 |
| 3. 跨 00:00 | 2026-03-10 23:00 → 2026-03-11 00:00 | 驗證恰好跨過 00:00 的最小跨日情境（邊界值測試） |
| 4. 跨年 | 2025-12-31 22:00 → 2026-01-01 01:00 | 驗證跨越年份邊界時，年份與月份同步遞進正確 |

每個情境驗證：集合數量、集合名稱、每集合 100 筆有效資料、備份集合已建立。

## 注意事項

- **Phase 2 與從備份還原均在 drop 前顯示筆數並詢問確認**，確認後才執行不可逆操作
- `schema_check.json` 含有主機資訊，**請勿提交至版控**（已列入 `.gitignore`）
- 帳密不存在任何檔案中，每次執行皆透過互動輸入
- 所有腳本需從專案根目錄執行

## 日誌

執行後日誌自動寫入 `logs/recovery_YYYYMMDD.log`，同時輸出至終端。
