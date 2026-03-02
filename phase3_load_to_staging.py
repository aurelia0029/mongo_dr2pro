from pymongo import MongoClient, InsertOne
import utils

def run_staging():
    logger = utils.setup_logger("Phase3")
    try:
        cfg = utils.load_config()["job_config"]
        p_db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]
        d_db = MongoClient(cfg["dr_uri"])[cfg["dr_db"]]
        query = utils.get_query(cfg)

        for coll_name in utils.get_target_collections(cfg):
            stage_name = f"{coll_name}_stage"
            p_db.drop_collection(stage_name)
            
            cursor = d_db[coll_name].find(query)
            buffer, count = [], 0
            for doc in cursor:
                buffer.append(InsertOne(doc))
                count += 1
                if len(buffer) >= 1000:
                    p_db[stage_name].bulk_write(buffer); buffer = []
            if buffer: p_db[stage_name].bulk_write(buffer)
            
            # 建立 _id 索引 (不帶 unique=True)
            p_db[stage_name].create_index([("_id", 1)])
            logger.info(f"搬運完成: {coll_name} -> {stage_name} ({count} 筆)")
        return True
    except Exception as e:
        logger.error(f"Phase 3 失敗: {e}")
        return False
if __name__ == "__main__":
    run_staging()
