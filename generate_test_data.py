import json, datetime, bson
from pymongo import MongoClient

def generate_test_data():
    with open("schema_check.json", "r") as f:
        cfg = json.load(f)["job_config"]

    p_client, d_client = MongoClient(cfg["prod_uri"]), MongoClient(cfg["dr_uri"])
    p_db, d_db = p_client[cfg["prod_db"]], d_client[cfg["dr_db"]]

    curr_ms = cfg["start_ts"]
    end_ms = cfg["end_ts"]
    
    print(f"[*] 初始化環境 (Shard Key: _id)...")

    while curr_ms < end_ms:
        dt = datetime.datetime.fromtimestamp(curr_ms / 1000.0)
        coll_name = dt.strftime(f"%Y%m%d%H_{cfg['coll_prefix']}")
        print(f"\n>>> 處理: {coll_name}")
        
        p_db[coll_name].drop()
        d_db[coll_name].drop()
        
        # DR 寫入 100 筆正確資料
        dr_docs = []
        for i in range(100):
            uid = bson.ObjectId()
            dr_docs.append({
                "_id": uid,
                "B": curr_ms + (i * 10000),
                "flowStart": f"flow_{i}",
                "shk": f"ENC_{i}".encode('utf-8'),
                "status": "correct"
            })
        d_db[coll_name].insert_many(dr_docs)

        # Prod 寫入 50 筆舊資料 (ID 與 DR 重疊)
        p_db[coll_name].insert_many([{
            "_id": dr_docs[i]["_id"], 
            "B": dr_docs[i]["B"], 
            "note": "old_data"
        } for i in range(50)])

        # 模擬分片索引
        p_db[coll_name].create_index([("_id", 1)])
        d_db[coll_name].create_index([("_id", 1)])
        curr_ms += 3600000

    print("\n✅ 測試環境就緒。")

if __name__ == "__main__": generate_test_data()
