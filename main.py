import os
import random
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="CineAI Studio - Production v10.11", version="10.11")

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
    <title>CineAI Studio v10.11</title>
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
        <h2>🎬 CineAI Studio v10.11</h2>
        <label>Tên Dự Án:</label>
        <input type="text" id="tenDuAn" value="Chiều cuối năm">
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
            if(!cotTruyen) { alert('Vui lòng nhập cốt truyện!'); return; }
            
            box.style.display = 'block';
            box.innerHTML = '⏳ Hệ thống đang điều phối cụm 5 Key với model chuẩn...';

            try {
                const res = await fetch('/api/v1/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ten_du_an: tenDuAn, cot_truyen: cotTruyen })
                });
                const data = await res.json();
                if(res.ok) {
                    box.innerHTML = '<strong>✨ KẾT QUẢ ĐẠO DIỄN (Dùng Key số ' + data.key_index_used + '):</strong>\\n\\n' + data.ket_qua;
                } else {
                    box.innerHTML = '❌ Lỗi API: ' + (data.detail || JSON.stringify(data));
                }
            } catch(e) {
                box.innerHTML = '❌ Lỗi kết nối: ' + e.message;
            }
        }
    </script>
</body>
</html>"""

@app.post("/api/v1/run")
def run_pipeline(req: RequestData):
    # Đọc danh sách key từ biến môi trường an toàn trên Render
    env_keys = os.getenv("GEMINI_API_KEYS", "")
    active_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    
    if not active_keys:
        raise HTTPException(
            status_code=400, 
            detail="Chưa cấu hình biến môi trường GEMINI_API_KEYS trên Render."
        )
    
    # Xáo trộn ngẫu nhiên để trượt key tự động
    keys_to_try = list(enumerate(active_keys))
    random.shuffle(keys_to_try)
    
    last_error = ""
    
    for idx, key in keys_to_try:
        # Cập nhật chuẩn model mới nhất theo thông báo từ Google API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={key}"
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
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            data = response.json()
            
            if response.status_code == 200 and "candidates" in data:
                ket_qua_ai = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"status": "success", "key_index_used": idx + 1, "ket_qua": ket_qua_ai}
            else:
                last_error = data.get("error", {}).get("message", response.text)
                continue
        except Exception as ex:
            last_error = str(ex)
            continue
            
    raise HTTPException(status_code=500, detail=f"Cả cụm API Key đều gặp sự cố. Chi tiết: {last_error}")
    
