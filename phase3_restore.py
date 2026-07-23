import shutil, subprocess, tempfile
from pymongo import MongoClient
import utils

def run_restore():
    logger = utils.setup_logger("Phase3")
    try:
        cfg = utils.load_config()["job_config"]
        d_db = MongoClient(cfg["dr_uri"])[cfg["dr_db"]]
        colls = utils.get_matching_collections(d_db, utils.get_hour_prefixes(cfg))

        logger.info(f"還原區間: {cfg['start_ts']} - {cfg['end_ts']}，共 {len(colls)} 個集合")
        for coll_name in colls:
            dump_dir = tempfile.mkdtemp(prefix="dr_restore_")
            try:
                r = subprocess.run([
                    "mongodump",
                    f"--uri={cfg['dr_uri']}",
                    f"--db={cfg['dr_db']}",
                    f"--collection={coll_name}",
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
