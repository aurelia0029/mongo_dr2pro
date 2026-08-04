(function () {
    const DB_NAME = (typeof dbName !== "undefined") ? String(dbName) : "mainDB";
    const COLL_SUFFIX = "_encColl";
    const HOUR_MS = 60 * 60 * 1000;
    const TW_OFFSET_MS = 8 * HOUR_MS;
    const JSON_PREFIX = "JSON_LOG ";

    const INDEX_SPECS = [
        { keys: { B: 1, A: 1 }, options: { name: "B_1_A_1" } },
        { keys: { C: 1 },       options: { name: "C_1" } },
        { keys: { W: 1 },       options: { name: "W_1" } },
        { keys: { BV: 1 },      options: { name: "BV_1" } },
        { keys: { AE: 1 },      options: { name: "AE_1" } }
    ];

    function log(msg) {
        const tw = new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei" });
        print("[" + tw + "] " + msg);
    }

    function nowTwIso() {
        const ms = Date.now() + TW_OFFSET_MS;
        const d = new Date(ms);
        return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}T${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}:${String(d.getUTCSeconds()).padStart(2, "0")}+08:00`;
    }

    function emitJson(obj) {
        print(JSON_PREFIX + JSON.stringify(obj));
    }

    function isValidHourStr(s) {
        return /^\d{10}$/.test(s) && Number(s.slice(8, 10)) >= 0 && Number(s.slice(8, 10)) <= 23;
    }

    function hourStrToTwMs(s) {
        const y = Number(s.slice(0, 4));
        const m = Number(s.slice(4, 6)) - 1;
        const d = Number(s.slice(6, 8));
        const h = Number(s.slice(8, 10));
        return Date.UTC(y, m, d, h) - TW_OFFSET_MS;
    }

    function twMsToHourStr(ms) {
        const d = new Date(ms + TW_OFFSET_MS);
        return `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, "0")}${String(d.getUTCDate()).padStart(2, "0")}${String(d.getUTCHours()).padStart(2, "0")}`;
    }

    // 判斷一個 collection 名稱是否屬於某個小時前綴：
    // 完全等於前綴（無分表，如 2026072808_encColl），
    // 或是前綴 + "_" + 任意分表編號（如 2026072808_encColl_1、_2 ...）
    function matchesHourPrefix(collName, prefix) {
        return collName === prefix || collName.startsWith(prefix + "_");
    }

    function ensureIndexes(coll, specs, metrics) {
        const existingNames = coll.getIndexes().map(i => i.name);
        let created = 0, skipped = 0, failed = 0;

        for (const spec of specs) {
            const name = spec.options.name;
            const keys = spec.keys;
            const idxEntry = { name, keys, duration_ms: 0, success: false, action: "" };

            if (existingNames.includes(name)) {
                log(coll.getName() + " 已有索引 " + name + "，略過");
                idxEntry.action = "skipped";
                idxEntry.success = true;
                metrics.indexes.push(idxEntry);
                skipped++;
                continue;
            }

            const t0 = Date.now();

            try {
                log(coll.getName() + " 建立索引 " + name + " keys=" + JSON.stringify(keys));
                coll.createIndex(keys, spec.options || {});

                idxEntry.action = "created";
                idxEntry.success = true;
                idxEntry.duration_ms = Date.now() - t0;
                metrics.indexes.push(idxEntry);
                created++;
            } catch (e) {
                log(coll.getName() + " 建立索引失敗 " + name + " | " + e);

                idxEntry.action = "failed";
                idxEntry.success = false;
                idxEntry.duration_ms = Date.now() - t0;
                idxEntry.error = String(e);
                metrics.indexes.push(idxEntry);
                failed++;
            }
        }

        metrics.summary = {
            total: specs.length,
            success: created + skipped,
            failed
        };

        log(coll.getName() + " Index summary: created=" + created + ", skipped=" + skipped + ", failed=" + failed);
    }

    if (typeof startHour === "undefined" || typeof endHour === "undefined") {
        log("ERROR: Missing startHour or endHour");
        quit(1);
    }

    startHour = String(startHour);
    endHour = String(endHour);

    if (!isValidHourStr(startHour) || !isValidHourStr(endHour)) {
        log("ERROR: 日期格式錯誤，請使用 YYYYMMDDHH，例如 2026050318 2026050400");
        quit(1);
    }

    const startMsAll = Date.now();
    const rangeStartMs = hourStrToTwMs(startHour);
    const rangeEndMs = hourStrToTwMs(endHour);

    if (rangeStartMs >= rangeEndMs) {
        log("ERROR: startHour 必須小於 endHour");
        quit(1);
    }

    const dbMain = db.getSiblingDB(DB_NAME);

    log("=== Manual range index builder start ===");
    log("Range: " + startHour + " <= hour < " + endHour);

    // 一次取得所有 collection 名稱，避免每小時都重新查詢一次
    const allCollNames = dbMain.getCollectionNames();

    for (let t = rangeStartMs; t < rangeEndMs; t += HOUR_MS) {
        const hourStr = twMsToHourStr(t);
        const prefix = hourStr + COLL_SUFFIX;

        // 找出這個小時底下所有相符的 collection：
        // 不分表（prefix 本身）、或任意分表編號（prefix_1, prefix_2 ...）都接受
        const matchedNames = allCollNames.filter(name => matchesHourPrefix(name, prefix));

        if (matchedNames.length === 0) {
            log(prefix + "（含分表）沒有符合的 Collection，跳過");

            const metrics = {
                task: "manual range build index",
                target: { db: DB_NAME, collection_prefix: prefix },
                start_ts: nowTwIso(),
                end_ts: nowTwIso(),
                duration_ms: 0,
                indexes: [],
                summary: { total: INDEX_SPECS.length, success: 0, failed: 0 }
            };
            emitJson(metrics);
            continue;
        }

        log(prefix + "（含分表）共找到 " + matchedNames.length + " 個 collection：" + matchedNames.join(", "));

        for (const collName of matchedNames) {
            const metrics = {
                task: "manual range build index",
                target: { db: DB_NAME, collection: collName },
                start_ts: nowTwIso(),
                end_ts: "",
                duration_ms: 0,
                indexes: [],
                summary: { total: 0, success: 0, failed: 0 }
            };

            const collStartMs = Date.now();
            log("Target collection: " + DB_NAME + "." + collName);

            try {
                const coll = dbMain.getCollection(collName);
                ensureIndexes(coll, INDEX_SPECS, metrics);
            } catch (e) {
                log("ERROR: 處理 " + collName + " 失敗：" + e);
                metrics.error = String(e);
                metrics.summary.failed = (metrics.summary.failed || 0) + 1;
            } finally {
                metrics.end_ts = nowTwIso();
                metrics.duration_ms = Date.now() - collStartMs;
                emitJson(metrics);
            }
        }
    }

    log("=== Manual range index builder done ===");
    log("Total duration_ms=" + (Date.now() - startMsAll));
})();
