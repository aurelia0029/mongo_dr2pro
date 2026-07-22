import json, shutil, subprocess, tempfile
from pymongo import MongoClient
import utils

def run_final_merge():
    logger = utils.setup_logger("Phase4")
    try:
        cfg = utils.load_config()["job_config"]
        query_json = json.dumps({cfg["time_field"]: {"$gte": cfg["start_ts"], "$lt": cfg["end_ts"]}})
        p_db = MongoClient(cfg["prod_uri"])[cfg["prod_db"]]

        for coll_name in utils.get_target_collections(cfg):
            dump_dir = tempfile.mkdtemp(prefix="dr_restore_")
            try:
                r = subprocess.run([
                    "mongodump",
                    f"--uri={cfg['dr_uri']}",
                    f"--db={cfg['dr_db']}",
                    f"--collection={coll_name}",
                    f"--query={query_json}",
                    f"--out={dump_dir}",
                ], capture_output=True, text=True)
                if r.returncode != 0:
                    raise RuntimeError(f"mongodump 失敗: {r.stderr}")

                r = subprocess.run([
                    "mongorestore",
                    f"--uri={cfg['prod_uri']}",
                    f"--nsFrom={cfg['dr_db']}.{coll_name}",
                    f"--nsTo={cfg['prod_db']}.{coll_name}",
                    "--drop",
                    dump_dir,
                ], capture_output=True, text=True)
                if r.returncode != 0:
                    raise RuntimeError(f"mongorestore 失敗: {r.stderr}")

                stage_name = f"{coll_name}_stage"
                if stage_name in p_db.list_collection_names():
                    p_db.drop_collection(stage_name)

                count = p_db[coll_name].count_documents({})
                logger.info(f"集合 {coll_name} 還原完成 ({count} 筆)，staging 已清除。")
            finally:
                shutil.rmtree(dump_dir, ignore_errors=True)

        return True
    except Exception as e:
        logger.error(f"Phase 4 失敗: {e}")
        return False

if __name__ == "__main__":
    run_final_merge()
