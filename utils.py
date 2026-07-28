import datetime, getpass, json, logging, os, sys
from pymongo import MongoClient

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
    start = datetime.datetime.strptime(cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(cfg["end_ts"],   "%Y%m%d%H")
    prefixes, curr = [], start
    while curr <= end:
        prefixes.append(f"{curr.strftime('%Y%m%d%H')}_{cfg['coll_prefix']}")
        curr += datetime.timedelta(hours=1)
    return prefixes

def get_matching_collections(db, prefixes):
    all_colls = set(db.list_collection_names())
    result = []
    for prefix in prefixes:
        result.extend(c for c in sorted(all_colls) if c.startswith(prefix))
    return result

def _build_uri(host, username, password):
    return f"mongodb://{username}:{password}@{host}/?authSource=admin"

def prompt_direction(base_cfg):
    """選擇搬移方向並確認，回傳 'dr_to_central' 或 'central_to_dr'。"""
    prod = base_cfg["prod_host"]
    dr   = base_cfg["dr_host"]
    options = {
        "1": ("dr_to_central", f"DR → Central  ({dr} → {prod})"),
        "2": ("central_to_dr", f"Central → DR  ({prod} → {dr})"),
    }
    while True:
        print("\n請選擇搬移方向：")
        for k, (_, label) in options.items():
            print(f"  [{k}] {label}")
        choice = input("\n請選擇 (1/2): ").strip()
        if choice not in options:
            print("請輸入 1 或 2")
            continue
        direction, label = options[choice]
        print(f"\n已選擇：{label}")
        confirm = input("確認？(y/n): ").strip().lower()
        if confirm == 'y':
            return direction
        print("重新選擇。\n")

def prompt_credentials_and_connect(base_cfg, direction):
    """帳密輸入，最多三次。回傳加入 src_*/dst_* 的 cfg。"""
    for attempt in range(1, 4):
        print(f"\nMongoDB 登入 ({attempt}/3)")
        username = input("使用者名稱: ").strip()
        password = getpass.getpass("密碼: ")
        prod_uri = _build_uri(base_cfg["prod_host"], username, password)
        dr_uri   = _build_uri(base_cfg["dr_host"],   username, password)
        try:
            MongoClient(prod_uri, serverSelectionTimeoutMS=5000)[base_cfg["prod_db"]].command("ping")
            MongoClient(dr_uri,   serverSelectionTimeoutMS=5000)[base_cfg["dr_db"]].command("ping")
            print("✅ 登入成功")
            cfg = {**base_cfg, "prod_uri": prod_uri, "dr_uri": dr_uri}
            if direction == "dr_to_central":
                cfg.update({"src_uri": dr_uri,   "src_db": base_cfg["dr_db"],
                            "dst_uri": prod_uri, "dst_db": base_cfg["prod_db"]})
            else:
                cfg.update({"src_uri": prod_uri, "src_db": base_cfg["prod_db"],
                            "dst_uri": dr_uri,   "dst_db": base_cfg["dr_db"]})
            return cfg
        except Exception as e:
            print(f"❌ 登入失敗: {e}")
    print("超過登入次數限制，結束程式。")
    sys.exit(1)

def prompt_time_range(cfg):
    """輸入起訖小時並讓使用者確認。回傳加入 start_ts/end_ts 的 cfg。"""
    while True:
        print()
        start_ts = input("起始小時 (YYYYMMDDHH，含): ").strip()
        end_ts   = input("結束小時 (YYYYMMDDHH，含): ").strip()
        try:
            start_dt = datetime.datetime.strptime(start_ts, "%Y%m%d%H")
            end_dt   = datetime.datetime.strptime(end_ts,   "%Y%m%d%H")
        except ValueError:
            print("格式錯誤，請輸入 YYYYMMDDHH（例如：2026071808）")
            continue
        if end_dt < start_dt:
            print("結束時間不能早於起始時間")
            continue
        temp_cfg = {**cfg, "start_ts": start_ts, "end_ts": end_ts}
        prefixes = get_hour_prefixes(temp_cfg)
        print(f"\n將處理以下 {len(prefixes)} 個小時的集合：")
        for p in prefixes:
            print(f"  {p}*")
        confirm = input("\n確認範圍？(y/n): ").strip().lower()
        if confirm == 'y':
            return temp_cfg
        print("重新輸入時間範圍。")

def get_runtime_cfg():
    """完整互動流程：載入設定 → 搬移方向 → 帳密登入 → 時間範圍確認。"""
    full_cfg = load_config()
    base_cfg = full_cfg["job_config"]
    direction = prompt_direction(base_cfg)
    cfg = prompt_credentials_and_connect(base_cfg, direction)
    cfg = prompt_time_range(cfg)
    cfg["data_schema"] = full_cfg["data_schema"]
    return cfg
