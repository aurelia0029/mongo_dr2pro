import datetime, os, subprocess
from pymongo import MongoClient
import utils

def run_evacuation():
    logger = utils.setup_logger("Phase1")
    try:
        cfg = utils.load_config()["job_config"]
        db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]
        colls = utils.get_matching_collections(db, utils.get_hour_prefixes(cfg))
        bak_dir = f"backups/bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
        os.makedirs(bak_dir, exist_ok=True)

        logger.info(f"開始備份 Production: {cfg['start_ts']} - {cfg['end_ts']}，共 {len(colls)} 個集合")
        for coll_name in colls:
            r = subprocess.run([
                "mongodump",
                f"--uri={cfg['prod_uri']}",
                f"--db={cfg['prod_db']}",
                f"--collection={coll_name}",
                f"--out={bak_dir}",
            ], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"mongodump 失敗: {r.stderr}")
            logger.info(f"集合 {coll_name} 備份至 {bak_dir}/")
        return True
    except Exception as e:
        logger.error(f"Phase 1 失敗: {e}")
        return False

if __name__ == "__main__":
    run_evacuation()
