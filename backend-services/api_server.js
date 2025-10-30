const express = require('express');
const cors = require('cors');
const Database = require('better-sqlite3'); // <-- เปลี่ยนมาใช้ better-sqlite3

const app = express();
const PORT = 3001; // กำหนด Port สำหรับ API Server ของเรา

// อนุญาตให้ Dashboard (ที่รันบน Port อื่น) สามารถเรียกใช้ API นี้ได้
app.use(cors());

// --- (แก้ไข) เชื่อมต่อกับฐานข้อมูลสำรองด้วย better-sqlite3 ---
let db;
try {
    // เปิดการเชื่อมต่อในโหมด "อ่านอย่างเดียว" เพื่อความปลอดภัย
    db = new Database('./local_backup.db', { readonly: true });
    console.log("✅ API Server connected to local SQLite database.");
    db.pragma('journal_mode = WAL');
} catch (err) {
    console.error("❌ API Server could not connect to local SQLite database", err.message);
    process.exit(1); // ออกจากโปรแกรมถ้าเชื่อมต่อฐานข้อมูลไม่ได้
}
// -----------------------------------------------------------

// สร้าง Endpoint สำหรับดึงข้อมูล visitors
app.get('/visitors', (req, res) => {
    try {
        const stmt = db.prepare("SELECT * FROM visitors ORDER BY created_at DESC");
        const rows = stmt.all(); // .all() จะดึงข้อมูลทั้งหมดออกมาทันที
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// สร้าง Endpoint สำหรับดึงข้อมูล station_visits
app.get('/station_visits', (req, res) => {
    try {
        const stmt = db.prepare("SELECT * FROM station_visits ORDER BY created_at DESC");
        const rows = stmt.all();
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Local API server for dashboard is running at http://localhost:${PORT}`);
    console.log("   Ready to serve data from local_backup.db in case of emergency.");
});
