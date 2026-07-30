import shutil, subprocess, tempfile
from pymongo import MongoClient
import utils
from audit import run_audit

def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def show_transfer_info(runtime_cfg):
    """Display source counts/sizes and destination disk space. Called by runner.py before timer starts."""
    src_db = MongoClient(runtime_cfg["src_uri"])[runtime_cfg["src_db"]]
    colls = utils.get_matching_collections(src_db, utils.get_hour_prefixes(runtime_cfg),
                                           runtime_cfg.get("subcoll_suffix"))
    dst_db = MongoClient(runtime_cfg["dst_uri"])[runtime_cfg["dst_db"]]
    dst_coll_names = set(dst_db.list_collection_names())

    print(f"\n欲搬移資料（來源：[{runtime_cfg['src_db']}]）：")
    print(f"  {'集合名稱':<35} {'筆數':>8}  {'大小':>10}")
    print("  " + "─" * 58)
    for coll_name in colls:
        cnt = src_db[coll_name].count_documents({})
        try:
            size = src_db.command("collStats", coll_name).get("storageSize", 0)
            size_str = _fmt_bytes(size)
        except Exception:
            size_str = "N/A"
        print(f"  {coll_name:<35} {cnt:>8}  {size_str:>10}")

    print(f"\n目的端覆蓋情況（[{runtime_cfg['dst_db']}]）：")
    print(f"  {'集合名稱':<35} {'目前筆數':>8}")
    print("  " + "─" * 47)
    for coll_name in colls:
        if coll_name in dst_coll_names:
            cnt = dst_db[coll_name].count_documents({})
            print(f"  {coll_name:<35} {cnt:>8}")
        else:
            print(f"  {coll_name:<35} {'(不存在)':>8}")

    print(f"\n目的端磁碟空間（/var/lib/mongo）：")
    try:
        r = subprocess.run(["df", "-h", "/var/lib/mongo"], capture_output=True, text=True)
        if r.returncode == 0:
            lines = r.stdout.strip().splitlines()
            for line in lines:
                print(f"  {line}")
        else:
            print("  （無法取得磁碟資訊）")
    except Exception:
        print("  （無法取得磁碟資訊）")

def run_restore(runtime_cfg, auto_confirm=False, skip_drop_confirm=False):
    """
    auto_confirm=True       — no prompts at all (validate_scenarios)
    skip_drop_confirm=False — standalone: runs audit → shows transfer info → asks y/n
    skip_drop_confirm=True  — runner.py: runs audit → asks y/n (transfer info already shown before timer)
    """
    logger = utils.setup_logger("Phase2")
    try:
        logger.info("=== 審計來源資料 ===")
        run_audit(runtime_cfg)
        logger.info("=== 審計完成 ===")

        src_db = MongoClient(runtime_cfg["src_uri"])[runtime_cfg["src_db"]]
        colls = utils.get_matching_collections(src_db, utils.get_hour_prefixes(runtime_cfg),
                                               runtime_cfg.get("subcoll_suffix"))

        if not auto_confirm:
            if not skip_drop_confirm:
                show_transfer_info(runtime_cfg)
            confirm = input("\n審計完成，確認執行 drop 並還原？(y/n): ").strip().lower()
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

                print(f"\n[mongorestore] {coll_name}")
                r = subprocess.run([
                    "mongorestore",
                    f"--uri={runtime_cfg['dst_uri']}",
                    f"--nsFrom={runtime_cfg['src_db']}.{coll_name}",
                    f"--nsTo={runtime_cfg['dst_db']}.{coll_name}",
                    "--drop",
                    dump_dir,
                ])
                if r.returncode != 0:
                    raise RuntimeError(f"mongorestore 失敗（exitcode={r.returncode}）")

                logger.info(f"集合 {coll_name} 還原完成。")
            finally:
                shutil.rmtree(dump_dir, ignore_errors=True)

        # Post-restore count verification
        dst_db = MongoClient(runtime_cfg["dst_uri"])[runtime_cfg["dst_db"]]
        all_match = True
        print(f"\n=== 搬移後筆數核對 ===")
        print(f"  {'集合名稱':<35} {'來源筆數':>8}  {'目的筆數':>8}  結果")
        print("  " + "─" * 65)
        for coll_name in colls:
            src_cnt = src_db[coll_name].count_documents({})
            dst_cnt = dst_db[coll_name].count_documents({})
            match = src_cnt == dst_cnt
            if not match:
                all_match = False
            status = "✅ 一致" if match else "❌ 不一致"
            print(f"  {coll_name:<35} {src_cnt:>8}  {dst_cnt:>8}  {status}")
        total_src = sum(src_db[c].count_documents({}) for c in colls)
        total_dst = sum(dst_db[c].count_documents({}) for c in colls)
        print("  " + "─" * 65)
        print(f"  {'合計':<35} {total_src:>8}  {total_dst:>8}  {'✅ 全部一致' if all_match else '❌ 有差異'}")
        logger.info(f"筆數核對：來源合計 {total_src}，目的合計 {total_dst}，{'一致' if all_match else '不一致'}")

        return all_match
    except Exception as e:
        logger.error(f"Phase 2 還原失敗: {e}")
        return False

if __name__ == "__main__":
    runtime_cfg = utils.get_runtime_cfg()
    log_handler, log_path = utils.open_session_log("restore")
    try:
        run_restore(runtime_cfg)
    finally:
        utils.close_session_log(log_handler)
