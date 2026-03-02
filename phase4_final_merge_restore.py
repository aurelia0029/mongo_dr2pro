from pymongo import MongoClient
import utils

def run_final_merge():
    logger = utils.setup_logger("Phase4")
    try:
        cfg = utils.load_config()["job_config"]
        db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]

        for coll_name in utils.get_target_collections(cfg):
            stage_name = f"{coll_name}_stage"
            if stage_name not in db.list_collection_names(): continue
            
            logger.info(f"開始原子合併: {stage_name} -> {coll_name}")
            db[stage_name].aggregate([{
                "$merge": {
                    "into": coll_name, "on": "_id",
                    "whenMatched": "keepExisting", "whenNotMatched": "insert"
                }
            }])
            db.drop_collection(stage_name)
            logger.info(f"集合 {coll_name} 合併成功。")
        return True
    except Exception as e:
        logger.error(f"Phase 4 失敗: {e}")
        return False
if __name__ == "__main__":
    run_final_merge()
