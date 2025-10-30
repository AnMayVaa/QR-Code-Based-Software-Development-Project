import React, { useState, useEffect, useCallback } from 'react';
import { supabase } from './supabaseClient';
import { useBarcodeScanner } from './useBarcodeScanner';
import { Html5QrcodeScanner } from 'html5-qrcode';
import { publishRegisterEvent } from './mqttClient';
import './App.css';

const REQUIRED_STATIONS = ['network', 'programming', 'electricity'];

function App() {
  const [tokenInput, setTokenInput] = useState('');
  const [activeToken, setActiveToken] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [allVisitors, setAllVisitors] = useState([]);
  const [result, setResult] = useState(null);
  const [isEligible, setIsEligible] = useState(false);
  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  
  const [formData, setFormData] = useState({
      fullname: '', surname: '', age: '', gender: '', school: '', email: '', phone: ''
  });

  useEffect(() => {
    const fetchVisitors = async () => {
        const { data } = await supabase.from('visitors').select('token');
        if (data) setAllVisitors(data.map(v => v.token));
    };
    fetchVisitors();
  }, []);

  const checkTokenStatus = useCallback(async (tokenToCheck) => {
    if (!tokenToCheck) return;
    setActiveToken(tokenToCheck);
    setTokenInput(tokenToCheck);
    setSuggestions([]);
    setResult('กำลังตรวจสอบ...');
    setIsEligible(false);

    const { data: visitor } = await supabase.from('visitors').select('token, registered_at').eq('token', tokenToCheck).single();
    if (!visitor) {
        setResult(`ไม่พบข้อมูลสำหรับ Token: ${tokenToCheck}`);
        return;
    }
    if (visitor.registered_at) {
        setResult('Token นี้ได้ทำการลงทะเบียนเสร็จสิ้นไปแล้ว');
        return;
    }

    const { data: visits } = await supabase.from('station_visits').select('station_id').eq('token', tokenToCheck).not('check_out_time', 'is', null);
    const completedStations = new Set(visits.map(v => v.station_id).filter(id => REQUIRED_STATIONS.includes(id)));
    const completedCount = completedStations.size;
    
    if (completedCount >= REQUIRED_STATIONS.length) {
        setResult(`ผ่านเงื่อนไข (${completedCount}/${REQUIRED_STATIONS.length}) สามารถลงทะเบียนได้`);
        setIsEligible(true);
    } else {
        setResult(`เข้าร่วมกิจกรรมยังไม่ครบ (${completedCount}/${REQUIRED_STATIONS.length})`);
    }
  }, []);

  const handleRegister = (e) => {
      e.preventDefault();
      const payload = {
          eventType: 'register', token: activeToken,
          fullname: `${formData.fullname} ${formData.surname}`,
          age: parseInt(formData.age), gender: formData.gender, school: formData.school,
          email: formData.email, phone: formData.phone,
          epoch: Math.floor(Date.now() / 1000)
      };
      publishRegisterEvent(payload);
      resetState();
  };

  const resetState = () => {
    setShowRegisterForm(false); setIsEligible(false); setTokenInput(''); setActiveToken(''); setResult(null);
  }
  
  const handleInputChange = (e) => {
    const value = e.target.value;
    setTokenInput(value);
    if (value.length > 0) {
        setSuggestions(allVisitors.filter(v => v.toLowerCase().includes(value.toLowerCase())).slice(0, 5));
    } else {
        setSuggestions([]);
    }
  };

  // --- (แก้ไข) ส่วนควบคุมกล้องสแกน ---
  useEffect(() => {
    if (!isScanning) return;
    
    const scanner = new Html5QrcodeScanner(
        'qr-reader-container', 
        { fps: 10, qrbox: { width: 250, height: 250 } }, 
        false
    );
    
    const onScanSuccess = (decodedText) => {
        scanner.clear().catch(() => {});
        setIsScanning(false);
        checkTokenStatus(decodedText);
    };
    
    scanner.render(onScanSuccess, () => {});

    return () => {
        if (scanner && scanner.getState() !== "STOPPED") {
             scanner.clear().catch(() => {});
        }
    };
  }, [isScanning, checkTokenStatus]);


  useBarcodeScanner({ onScan: checkTokenStatus });

  return (
    <div className="container">
        {!showRegisterForm ? <h1>Enter your token</h1> : <h1>Fill the information</h1>}
        
        {!showRegisterForm && (
            <div className="card">
                <div className="input-container">
                    <div className="input-group">
                        <input type="text" placeholder="พิมพ์ Token หรือสแกน..." value={tokenInput} onChange={handleInputChange} />
                        <button onClick={() => checkTokenStatus(tokenInput)}>Submit</button>
                    </div>
                    {suggestions.length > 0 && (
                        <ul className="suggestions-list">
                            {suggestions.map(s => <li key={s} onClick={() => checkTokenStatus(s)}>{s}</li>)}
                        </ul>
                    )}
                </div>
                 <button onClick={() => setIsScanning(p => !p)} className="scan-btn-link">
                    {isScanning ? 'ปิดกล้อง' : 'หรือเปิดกล้องเพื่อสแกน'}
                </button>
                {isScanning && <div id="qr-reader-container"></div>}

                {result && <div className={`result ${isEligible ? 'success' : 'error'}`}>{result}</div>}

                {isEligible && (
                     <div className="confirm-popup">
                        <h3>ยืนยันการลงทะเบียน</h3>
                        <p>คุณเข้าร่วมกิจกรรมครบแล้ว ต้องการลงทะเบียนเพื่อรับของรางวัลหรือไม่?</p>
                        <div className="button-group">
                            <button className="cancel" onClick={resetState}>ยกเลิก</button>
                            <button className="confirm" onClick={() => setShowRegisterForm(true)}>ลงทะเบียนตอนนี้</button>
                        </div>
                    </div>
                )}
            </div>
        )}

        {showRegisterForm && (
            <div className="card">
                <form onSubmit={handleRegister}>
                    <div className="form-grid">
                        <input name="fullname" placeholder="ชื่อ" onChange={e => setFormData({...formData, fullname: e.target.value})} required />
                        <input name="surname" placeholder="นามสกุล" onChange={e => setFormData({...formData, surname: e.target.value})} required />
                    </div>
                     <div className="form-grid">
                        <input name="age" type="number" placeholder="อายุ" onChange={e => setFormData({...formData, age: e.target.value})} required />
                        <select name="gender" onChange={e => setFormData({...formData, gender: e.target.value})} required>
                            <option value="">-- เลือกเพศ --</option>
                            <option value="ชาย">ชาย</option>
                            <option value="หญิง">หญิง</option>
                            <option value="อื่นๆ">อื่นๆ</option>
                        </select>
                    </div>
                    <input name="school" placeholder="โรงเรียน" onChange={e => setFormData({...formData, school: e.target.value})} />
                    <input name="email" type="email" placeholder="อีเมล" onChange={e => setFormData({...formData, email: e.target.value})} />
                    <input name="phone" placeholder="เบอร์โทรศัพท์" onChange={e => setFormData({...formData, phone: e.target.value})} />
                    <button type="submit" className="register-btn">Register</button>
                </form>
            </div>
        )}
    </div>
  );
}

export default App;