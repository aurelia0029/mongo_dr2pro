import datetime, json, logging, os

def load_config():
    with open("schema_check.json", "r") as f:
        return json.load(f)

def setup_logger(phase_name):
    if not os.path.exists("logs"): os.makedirs("logs")
    log_filename = f"logs/recovery_{datetime.datetime.now().strftime('%Y%m%d')}.log"
    logger = logging.getLogger(phase_name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')
        fh = logging.FileHandler(log_filename, encoding='utf-8'); fh.setFormatter(formatter)
        sh = logging.StreamHandler(); sh.setFormatter(formatter)
        logger.addHandler(fh); logger.addHandler(sh)
    return logger

def get_hour_prefixes(cfg):
    """回傳每個目標小時的 collection 前綴，例如 ['2026071808_encColl', '2026071809_encColl']"""
    start = datetime.datetime.strptime(cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(cfg["end_ts"],   "%Y%m%d%H")
    prefixes, curr = [], start
    while curr <= end:
        prefixes.append(f"{curr.strftime('%Y%m%d%H')}_{cfg['coll_prefix']}")
        curr += datetime.timedelta(hours=1)
    return prefixes

def get_matching_collections(db, prefixes):
    """回傳 db 中所有以任一 prefix 開頭的 collection 名稱（已排序）"""
    all_colls = set(db.list_collection_names())
    result = []
    for prefix in prefixes:
        result.extend(c for c in sorted(all_colls) if c.startswith(prefix))
    return result
