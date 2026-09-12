# =====================================================================
# CINEAI STUDIO v9.2 - XƯỞNG PHIM TỰ ĐỘNG 11 TẦNG (FULL PIPELINE)
# =====================================================================

import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="CineAI Studio v9.2 - Full Pipeline", version="9.2")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")

class ProjectRequest(BaseModel):
    ten_du_an: str
    cot_truyen: str
    phong_cach: str = "Cinematic 3D Epic"

# --- PHẦN 1: GIAO DIỆN WEB DASHBOARD (HTML/CSS/JS) ---
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CineAI Studio v9.2 - Xưởng Phim Tự Động</title>
    <style>
        :root { --bg: #0b0f19; --card: #1e293b; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8; --border: #334155; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg); color: var(--text); padding: 20px; line-height: 1.6; }
        .container { max-width: 800px; margin: 0 auto; }
        header { text-align: center; margin-bottom: 25px; }
        header h1 { color: var(--accent); font-size: 1.8rem; margin-bottom: 5px; }
        header p { color: var(--muted); font-size: 0.9rem; }
        .card { background-color: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-size: 0.9rem; font-weight: 500; margin-bottom: 6px; color: #cbd5e1; }
        input, select, textarea { width: 100%; padding: 12px; background-color: #0f172a; border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 1rem; }
        textarea { resize: vertical; min-height: 120px; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); }
        button { background: linear-gradient(135deg, #38bdf8, #0284c7); color: #0f172a; border: none; padding: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; font-size: 1rem; transition: opacity 0.2s; }
        button:active { opacity: 0.8; }
        .output { background: #0f172a; padding: 18px; margin-top: 20px; border-radius: 8px; border: 1px dashed var(--border); white-space: pre-wrap; color: var(--accent); font-size: 0.9rem; line-height: 1.6; display: none; }
        .loading { text-align: center; color: #f59e0b; margin-top: 15px; font-style: italic; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎬 CineAI Studio v9.2</h1>
            <p>Xưởng Sản Xuất Phim Tự Động 11 Tầng (Audiophile 3D & Keyframe)</p>
        </header>

        <div class="card">
            <div class="form-group">
                <label>Tên Dự Án Phim:</label>
                <input type="text" id="tenDuAn" value="Chiều cuối năm">
            </div>
            <div class="form-group">
                <label>Cốt Truyện Thô / Nguyên Liệu Đời Thực:</label>
                <textarea id="cotTruyen" placeholder="Nhập chất liệu thô, gai góc, chi tiết..."></textarea>
            </div>
            <div class="form-group">
                <label>Phong Cách Đạo Diễn & Hình Ảnh:</label>
                <select id="phongCach">
                    <option value="Cinematic 3D Epic">Cinematic 3D Epic</option>
                    <option value="Art-Pop Narrative">Art-Pop Narrative (Tự sự)</option>
                    <option value="Raw Realism 8K">Raw Realism (Đời thực gai góc)</option>
                </select>
            </div>
            <button onclick="chaySanXuatToanDien()">🚀 Kích Hoạt Xưởng Phim Toàn Diện</button>
            <div id="loadingText" class="loading">⏳ Hệ thống đang điều phối 11 tầng (Kịch bản, Keyframe, Suno Audiophile)...</div>
            <div id="resultBox" class="output"></div>
        </div>
    </div>

    <script>
        async function chaySanXuatToanDien() {
            const tenDuAn = document.getElementById('tenDuAn').value.trim();
            const cotTruyen = document.getElementById('cotTruyen').value.trim();
            const phongCach = document.getElementById('phongCach').value;
            const btn = document.querySelector('button');
            const loading = document.getElementById('loadingText');
            const box = document.getElementById('resultBox');

            if (!cotTruyen) {
                alert('Vui lòng nhập cốt truyện thô!');
                return;
            }

            btn.disabled = true;
            loading.style.display = 'block';
            box.style.display = 'none';

            try {
                const res = await fetch('/api/v1/studio/san-xuat-toan-dien', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ten_du_an: tenDuAn, cot_truyen: cotTruyen, phong_cach: phongCach })
                });
                const data = await res.json();
                
                loading.style.display = 'none';
                btn.disabled = false;
                box.style.display = 'block';

                if (res.ok) {
                    box.innerHTML = `<strong>✨ KẾT QUẢ XUẤT XƯỞNG TOÀN DIỆN (11 TẦNG):</strong>\n\n${data.ket_qua_11_tang}`;
                } else {
                    box.innerHTML = `❌ Lỗi hệ thống: ${data.detail || JSON.stringify(data)}`;
                }
            } catch(e) {
                loading.style.display = 'none';
                btn.disabled = false;
                box.style.display = 'block';
                box.innerHTML = `❌ Lỗi kết nối mạng: ${e.message}`;
            }
        }
    </script>
</body>
</html>
"""

# --- PHẦN 2: BACKEND & LOGIC XỬ LÝ 11 TẦNG ---
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_TEMPLATE

@app.post("/api/v1/studio/san-xuat-toan-dien")
def san_xuat_toan_dien(req: ProjectRequest):
    try:
        api_key = GEMINI_API_KEY if GEMINI_API_KEY != "YOUR_GEMINI_KEY" else os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=400, detail="Chưa cấu hình Gemini API Key trên hệ thống Cloud.")

        # Sử dụng model gemini-3.6-flash chuẩn mới nhất theo yêu cầu hệ thống
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt_he_thong = (
            f"Bạn là hệ thống trí tuệ nhân tạo cốt lõi của CineAI Studio. "
            f"Dự án phim: '{req.ten_du_an}'. Phong cách hình ảnh và không gian: '{req.phong_cach}'. "
            f"Hãy thực hiện phân rã trọn vẹn cốt truyện thô sau đây thành một bộ hồ sơ xuất xưởng hoàn chỉnh bao gồm: "
            f"1. 11 chốt khóa đạo diễn điện ảnh (từ tiền đề, DNA nhân vật, không gian, gam màu, chuyển động máy quay đến thông điệp). "
            f"2. Bộ Visual Prompt chuẩn quốc tế cho từng phân cảnh để kết nối với Stability AI tạo Keyframe hình ảnh (tách bạch ánh sáng, 8k resolution, không dùng ảnh thật thô tục). "
            f"3. Cấu trúc âm thanh và mã lệnh Suno AI Audiophile đạt chuẩn >= 90 điểm, 100% tiếng Anh chuyên nghiệp, chia rõ làm 2 phần (Part 1 & Part 2), tích hợp lập trình Stereo 3D: Binaural 3D spatial audio, holographic soundstage, dynamic left-right hard panning, crystal clear 24-bit audiophile, warm mid, shimmering treble. "
            f"Cốt truyện thô nguyên liệu đầu vào: {req.cot_truyen}"
        )
        
        payload = {"contents": [{"parts": [{"text": prompt_he_thong}]}]}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
            
        ket_qua_ai = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        
        return {
            "status": "success",
            "project_name": req.ten_du_an,
            "ket_qua_11_tang": ket_qua_ai
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
