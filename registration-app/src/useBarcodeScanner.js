import { useEffect, useState, useCallback } from 'react';

export function useBarcodeScanner({ onScan }) {
  const [scanBuffer, setScanBuffer] = useState('');
  const [timerId, setTimerId] = useState(null);

  const handleKeyDown = useCallback((event) => {
    // ป้องกันการทำงานซ้ำซ้อน
    event.stopImmediatePropagation();

    // ถ้ากด Enter และมีข้อมูลใน buffer แสดงว่าสแกนเสร็จแล้ว
    if (event.key === 'Enter' && scanBuffer.length > 0) {
      event.preventDefault(); // ป้องกัน Enter ไปทำอย่างอื่น
      onScan(scanBuffer);   // ส่งข้อมูลที่สแกนได้ออกไป
      setScanBuffer('');    // ล้าง buffer
      clearTimeout(timerId);
      return;
    }

    // รับข้อมูลตัวอักษร/ตัวเลขเท่านั้น
    if (event.key.length === 1) {
      setScanBuffer(prev => prev + event.key);
    }
    
    // รีเซ็ต buffer ถ้าพิมพ์ช้าเกินไป (คนพิมพ์ ไม่ใช่เครื่องสแกน)
    if (timerId) clearTimeout(timerId);
    const newTimer = setTimeout(() => setScanBuffer(''), 100); // 100ms timeout
    setTimerId(newTimer);

  }, [scanBuffer, onScan, timerId]);

  useEffect(() => {
    // เริ่มดักฟังเมื่อ component ถูกสร้าง
    window.addEventListener('keydown', handleKeyDown);

    // หยุดดักฟังเมื่อ component ถูกทำลาย
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      if (timerId) clearTimeout(timerId);
    };
  }, [handleKeyDown, timerId]);
}