import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { supabase } from './supabaseClient';
import { Html5QrcodeScanner } from 'html5-qrcode';
import { useBarcodeScanner } from './useBarcodeScanner';

import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// --- (ใหม่) สวิตช์สำหรับเลือกแหล่งข้อมูล ---
// - ตั้งเป็น false เพื่อใช้ Supabase (มี Real-time)
// - ตั้งเป็น true เพื่อใช้ Local API Server (สำหรับตอนเน็ตล่ม)
const USE_LOCAL_API = false; // <== เปลี่ยนค่านี้เพื่อสลับโหมด
// ------------------------------------------

const LOCAL_API_URL = 'http://localhost:3001';
const REQUIRED_STATIONS = ['network', 'programming', 'electricity'];
// -----------------------------------------------------------------
// ... (โค้ดส่วน Components ย่อยทั้งหมดเหมือนเดิม) ...
const StatCard = ({ title, value, unit }) => (
    <div className="stat-card">
        <div className="stat-value">{value}</div>
        <div className="stat-title">{title} {unit && <span className="stat-unit">({unit})</span>}</div>
    </div>
);
const VisitorRow = ({ visitor, visits, onRowClick }) => {
    const { status, progress, completedCount } = useMemo(() => {
        const completedStations = new Set(visits.filter(v => v.check_out_time).map(v => v.station_id));
        const progress = Math.round((completedStations.size / REQUIRED_STATIONS.length) * 100);
        let status = 'กำลังร่วมกิจกรรม';
        if (visitor.registered_at) status = 'ลงทะเบียนเสร็จสิ้น';
        else if (visitor.reward_claimed_at) status = 'รับรางวัลแล้ว';
        else if (progress === 100) status = 'ผ่านทุกฐาน';
        return { status, progress, completedCount: completedStations.size };
    }, [visitor, visits]);
    return (
        <tr onClick={() => onRowClick(visitor.token)}>
            <td>{visitor.token}</td>
            <td>
                <div className="progress-bar"><div className="progress-bar-fill" style={{ width: `${progress}%` }}>{progress}%</div></div>
            </td>
            <td>{completedCount} / {REQUIRED_STATIONS.length}</td>
            <td className={`status-${status.replace(/\s/g, '-')}`}>{status}</td>
        </tr>
    );
};
const VisitorDetailModal = ({ visitor, visits, onClose }) => {
    if (!visitor) return null;
    const completedStations = new Set(visits.filter(v => v.check_out_time).map(v => v.station_id));
    const progress = Math.round((completedStations.size / REQUIRED_STATIONS.length) * 100);
    let status = 'กำลังร่วมกิจกรรม';
    if (visitor.registered_at) status = 'ลงทะเบียนเสร็จสิ้น';
    else if (visitor.reward_claimed_at) status = 'รับรางวัลแล้ว';
    else if (progress === 100) status = 'ผ่านทุกฐาน';
    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button onClick={onClose} className="modal-close-btn">&times;</button>
                <h2>รายละเอียด: {visitor.token}</h2>
                {visitor.fullname && <p><strong>ชื่อ-สกุล:</strong> {visitor.fullname} (อายุ {visitor.age} ปี)</p>}
                <p><strong>สถานะปัจจุบัน:</strong> <span className={`status-text status-${status.replace(/\s/g, '-')}`}>{status}</span></p>
                <div className="progress-bar"><div className="progress-bar-fill" style={{ width: `${progress}%` }}>{progress}%</div></div>
                <h4>ประวัติการเข้าชมสถานี:</h4>
                <ul className="visit-history">
                    {visits.sort((a,b) => new Date(b.created_at) - new Date(a.created_at)).map(visit => (
                        <li key={visit.id}>
                            <strong>{visit.station_id}</strong>
                            <div>Check-in: {new Date(visit.check_in_time).toLocaleTimeString('th-TH')}</div>
                            {visit.check_out_time ? 
                                <div>Check-out: {new Date(visit.check_out_time).toLocaleTimeString('th-TH')}</div> : 
                                <div className="status-active">ยังอยู่ในสถานี</div>
                            }
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
};
const StationVisitorsModal = ({ station, visitors, onClose }) => {
    if (!station) return null;
    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button onClick={onClose} className="modal-close-btn">&times;</button>
                <h2>ผู้เข้าร่วมในฐาน: {station} ({visitors.length} คน)</h2>
                <div className="visitor-tags-list">
                    {visitors.map(token => <span key={token} className="visitor-tag">{token}</span>)}
                </div>
            </div>
        </div>
    );
};
const NotFoundModal = ({ token, onClose }) => {
    if (!token) return null;
    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button onClick={onClose} className="modal-close-btn">&times;</button>
                <h2>ไม่พบข้อมูล</h2>
                <p>ไม่พบผู้เข้าร่วมสำหรับ Token ID ที่สแกนได้:</p>
                <div className="not-found-token">{token}</div>
            </div>
        </div>
    );
};
const VisitorLookup = ({ onVisitorFound }) => {
    const [isScanning, setIsScanning] = useState(false);
    useEffect(() => {
        if (!isScanning) return;
        const scanner = new Html5QrcodeScanner(
            'qr-reader', { fps: 30, qrbox: { width: 250, height: 250 }, experimentalFeatures: { useBarCodeDetectorIfSupported: true } }, false
        );
        const onScanSuccess = (decodedText) => {
            scanner.clear().catch(() => {});
            setIsScanning(false);
            onVisitorFound(decodedText);
        };
        scanner.render(onScanSuccess, () => {});
        return () => { if (scanner && scanner.getState() !== "STOPPED") scanner.clear().catch(() => {}); };
    }, [isScanning, onVisitorFound]);
    return (
        <div className="card">
            <h2>ค้นหา / ตรวจสอบสถานะ</h2>
            <button onClick={() => setIsScanning(p => !p)} className="scan-btn">
                {isScanning ? 'ปิดกล้องสแกน' : '📷 เปิดกล้องสแกน QR Code'}
            </button>
            <div className="scanner-container">
                {isScanning && <div id="qr-reader"></div>}
            </div>
        </div>
    );
};


// --- Component หลัก ---
function App() {
  // --- State ทั้งหมดเหมือนเดิม ---
  const [visitors, setVisitors] = useState([]);
  const [visits, setVisits] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedToken, setSelectedToken] = useState(null);
  const [viewingStation, setViewingStation] = useState(null);
  const [notFoundToken, setNotFoundToken] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString('th-TH'));
  const [status, setStatus] = useState('กำลังเชื่อมต่อ...');

  // --- useEffect สำหรับนาฬิกา เหมือนเดิม ---
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date().toLocaleTimeString('th-TH')), 1000);
    return () => clearInterval(timer);
  }, []);

  // --- (แก้ไข) useEffect หลักที่รวมทุก Logic การดึงข้อมูล ---
  useEffect(() => {
    // --- โหมด Local API (Polling) ---
    if (USE_LOCAL_API) {
        console.log("MODE: Using Local API Server");
        setStatus('🟡 Using Local API (อัปเดตทุก 5 วินาที)');

        const fetchLocalData = async () => {
            try {
                const [visitorsRes, visitsRes] = await Promise.all([
                    fetch(`${LOCAL_API_URL}/visitors`),
                    fetch(`${LOCAL_API_URL}/station_visits`)
                ]);
                if (!visitorsRes.ok || !visitsRes.ok) throw new Error('Network response was not ok');
                const visitorsData = await visitorsRes.json();
                const visitsData = await visitsRes.json();
                setVisitors(visitorsData || []);
                setVisits(visitsData || []);
            } catch (error) {
                console.error("Failed to fetch from local API:", error);
                setStatus('🔴 เชื่อมต่อ Local API ไม่สำเร็จ (เช็คว่า api_server.js รันอยู่หรือไม่)');
            }
        };

        fetchLocalData();
        const intervalId = setInterval(fetchLocalData, 5000);
        return () => clearInterval(intervalId);
    }
    
    // --- โหมด Supabase (Real-time อัจฉริยะ) ---
    else {
        console.log("MODE: Using Supabase Real-time (Smart)");
        
        const fetchInitialData = async () => {
          setStatus('กำลังดึงข้อมูลเริ่มต้น...');
          const { data: vData } = await supabase.from('visitors').select('*');
          const { data: viData } = await supabase.from('station_visits').select('*');
          setVisitors(vData || []);
          setVisits(viData || []);
          setStatus('✅ เชื่อมต่อ Real-time สำเร็จ!');
        };
        fetchInitialData();

        const handleVisitorInsert = (payload) => setVisitors(current => [...current, payload.new]);
        const handleVisitorUpdate = (payload) => setVisitors(current => current.map(v => v.token === payload.new.token ? payload.new : v));
        const handleVisitInsert = (payload) => setVisits(current => [...current, payload.new]);
        const handleVisitUpdate = (payload) => setVisits(current => current.map(v => v.id === payload.new.id ? payload.new : v));

        const sub = supabase.channel('public-tables')
          .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'visitors' }, handleVisitorInsert)
          .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'visitors' }, handleVisitorUpdate)
          .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'station_visits' }, handleVisitInsert)
          .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'station_visits' }, handleVisitUpdate)
          .subscribe();

        return () => supabase.removeChannel(sub);
    }
  }, []); // useEffect นี้จะรันแค่ครั้งเดียวเพื่อตั้งค่าโหมดการทำงาน
  // -----------------------------------------------------------

  const handleScanResult = useCallback((scannedToken) => {
      const visitorExists = visitors.some(v => v.token === scannedToken);
      if (visitorExists) {
          setSelectedToken(scannedToken);
      } else {
          setNotFoundToken(scannedToken);
      }
  }, [visitors]);

  // --- 2. เรียกใช้เครื่องมือดักจับ ---
  // บรรทัดนี้จะทำให้แอป "ฟัง" ข้อมูลจากสแกนเนอร์ตลอดเวลา
  useBarcodeScanner({ onScan: handleScanResult });
  // ---------------------------------


  const { 
    filteredVisitors, selectedVisitorData, totalCompleted, 
    totalClaimed, totalRegistered, currentOccupancy, activeVisitorsByStation 
  } = useMemo(() => {
    // ... (ส่วนนี้เหมือนเดิม) ...
    const filtered = searchTerm ? visitors.filter(v => v.token.toLowerCase().includes(searchTerm.toLowerCase())) : visitors;
    let selectedData = null;
    if (selectedToken) {
        const visitor = visitors.find(v => v.token === selectedToken);
        if (visitor) selectedData = { visitor, visits: visits.filter(v => v.token === selectedToken) };
    }
    const completed = visitors.filter(v => {
        const completedSet = new Set(visits.filter(visit => visit.token === v.token && visit.check_out_time).map(visit => visit.station_id));
        return REQUIRED_STATIONS.every(station => completedSet.has(station));
    }).length;
    const activeVisits = visits.filter(v => v.check_out_time === null);
    const activeByStation = activeVisits.reduce((acc, visit) => {
        if (!acc[visit.station_id]) acc[visit.station_id] = [];
        acc[visit.station_id].push(visit.token);
        return acc;
    }, {});
    const occupancy = Object.keys(activeByStation).reduce((acc, station) => {
        acc[station] = activeByStation[station].length;
        return acc;
    }, {});
    return {
        filteredVisitors: filtered, selectedVisitorData: selectedData, totalCompleted: completed,
        totalClaimed: visitors.filter(v => v.reward_claimed_at).length,
        totalRegistered: visitors.filter(v => v.registered_at).length,
        currentOccupancy: occupancy, activeVisitorsByStation: activeByStation
    };
  }, [searchTerm, selectedToken, visits, visitors]);

  const barChartData = {
    labels: Object.keys(currentOccupancy),
    datasets: [{
      label: 'จำนวนคนปัจจุบันในสถานี',
      data: Object.values(currentOccupancy),
      backgroundColor: 'rgba(53, 162, 235, 0.6)',
    }],
  };
  
  return (
    <div className="dashboard-container">
      {/* ... (โค้ดส่วน JSX ที่แสดงผลทั้งหมดเหมือนเดิม) ... */}
      <div className="card">
        <div className="header-main">
          <div className="header-title"><h1>📊 Live Event Dashboard</h1><p>Open House Gamification</p></div>
          <div className="live-clock">{currentTime}</div>
        </div>
        <div className="status-bar status-subscribed">{status}</div>
      </div>
      <div className="card">
        <h2>ภาพรวมกิจกรรม</h2>
        <div className="stats-grid">
          <StatCard title="ผู้เข้าร่วมทั้งหมด" value={visitors.length} unit="คน" />
          <StatCard title="ผ่านทุกฐานแล้ว" value={totalCompleted} unit="คน" />
          <StatCard title="รับรางวัลแล้ว" value={totalClaimed} unit="คน" />
          <StatCard title="ลงทะเบียนเสร็จสิ้น" value={totalRegistered} unit="คน" />
        </div>
      </div>
      <VisitorLookup onVisitorFound={handleScanResult} />
      {selectedVisitorData && 
        <VisitorDetailModal 
            visitor={selectedVisitorData.visitor} 
            visits={selectedVisitorData.visits}
            onClose={() => setSelectedToken(null)} 
        />
      }
      {viewingStation && 
        <StationVisitorsModal 
            station={viewingStation}
            visitors={activeVisitorsByStation[viewingStation] || []}
            onClose={() => setViewingStation(null)}
        />
      }
      <NotFoundModal token={notFoundToken} onClose={() => setNotFoundToken(null)} />
      <div className="charts-grid">
        <div className="card">
          <h2>จำนวนคนในแต่ละสถานี (ปัจจุบัน)</h2>
          <Bar data={barChartData} options={{ responsive: true }} />
        </div>
        <div className="card">
            <h2>ผู้เข้าร่วมกิจกรรมปัจจุบัน</h2>
            <div className="active-list">
                {Object.keys(currentOccupancy).length > 0 ? (
                    Object.entries(currentOccupancy).map(([station, count]) => (
                        <div key={station} className="active-station-item" onClick={() => setViewingStation(station)}>
                            <span>{station}</span>
                            <span className="active-count">{count} คน</span>
                        </div>
                    ))
                ) : (<p>ยังไม่มีผู้เข้าร่วมในสถานีใดๆ</p>)}
            </div>
        </div>
      </div>
      <div className="card">
        <h2>ตารางติดตามความคืบหน้า</h2>
        <input 
            type="text" 
            className="search-input"
            placeholder="พิมพ์เพื่อค้นหา Token ID..." 
            onChange={(e) => setSearchTerm(e.target.value)} 
        />
        <table className="progress-table">
          <thead>
            <tr>
              <th>Token ID</th>
              <th>ความคืบหน้า</th>
              <th>ฐานที่ผ่าน</th>
              <th>สถานะ</th>
            </tr>
          </thead>
          <tbody>
            {filteredVisitors.map(visitor => (
              <VisitorRow 
                key={visitor.token} 
                visitor={visitor} 
                visits={visits.filter(v => v.token === visitor.token)}
                onRowClick={setSelectedToken}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --- CSS ที่จำเป็น (ไม่มีการเปลี่ยนแปลง) ---
const styles = `
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; }
.stat-card { background-color: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
.stat-value { font-size: 2.5em; font-weight: 700; }
.stat-title { color: #6c757d; margin-top: 4px; }
.stat-unit { font-size: 0.8em; }
.progress-table { width: 100%; border-collapse: collapse; margin-top: 16px; }
.progress-table th, .progress-table td { text-align: left; padding: 12px; border-bottom: 1px solid #eee; }
.progress-table tbody tr { cursor: pointer; transition: background-color 0.2s; }
.progress-table tbody tr:hover { background-color: #f8f9fa; }
.progress-table thead th { background-color: #f8f9fa; }
.progress-bar { background-color: #e9ecef; border-radius: 12px; height: 24px; width: 100%; overflow: hidden; }
.progress-bar-fill { background-color: #0d6efd; color: white; display: flex; align-items: center; justify-content: center; height: 100%; font-size: 12px; font-weight: bold; transition: width 0.4s ease; }
.status-ลงทะเบียนเสร็จสิ้น { color: #198754; font-weight: bold; }
.status-รับรางวัลแล้ว { color: #fd7e14; font-weight: bold; }
.status-ผ่านทุกฐาน { color: #0dcaf0; font-weight: bold; color: #000;}
.status-กำลังร่วมกิจกรรม { color: #6c757d; }
.status-text { font-weight: bold; padding: 4px 8px; border-radius: 4px; color: white; }
.status-text.status-ลงทะเบียนเสร็จสิ้น { background-color: #198754; }
.status-text.status-รับรางวัลแล้ว { background-color: #fd7e14; }
.status-text.status-ผ่านทุกฐาน { background-color: #0dcaf0; color: #000; }
.status-text.status-กำลังร่วมกิจกรรม { background-color: #6c757d; }
.search-input { width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 8px; box-sizing: border-box; }
.scan-btn { width: 100%; padding: 12px; font-size: 16px; background-color: #0d6efd; color: white; border: none; border-radius: 8px; cursor: pointer; transition: background-color 0.2s; }
.scan-btn:hover { background-color: #0b5ed7; }
.scanner-container { max-width: 500px; margin: 20px auto 0; }
/* Modal Styles */
.modal-backdrop { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 1000; }
.modal-content { background-color: white; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%; box-shadow: 0 5px 15px rgba(0,0,0,0.3); position: relative; animation: modal-fade-in 0.3s; }
@keyframes modal-fade-in { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
.modal-close-btn { position: absolute; top: 10px; right: 15px; background: none; border: none; font-size: 24px; cursor: pointer; }
.visit-history { list-style: none; padding: 0; max-height: 200px; overflow-y: auto; }
.visit-history li { background-color: #f8f9fa; padding: 10px; border-radius: 4px; margin-bottom: 8px; }
.status-active { color: #dc3545; font-weight: bold; }
.charts-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
@media (max-width: 900px) { .charts-grid { grid-template-columns: 1fr; } }
.active-list { display: flex; flex-direction: column; gap: 12px; }
.active-station-item { display: flex; justify-content: space-between; align-items: center; font-size: 1.1em; padding: 12px; border-radius: 8px; background-color: #f8f9fa; cursor: pointer; transition: background-color 0.2s; }
.active-station-item:hover { background-color: #e9ecef; }
.active-count { font-weight: bold; background-color: #e9ecef; padding: 4px 10px; border-radius: 12px; }
.visitor-tags-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; max-height: 300px; overflow-y: auto; }
.visitor-tag { background-color: #e9ecef; padding: 4px 10px; border-radius: 12px; font-size: 14px; }
.not-found-token { background-color: #fff3cd; color: #664d03; padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; margin-top: 10px; border: 1px solid #ffecb5;}
`;
const styleSheet = document.createElement("style");
styleSheet.innerText = styles;
document.head.appendChild(styleSheet);


export default App;