import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="CineAI Studio", version="10.3")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

class RequestData(BaseModel):
    ten_du_an: str
    cot_truyen: str

@app.get("/", response_class=HTMLResponse)
def home():
    return """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CineAI Studio</title>
    <style>
        body { background: #0b0f19; color: #f8fafc; font-family: sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 20px; }
        input, textarea { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #475569; color: #fff; border-radius: 8px; margin-bottom: 12px; box-sizing: border-box; }
        button { background: #38bdf8; color: #0f172a; border: none; padding: 14px; font-weight: bold; border-radius: 8px; width: 100%; cursor: pointer; }
        .output { background: #0f172a; padding: 15px; margin-top: 15px; border-radius: 8px; border: 1px dashed #475569; white-space: pre-wrap; color: #38bdf8; display: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🎬 CineAI Studio v10.3</h2>
        <label>Tên Dự Án:</label>
        <input type="text" id="tenDuAn" value="Mùi khói bếp đầu mùa">
        <label>Cốt Truyện Thô:</label>
        <textarea id="cotTruyen" rows="4" placeholder="Nhập nội dung..."></textarea>
        <button onclick="chayXuatXuong()">🚀 Kích Hoạt Đạo Diễn AI</button>
        <div id="resultBox" class="output"></div>
    </div>
    <script>
        async function chayXuatXuong() {
            const tenDuAn = document.getElementById('tenDuAn').value;
            const cotTruyen = document.getElementById('cotTruyen').value;
            const box = document.getElementById('resultBox');
            if(!cotTruyen) { alert('Nhập cốt truyện đi anh!'); return; }
            
            box.style.display = 'block';
            box.innerHTML = '⏳ Đang xử lý 11 tầng đạo diễn...';

            try {
                const res = await fetch('/api/v1/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ten_du_an: tenDuAn, cot_truyen: cotTruyen })
                });
                const data = await res.json();
                if(res.ok) {
                    box.innerHTML = '<strong>✨ KẾT QUẢ:</strong>\\n\\n' + data.ket_qua;
                } else {
                    box.innerHTML = '❌ Lỗi API: ' + (data.detail || JSON.stringify(data));
                }
            } catch(e) {
                box.innerHTML = '❌ Lỗi kết nối JavaScript: ' + e.message;
            }
        }
    </script>
</body>
</html>"""

@app.post("/api/v1/run")
def run_pipeline(req: RequestData):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=400, detail="Chưa cấu hình GEMINI_API_KEY trong Environment Variables của Render.")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    prompt = f"Phân rã dự án '{req.ten_du_an}' với cốt truyện '{req.cot_truyen}' thành 11 chốt khóa đạo diễn, Visual Prompt và mã lệnh Suno AI 3D."
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
        
    data = response.json()
    ket_qua_ai = data["candidates"][0]["content"]["parts"][0]["text"]
    return {"status": "success", "ket_qua": ket_qua_ai}
    
