import datetime, getpass, json, logging, os, sys
from pymongo import MongoClient

def load_config():
    with open("schema_check.json", "r") as f:
        return json.load(f)

def setup_logger(phase_name):
    """Console-only logger. File logging is handled by open_session_log."""
    logger = logging.getLogger(phase_name)
    logger.setLevel(logging.INFO)
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'))
    logger.addHandler(sh)
    return logger

def open_session_log(log_name):
    """Add a timestamped FileHandler to the root logger. Returns (handler, log_path)."""
    os.makedirs("logs", exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = f"logs/{log_name}_{ts}.log"
    handler = logging.FileHandler(log_path, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    print(f"[日誌] 寫入 {log_path}")
    return handler, log_path

def close_session_log(handler):
    """Remove FileHandler from root logger and close the file."""
    logging.getLogger().removeHandler(handler)
    handler.close()

def get_hour_prefixes(cfg):
    start = datetime.datetime.strptime(cfg["start_ts"], "%Y%m%d%H")
    end   = datetime.datetime.strptime(cfg["end_ts"],   "%Y%m%d%H")
    prefixes, curr = [], start
    while curr <= end:
        prefixes.append(f"{curr.strftime('%Y%m%d%H')}_{cfg['coll_prefix']}")
        curr += datetime.timedelta(hours=1)
    return prefixes

def get_matching_collections(db, prefixes, subcoll_suffix=None):
    all_colls = set(db.list_collection_names())
    result = []
    for prefix in prefixes:
        if subcoll_suffix is None:
            result.extend(c for c in sorted(all_colls) if c.startswith(prefix))
        else:
            target = f"{prefix}_{subcoll_suffix}"
            if target in all_colls:
                result.append(target)
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

def prompt_subcoll_selection(cfg):
    """詢問搬移所有分表或單一分表。設定 cfg['subcoll_suffix']（None=所有，字串=單一）。"""
    prefixes = get_hour_prefixes(cfg)
    example = prefixes[0] if prefixes else f"(YYYYMMDDHH)_{cfg['coll_prefix']}"
    print(f"\n分表選擇：")
    print(f"  [0] 所有分表（{example}, {example}_1, {example}_2 ...）")
    print(f"  [N] 單一分表（輸入分表編號，例：1 → 只搬移 {example}_1）")
    while True:
        choice = input("\n請選擇（0=全部，或輸入分表編號）: ").strip()
        if choice == "0" or choice == "":
            cfg["subcoll_suffix"] = None
            print("已選擇：所有分表。")
            return cfg
        if choice.isdigit() and int(choice) > 0:
            cfg["subcoll_suffix"] = choice
            print(f"已選擇：分表 _{choice}（例：{example}_{choice}）")
            return cfg
        print("請輸入 0（全部）或正整數分表編號。")

def get_runtime_cfg():
    """完整互動流程：載入設定 → 搬移方向 → 帳密登入 → 時間範圍確認 → 分表選擇。"""
    full_cfg = load_config()
    base_cfg = full_cfg["job_config"]
    direction = prompt_direction(base_cfg)
    cfg = prompt_credentials_and_connect(base_cfg, direction)
    cfg = prompt_time_range(cfg)
    cfg = prompt_subcoll_selection(cfg)
    cfg["data_schema"] = full_cfg["data_schema"]
    return cfg
