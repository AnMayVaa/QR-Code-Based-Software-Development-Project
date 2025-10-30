import mqtt from 'mqtt';

// --- การตั้งค่า Broker และ Topic ---
// ตรวจสอบให้แน่ใจว่าคุณเลือกใช้ Address ที่ถูกต้อง

// สำหรับทดสอบใน Local
const BROKER_ADDRESS = 'ws://192.168.106.166:8081'; // <-- เข้าประตู 8081

// สำหรับใช้งานจริงผ่าน Cloud
// const BROKER_ADDRESS = 'ws://broker.hivemq.com:8000/mqtt'; 

// (สำคัญ) Topic ต้องตรงกับ listener.js
const TOPIC = 'openhouse/qrscan';
// -----------------------------------------------------------------

const client = mqtt.connect(BROKER_ADDRESS, {
    connectTimeout: 4000 
});

client.on('connect', () => {
  console.log(`✅ MQTT Client connected to broker at ${BROKER_ADDRESS}`);
});

client.on('error', (err) => {
    console.error('MQTT Connection error:', err.message);
    client.end();
});

// --- ฟังก์ชันสำหรับส่งข้อมูลการลงทะเบียน ---
const publishRegisterEvent = (payload) => {
    if (!client.connected) {
        console.error('MQTT client is not connected.');
        alert('Error: ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้');
        return;
    }
    const message = JSON.stringify(payload);
    client.publish(TOPIC, message, (err) => {
        if (err) {
            console.error('MQTT publish error:', err);
            alert('เกิดข้อผิดพลาดในการส่งข้อมูล');
        } else {
            console.log('Published registration event:', message);
            alert(`ส่งข้อมูลลงทะเบียนสำหรับ Token: ${payload.token} เรียบร้อยแล้ว!`);
        }
    });
};

// --- (สำคัญ) บรรทัดนี้คือการทำให้ฟังก์ชันพร้อมใช้งานสำหรับไฟล์อื่น ---
export { publishRegisterEvent };