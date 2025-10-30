const mqtt = require('mqtt');
const Database = require('better-sqlite3');

// --- การตั้งค่า ---
// เลือก Broker ที่ต้องการใช้งานโดยการลบ Comment (//) ออกจากบรรทัดที่ต้องการ
//const BROKER_ADDRESS = 'mqtt://broker.hivemq.com'; // สำหรับใช้งานจริงผ่าน Cloud
const BROKER_ADDRESS = 'ws://192.168.106.166:8081';   // สำหรับทดสอบใน Local Network
const TOPIC = 'openhouse/qrscan';
const PROCESS_INTERVAL = 1000; // Worker ทำงานทุก 1 วินาที
// -----------------------------------------------------------------

// --- ส่วนที่ 1: ตั้งค่าฐานข้อมูล (ใช้ better-sqlite3) ---
let db;
try {
    db = new Database('./local_backup.db');
    console.log("✅ Database connection established using better-sqlite3.");
    db.pragma('journal_mode = WAL');
    db.exec(`
        CREATE TABLE IF NOT EXISTS visitors (
            token TEXT PRIMARY KEY, created_at TEXT, fullname TEXT, age INTEGER,
            reward_claimed_at TEXT, registered_at TEXT,
            gender TEXT, school TEXT, email TEXT, phone TEXT,
            synced_to_supabase INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS station_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, token TEXT,
            station_id TEXT, check_in_time TEXT, check_out_time TEXT,
            synced_to_supabase INTEGER DEFAULT 0
        );
    `);
    console.log("✅ Tables initialized successfully.");
} catch (err) {
    console.error("❌ FATAL: Could not initialize database", err.message);
    process.exit(1);
}
// -----------------------------------------------------------------


// --- ส่วนที่ 2: สถาปัตยกรรม "Queue-Worker" ---
let commandQueue = []; // คิวสำหรับพัก "คำสั่ง" ที่จะทำงานกับ DB

// เตรียมคำสั่งทั้งหมดไว้ล่วงหน้าเพื่อประสิทธิภาพสูงสุด
const statementMap = {
    insertVisitor: db.prepare(`INSERT INTO visitors (token, created_at) VALUES (?, ?) ON CONFLICT(token) DO NOTHING`),
    insertVisit: db.prepare(`INSERT INTO station_visits (token, station_id, check_in_time, created_at) VALUES (?, ?, ?, ?)`),
    updateVisit: db.prepare(`UPDATE station_visits SET check_out_time = ?, synced_to_supabase = 0 WHERE token = ? AND station_id = ? AND check_out_time IS NULL`),
    registerVisitor: db.prepare(`UPDATE visitors SET fullname = ?, age = ?, gender = ?, school = ?, email = ?, phone = ?, registered_at = ?, reward_claimed_at = ?, synced_to_supabase = 0 WHERE token = ?`)
};

// "Worker" ที่จะรันคำสั่งทั้งหมดในคิวในครั้งเดียว (Transaction)
const processCommandQueue = db.transaction(() => {
    if (commandQueue.length === 0) return;

    const commandsToRun = commandQueue.splice(0, commandQueue.length); // หยิบงานทั้งหมดออกจากคิว
    console.log(`\n⚙️ Worker executing transaction for ${commandsToRun.length} commands...`);
    
    for (const cmd of commandsToRun) {
        try {
            const info = statementMap[cmd.type].run(...cmd.params);
            console.log(`[DEBUG] Ran ${cmd.type} for ${cmd.params[0]}. Changes: ${info.changes}`);
        } catch (e) {
            console.error(`[FAIL] Failed to execute command: ${cmd.type}`, e);
        }
    }
    console.log(`✅ Transaction finished.`);
});

// ตั้งเวลาให้ Worker ทำงาน
setInterval(processCommandQueue, PROCESS_INTERVAL);
// -----------------------------------------------------------------


// --- ส่วนที่ 3: MQTT Listener ---
const mqttClient = mqtt.connect(BROKER_ADDRESS);

function formatDateTimeSortable(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

mqttClient.on('connect', () => {
  console.log(`✅ MQTT Listener connected to Broker`);
  mqttClient.subscribe(TOPIC, (err) => {
    if (!err) console.log(`👂 Subscribed to topic: ${TOPIC}`);
  });
});

// Listener ทำหน้าที่แค่วาง "คำสั่ง" ลงในคิว
mqttClient.on('message', (topic, message) => {
    try {
        const payload = JSON.parse(message.toString());
        console.log(`📥 Queuing commands for token ${payload.token}`);
        
        const eventTime = new Date(payload.epoch * 1000);
        const eventTimeSortable = formatDateTimeSortable(eventTime);
        const { token, location, check, fullname, age, gender, school, email, phone, eventType } = payload;

        if (check === 1) {
            commandQueue.push({ type: 'insertVisitor', params: [token, eventTimeSortable] });
            commandQueue.push({ type: 'insertVisit', params: [token, location, eventTimeSortable, eventTimeSortable] });
        } else if (check === 0) {
            commandQueue.push({ type: 'updateVisit', params: [eventTimeSortable, token, location] });
        } else if (eventType === 'register') {
            commandQueue.push({ type: 'registerVisitor', params: [fullname, age, gender, school, email, phone, eventTimeSortable, eventTimeSortable, token] });
        }
    } catch (e) {
        console.error(`Error processing message: ${message.toString()}`, e.message);
    }
});