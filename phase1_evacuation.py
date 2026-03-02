from pymongo import MongoClient
import utils, time

def run_evacuation():
    logger = utils.setup_logger("Phase1")
    try:
        cfg = utils.load_config()["job_config"]
        db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]
        query = utils.get_query(cfg)
        
        logger.info(f"開始排空 Production 區間資料: {cfg['start_ts']} - {cfg['end_ts']}")
        for coll_name in utils.get_target_collections(cfg):
            bak_name = f"{coll_name}_bak_{time.strftime('%H%M')}"
            # 只備份區間內的資料
            db[coll_name].aggregate([{"$match": query}, {"$out": bak_name}])
            bak_cnt = db[bak_name].count_documents({})
            # 只刪除區間內的資料
            del_cnt = db[coll_name].delete_many(query).deleted_count
            logger.info(f"集合 {coll_name}: 備份 {bak_cnt} 筆, 刪除 {del_cnt} 筆")
        return True
    except Exception as e:
        logger.error(f"Phase 1 失敗: {e}")
        return False

if __name__ == "__main__":
    run_evacuation()

