import datetime, json, os, subprocess
import utils

def run_evacuation():
    logger = utils.setup_logger("Phase1")
    try:
        cfg = utils.load_config()["job_config"]
        query_json = json.dumps({cfg["time_field"]: {"$gte": cfg["start_ts"], "$lt": cfg["end_ts"]}})
        bak_dir = f"backups/bak_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
        os.makedirs(bak_dir, exist_ok=True)

        logger.info(f"開始備份 Production 區間資料: {cfg['start_ts']} - {cfg['end_ts']}")
        for coll_name in utils.get_target_collections(cfg):
            r = subprocess.run([
                "mongodump",
                f"--uri={cfg['prod_uri']}",
                f"--db={cfg['prod_db']}",
                f"--collection={coll_name}",
                f"--query={query_json}",
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
