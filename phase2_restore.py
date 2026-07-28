import shutil, subprocess, tempfile
from pymongo import MongoClient
import utils
from audit import run_audit

def run_restore(runtime_cfg, auto_confirm=False):
    logger = utils.setup_logger("Phase2")
    try:
        logger.info("=== 審計來源資料 ===")
        run_audit(runtime_cfg)
        logger.info("=== 審計完成，開始還原 ===")

        src_db = MongoClient(runtime_cfg["src_uri"])[runtime_cfg["src_db"]]
        colls = utils.get_matching_collections(src_db, utils.get_hour_prefixes(runtime_cfg))

        dst_db = MongoClient(runtime_cfg["dst_uri"])[runtime_cfg["dst_db"]]
        dst_coll_names = set(dst_db.list_collection_names())

        print(f"\n以下目的端集合將被 drop 並從來源端覆蓋還原 [{runtime_cfg['dst_db']}]：")
        print(f"  {'集合名稱':<35} {'目前筆數':>8}")
        print("  " + "─" * 47)
        for coll_name in colls:
            if coll_name in dst_coll_names:
                cnt = dst_db[coll_name].count_documents({})
                print(f"  {coll_name:<35} {cnt:>8}")
            else:
                print(f"  {coll_name:<35} {'(不存在)':>8}")

        if not auto_confirm:
            confirm = input("\n確認執行 drop 並還原？(y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("使用者取消操作。")
                return False

        logger.info(f"還原 [{runtime_cfg['src_db']}] → [{runtime_cfg['dst_db']}]，共 {len(colls)} 個集合")
        for coll_name in colls:
            dump_dir = tempfile.mkdtemp(prefix="restore_")
            try:
                r = subprocess.run([
                    "mongodump",
                    f"--uri={runtime_cfg['src_uri']}",
                    f"--db={runtime_cfg['src_db']}",
                    f"--collection={coll_name}",
                    f"--out={dump_dir}",
                ], capture_output=True, text=True)
                if r.returncode != 0:
                    raise RuntimeError(f"mongodump 失敗: {r.stderr}")

                r = subprocess.run([
                    "mongorestore",
                    f"--uri={runtime_cfg['dst_uri']}",
                    f"--nsFrom={runtime_cfg['src_db']}.{coll_name}",
                    f"--nsTo={runtime_cfg['dst_db']}.{coll_name}",
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
        logger.error(f"Phase 2 還原失敗: {e}")
        return False

if __name__ == "__main__":
    run_restore(utils.get_runtime_cfg())
