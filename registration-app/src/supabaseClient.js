import { createClient } from '@supabase/supabase-js';

// --- การตั้งค่า ---
const SUPABASE_URL = 'https://xeejnzrxxdzkkhcjbuce.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhlZWpuenJ4eGR6a2toY2pidWNlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc0NDQ4OTcsImV4cCI6MjA3MzAyMDg5N30.uc57dQCH1kNKVg3gHagfnLdxQD3G6yJmINMIXu5Frow';

// สร้างและ export client สำหรับให้ไฟล์อื่นเรียกใช้
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
