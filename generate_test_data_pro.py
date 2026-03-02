import json
import datetime
import bson
import logging
import os
from pymongo import MongoClient, UpdateOne

# --- 基礎日誌配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger("TestGenerator")

def get_coll_name(ts_ms, prefix):
    """根據毫秒時間戳與前綴回傳集合名稱 (格式: 2026022812_encColl)"""
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0)
    return dt.strftime(f"%Y%m%d%H_{prefix}")

def generate_test_data():
    # 1. 載入配置
    config_path = "schema_check.json"
    if not os.path.exists(config_path):
        logger.error(f"找不到 {config_path}，請確認檔案路徑。")
        return

    with open(config_path, "r") as f:
        full_cfg = json.load(f)
        cfg = full_cfg["job_config"]

    start_ts = cfg["start_ts"]
    end_ts = cfg["end_ts"]
    prefix = cfg["coll_prefix"]
    time_field = cfg["time_field"]

    p_client = MongoClient(cfg["prod_uri"])
    d_client = MongoClient(cfg["dr_uri"])
    p_db = p_client[cfg["prod_db"]]
    d_db = d_client[cfg["dr_db"]]

    logger.info(f"=== 測試資料產生器啟動 ===")
    logger.info(f"區間: {start_ts} -> {end_ts}")
    logger.info(f"涉及環境: {cfg['prod_uri']} & {cfg['dr_uri']}")

    # 2. 找出所有受影響的集合名稱
    target_colls = set()
    temp_ts = start_ts
    while temp_ts <= end_ts:
        target_colls.add(get_coll_name(temp_ts, prefix))
        temp_ts += 3600000 # 步進一小時
    
    # 3. 逐一處理集合
    for coll_name in sorted(list(target_colls)):
        logger.info(f"--- 處理集合: {coll_name} ---")
        
        # 取得該小時的邊界 (例如 10:00:00.000 到 10:59:59.999)
        # 這裡是為了確保我們只在該小時的集合內寫入「符合全局區間」的資料
        dt_obj = datetime.datetime.strptime(coll_name.split('_')[0], "%Y%m%d%H")
        hour_start = int(dt_obj.timestamp() * 1000)
        hour_end = hour_start + 3600000 - 1

        # 計算實際要寫入的時間範圍 (取全局區間與小時邊界的交集)
        actual_start = max(start_ts, hour_start)
        actual_end = min(end_ts, hour_end)

        if actual_start >= actual_end:
            logger.warning(f"跳過 {coll_name}: 不在指定的毫秒區間內")
            continue

        # 清理舊資料
        p_db[coll_name].drop()
        d_db[coll_name].drop()

        dr_docs = []
        prod_docs = []
        
        # 4. 生成 100 筆資料 (DR) 與 50 筆資料 (Prod)
        # 資料會在實際區間內均勻分佈
        step = (actual_end - actual_start) // 100
        
        for i in range(100):
            doc_ts = actual_start + (i * step)
            unique_id = bson.ObjectId() # 核心：同步 _id
            
            # DR 完整資料 (包含加密 bytes)
            dr_docs.append({
                "_id": unique_id,
                time_field: doc_ts,
                "flowStart": f"flow_{coll_name}_{i}",
                "shk": f"SECURE_DATA_{i}".encode('utf-8'), # 模擬 Bytes
                "status": "VALID_DR_DATA",
                "gen_time": datetime.datetime.now()
            })

            # 前 50 筆同時寫入 Production，但內容是錯的 (模擬需要被修復)
            if i < 50:
                prod_docs.append({
                    "_id": unique_id,
                    time_field: doc_ts,
                    "flowStart": f"OLD_flow_{i}",
                    "shk": b"OLD_ENCRYPTED_DATA",
                    "note": "Wait for Phase 1 to delete me",
                    "status": "CORRUPTED"
                })

        # 寫入資料
        if dr_docs:
            d_db[coll_name].insert_many(dr_docs)
            # 建立索引 (模擬真實環境)
            d_db[coll_name].create_index([("_id", 1)])
            d_db[coll_name].create_index([(time_field, 1)])
            
        if prod_docs:
            p_db[coll_name].insert_many(prod_docs)
            p_db[coll_name].create_index([("_id", 1)])
            p_db[coll_name].create_index([(time_field, 1)])

        logger.info(f"   -> {coll_name} 完成: DR(100筆), Prod(50筆衝突)")

    logger.info("✅ 所有測試場景建置完成。")

if __name__ == "__main__":
    generate_test_data()
