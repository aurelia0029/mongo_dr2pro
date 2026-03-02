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

def get_target_collections(cfg):
    colls = set()
    curr = cfg["start_ts"]
    while curr < cfg["end_ts"]:
        dt = datetime.datetime.fromtimestamp(curr / 1000.0)
        colls.add(dt.strftime(f"%Y%m%d%H_{cfg['coll_prefix']}"))
        curr += 3600000 
    return sorted(list(colls))

def get_query(cfg):
    # 這確保了不論 start/end 是不是整點，操作都只鎖定在此區間
    return {cfg["time_field"]: {"$gte": cfg["start_ts"], "$lt": cfg["end_ts"]}}
