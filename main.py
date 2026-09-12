# =====================================================================
# CINEAI STUDIO v10.2 - FIX LỖI 404 & ĐỒNG BỘ LUỒNG PIPELINE
# =====================================================================

import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="CineAI Studio v10.2", version="10.2")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")

class ProjectRequest(BaseModel):
    ten_du_an: str
    cot_truyen: str
    phong_cach: str = "Cinematic 3D Epic"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CineAI Studio v10.2 - Xưởng Phim Tự Động</title>
    <style>
        :root { --bg: #0b0f19; --card: #1e293b; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8; --border: #334155; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }
        body { background-color: var(--bg); color: var(--text); padding: 20px; line-height: 1.6; }
        .container { max-width: 850px; margin: 0 auto; }
        header { text-align: center; margin-bottom: 25px; }
        header h1 { color: var(--accent); font-size: 1.8rem; margin-bottom: 5px; }
        header p { color: var(--muted); font-size: 0.9rem; }
        .card { background-color: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 10px 15px rgba(0,0,0,0.5); }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-size: 0.9rem; font-weight: 500; margin-bottom: 6px; color: #cbd5e1; }
        input, select, textarea { width: 100%; padding: 12px; background-color: #0f172a; border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 1rem; }
        textarea { resize: vertical; min-height: 120px; }
        button { background: linear-gradient(135deg, #38bdf8, #0284c7); color: #0f172a; border: none; padding: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; font-size: 1rem; }
        .output { background: #0f172a; padding: 18px; margin-top: 20px; border-radius: 8px; border: 1px dashed var(--border); white-space: pre-wrap; color: var(--accent); font-size: 0.9rem; display: none; }
        .loading { text-align: center; color: #f59e0b; margin-top: 15px; font-style: italic; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎬 CineAI Studio v10.2</h1>
            <p>Xưởng Sản Xuất Phim Chuẩn Tối Ưu Chi Phí & Đồng Bộ API</p>
        </header>

        <div class="card">
            <div class="form-group">
                <label>Tên Dự Án Phim:</label>
                <input type="text" id="tenDuAn" value="Mùi khói bếp đầu mùa">
            </div>
            <div class="form-group">
                <label>Cốt Truyện Thô / Nguyên Liệu Đời Thực:</label>
                <textarea id="cotTruyen" placeholder="Nhập chất liệu thô..."></textarea>
            </div>
            <button onclick="chayQuyTrinh()">🚀 Kích Hoạt Đạo Diễn Tối Ưu Chi Phí</button>
            <div id="loadingText" class="loading">⏳ Hệ thống đang điều phối 11 tầng đạo diễn...</div>
            <div id="resultBox" class="output"></div>
        </div>
    </div>

    <script>
        async function chayQuyTrinh() {
            const tenDuAn = document.getElementById('tenDuAn').value.trim();
            const cotTruyen = document.getElementById('cotTruyen').value.trim();
            const btn = document.querySelector('button');
            const loading = document.getElementById('loadingText');
            const box = document.getElementById('resultBox');

            if (!cotTruyen) { alert('Vui lòng nhập cốt truyện!'); return; }

            btn.disabled = true;
            loading.style.display = 'block';
            box.style.display = 'none';

            try {
                const res = await fetch('/api/v1/studio/pipeline', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ten_du_an: tenDuAn, cot_truyen: cotTruyen })
                });
                const data = await res.json();
                
                loading.style.display = 'none';
                btn.disabled = false;
                box.style.display = 'block';

                if (res.ok) {
                    box.innerHTML = `<strong>✨ KẾT QUẢ ĐẠO DIỄN:</strong>\\n\\n${data.ket_qua_11_tang}`;
                } else {
                    box.innerHTML = `❌ Lỗi hệ thống: ${data.detail || JSON.stringify(data)}`;
                }
            } catch(e) {
                loading.style.display = 'none';
                btn.disabled = false;
                box.style.display = 'block';
                box.innerHTML = `❌ Lỗi kết nối: ${e.message}`;
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_TEMPLATE

@app.post("/api/v1/studio/pipeline")
def pipeline(req: ProjectRequest):
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_KEY":
            raise HTTPException(status_code=400, detail="Thiếu Gemini API Key.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        prompt = (
            f"Bạn là hệ thống trí tuệ nhân tạo cốt lõi của CineAI Studio. "
            f"Dự án: '{req.ten_du_an}'. "
            f"Hãy phân rã cốt truyện thô sau đây thành một bộ hồ sơ xuất xưởng hoàn chỉnh đạt chuẩn >= 90 điểm: "
            f"1. 11 chốt khóa đạo diễn điện ảnh sắc bén. "
            f"2. Bộ Visual Prompt cực kỳ chuẩn xác và tối giản cho Keyframe hình ảnh. "
            f"3. Cấu trúc âm thanh và mã lệnh Suno AI Audiophile chia 2 phần, 100% tiếng Anh chuẩn xác tích hợp Stereo 3D. "
            f"Cốt truyện thô đầu vào: {req.cot_truyen}"
        )
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
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
        
