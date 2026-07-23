import json, shutil, subprocess, tempfile
import utils

def run_restore():
    logger = utils.setup_logger("Phase3")
    try:
        cfg = utils.load_config()["job_config"]
        query_json = json.dumps({cfg["time_field"]: {"$gte": cfg["start_ts"], "$lt": cfg["end_ts"]}})

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

                logger.info(f"集合 {coll_name} 還原完成。")
            finally:
                shutil.rmtree(dump_dir, ignore_errors=True)

        return True
    except Exception as e:
        logger.error(f"Phase 3 失敗: {e}")
        return False

if __name__ == "__main__":
    run_restore()
