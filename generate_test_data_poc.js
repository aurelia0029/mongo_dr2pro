// generate_test_data_poc.js
// 用法（mongosh --eval 帶入參數後執行本檔案）：
//
// mongosh "mongodb://<host>:27017/mainDB" \
//   --eval 'var startHour="2026072711"; var endHour="2026072813"; \
//           var subTableSuffix=""; var docsPerColl=100; \
//           var statusLabel="VALID_DR_DATA";' \
//   generate_test_data_poc.js
//
// 參數說明：
//   startHour / endHour : YYYYMMDDHH，含頭尾（跟正式搬移的時間範圍一致）
//   subTableSuffix       : "" 代表不分表（產生 2026072711_encColl）
//                           "_1" 代表分表1（產生 2026072711_encColl_1）
//   docsPerColl          : 每個 collection 要塞幾筆
//   statusLabel          : 測試標記欄位，方便截圖辨識資料來源，
//                           正式環境的真實資料不會有這個欄位
//                           建議：DR 端塞 "VALID_DR_DATA"，Central 端塞 "CORRUPTED"（模擬遺失前的舊資料）

(function () {
    const DB_NAME = "mainDB";
    const COLL_PREFIX = "encColl";
    const HOUR_MS = 60 * 60 * 1000;
    const TW_OFFSET_MS = 8 * HOUR_MS;

    // 與 schema_check.json 的 data_schema 完全一致
    const REQUIRED_FIELDS = ["A","B","G","M","J","N","H1","H2","K1","K2","P","Q","R","S","O","W","BV","T","C","D","E","V","U","F","AE"];
    const TYPE_RULES = {
        A:"int", B:"int", G:"int", M:"str", J:"int", N:"str",
        H1:"int", H2:"int", K1:"int", K2:"int", P:"int", Q:"int",
        R:"int", S:"int", O:"str", W:"str", BV:"str", T:"str",
        C:"str", D:"str", E:"str", V:"str", U:"str", F:"str", AE:"int"
    };

    function log(msg) {
        const tw = new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei" });
        print("[" + tw + "] " + msg);
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

    function randInt(max = 100000) {
        return Math.floor(Math.random() * max);
    }

    function randStr(prefix, len = 8) {
        return prefix + "_" + Math.random().toString(36).slice(2, 2 + len);
    }

    function makeDoc(seq, hourStr, collName) {
        const doc = {};
        for (const field of REQUIRED_FIELDS) {
            doc[field] = TYPE_RULES[field] === "int" ? randInt() : randStr(field.toLowerCase());
        }
        // 以下為測試輔助欄位，非 schema 必填欄位，方便 POC 截圖辨識/驗證，正式資料不會有
        doc.status = typeof statusLabel !== "undefined" ? statusLabel : "TEST_DATA";
        doc._seq = seq;
        doc._src_hour = hourStr;
        doc._src_coll = collName;
        return doc;
    }

    // ---- 參數檢查 ----
    if (typeof startHour === "undefined" || typeof endHour === "undefined") {
        log("ERROR: 請透過 --eval 帶入 startHour / endHour");
        quit(1);
    }
    const _subSuffix = typeof subTableSuffix !== "undefined" ? subTableSuffix : "";
    const _docsPerColl = typeof docsPerColl !== "undefined" ? Number(docsPerColl) : 100;

    startHour = String(startHour);
    endHour = String(endHour);

    if (!isValidHourStr(startHour) || !isValidHourStr(endHour)) {
        log("ERROR: 日期格式錯誤，請使用 YYYYMMDDHH");
        quit(1);
    }

    const rangeStartMs = hourStrToTwMs(startHour);
    const rangeEndMs = hourStrToTwMs(endHour); // 這裡直接 <= 處理成含尾

    const dbMain = db.getSiblingDB(DB_NAME);

    log("=== POC 測試資料產生開始 ===");
    log("Range: " + startHour + " ~ " + endHour + "（含頭尾），分表後綴=" + (_subSuffix || "（無）") + "，每集合筆數=" + _docsPerColl);

    let totalColl = 0, totalDocs = 0;

    for (let t = rangeStartMs; t <= rangeEndMs; t += HOUR_MS) {
        const hourStr = twMsToHourStr(t);
        const collName = hourStr + "_" + COLL_PREFIX + _subSuffix;

        const docs = [];
        for (let i = 0; i < _docsPerColl; i++) {
            docs.push(makeDoc(i, hourStr, collName));
        }

        try {
            const res = dbMain.getCollection(collName).insertMany(docs, { ordered: false });
            const insertedCount = res.insertedIds ? Object.keys(res.insertedIds).length : docs.length;
            log(collName + " 已插入 " + insertedCount + " 筆");
            totalColl++;
            totalDocs += insertedCount;
        } catch (e) {
            log("ERROR: 插入 " + collName + " 失敗：" + e);
        }
    }

    log("=== 完成：共 " + totalColl + " 個 collection，總計 " + totalDocs + " 筆 ===");
})();
