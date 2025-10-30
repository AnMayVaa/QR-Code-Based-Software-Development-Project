const { createClient } = require('@supabase/supabase-js');
const Database = require('better-sqlite3');

const SUPABASE_URL = 'https://xeejnzrxxdzkkhcjbuce.supabase.co';
const SUPABASE_SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhlZWpuenJ4eGR6a2toY2pidWNlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0NDQ4OTcsImV4cCI6MjA3MzAyMDg5N30.uc57dQCH1kNKVg3gHagfnLdxQD3G6yJmINMIXu5Frow';
const SYNC_INTERVAL = 5000; // ทำงานเร็วขึ้นเป็นทุก 5 วินาที
const BATCH_SIZE = 200;     // (ใหม่) ขนาดของแต่ละล็อต

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
let db;
try {
    db = new Database('./local_backup.db');
    db.pragma('journal_mode = WAL');
} catch (err) { /* ... */ }

// (แก้ไข) เตรียมคำสั่ง SQL ให้มี LIMIT
const selectVisitorsStmt = db.prepare(`SELECT * FROM visitors WHERE synced_to_supabase = 0 LIMIT ${BATCH_SIZE}`);
const selectVisitsStmt = db.prepare(`SELECT * FROM station_visits WHERE synced_to_supabase = 0 LIMIT ${BATCH_SIZE}`);
const updateVisitorsStmt = db.prepare(`UPDATE visitors SET synced_to_supabase = 1 WHERE token = ?`);
const updateVisitsStmt = db.prepare(`UPDATE station_visits SET synced_to_supabase = 1 WHERE id = ?`);

async function syncTable(tableName, selectStmt, updateStmt, primaryKey) {
    const unsyncedRows = selectStmt.all();
    if (unsyncedRows.length === 0) return;

    console.log(`[${tableName}] Found ${unsyncedRows.length} unsynced records. Syncing batch...`);
    const dataToSync = unsyncedRows.map(({ synced_to_supabase, ...rest }) => rest);
    const { error } = await supabase.from(tableName).upsert(dataToSync, { onConflict: primaryKey });

    if (error) {
        console.error(`⚠️ [${tableName}] Supabase sync failed:`, error.message);
        return;
    }

    const updateTransaction = db.transaction((rows) => {
        for (const row of rows) updateStmt.run(row[primaryKey]);
    });
    updateTransaction(unsyncedRows);
    
    console.log(`✅ [${tableName}] Successfully synced ${unsyncedRows.length} records.`);
}

async function main() {
    console.log("🚀 Sync service started (Batch Mode)...");
    setInterval(async () => {
        try {
            await syncTable('visitors', selectVisitorsStmt, updateVisitorsStmt, 'token');
            await syncTable('station_visits', selectVisitsStmt, updateVisitsStmt, 'id');
        } catch (e) {
            console.error("An error occurred during the sync cycle:", e);
        }
    }, SYNC_INTERVAL);
}

main();