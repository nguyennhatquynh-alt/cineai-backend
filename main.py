import os
import random
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="CineAI Studio - Production v10.19", version="10.19")

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
    <title>CineAI Studio v10.19</title>
    <style>
        body { background: #0b0f19; color: #f8fafc; font-family: sans-serif; padding: 20px; max-width: 900px; margin: 0 auto; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 20px; }
        input, textarea { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #475569; color: #fff; border-radius: 8px; margin-bottom: 12px; box-sizing: border-box; }
        button { background: #38bdf8; color: #0f172a; border: none; padding: 14px; font-weight: bold; border-radius: 8px; width: 100%; cursor: pointer; font-size: 16px; }
        .output { background: #0f172a; padding: 20px; margin-top: 15px; border-radius: 8px; border: 1px dashed #475569; white-space: pre-wrap; color: #38bdf8; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🎬 CineAI Studio v10.19 (11 Tầng Đạo Diễn & Audiophile)</h2>
        <label>Tên Dự Án:</label>
        <input type="text" id="tenDuAn" value="Chiều cuối năm">
        <label>Cốt Truyện Thô (Đời thực / Gai góc / Biến động):</label>
        <textarea id="cotTruyen" rows="5" placeholder="Nhập cốt truyện thô..."></textarea>
        <button onclick="chayXuatXuong()">🚀 Kích Hoạt 11 Tầng Lọc Đạo Diễn AI</button>
        <div id="resultBox" class="output" style="display: none;"></div>
    </div>
    <script>
        async function chayXuatXuong() {
            const tenDuAn = document.getElementById('tenDuAn').value;
            const cotTruyen = document.getElementById('cotTruyen').value;
            const box = document.getElementById('resultBox');
            if(!cotTruyen) { alert('Vui lòng nhập cốt truyện!'); return; }
            
            box.style.display = 'block';
            box.innerHTML = '⏳ Hệ thống đang chạy 11 tầng lọc đạo diễn và tinh chế âm thanh Audiophile...';

            try {
                const res = await fetch('/api/v1/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ten_du_an: tenDuAn, cot_truyen: cotTruyen })
                });
                const data = await res.json();
                if(res.ok) {
                    box.innerHTML = '<strong>✨ HỒ SƠ XUẤT XƯỞNG HOÀN CHỈNH (Key #' + data.key_index_used + '):</strong>\\n\\n' + data.ket_qua;
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
    env_keys = os.getenv("GEMINI_API_KEYS", "")
    active_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
    
    if not active_keys:
        raise HTTPException(status_code=400, detail="Chưa cấu hình biến môi trường GEMINI_API_KEYS trên Render.")
    
    keys_to_try = list(enumerate(active_keys))
    random.shuffle(keys_to_try)
    
    last_error = ""
    
    for idx, key in keys_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}
        
        # PROMPT CHUẨN HÓA 11 TẦNG ĐẠO DIỄN VÀ AUDIOPHILE CHUYÊN SÂU
        prompt = (
            f"Bạn là hệ thống trí tuệ nhân tạo cốt lõi của CineAI Studio. "
            f"Dự án: '{req.ten_du_an}'. "
            f"Hãy thực hiện phân rã cốt truyện thô đầu vào qua quy trình kiểm duyệt 11 tầng đạo diễn và sản xuất âm nhạc để xuất xưởng một bộ hồ sơ hoàn chỉnh đạt chuẩn >= 90 điểm.\n\n"
            f"Cốt truyện thô: {req.cot_truyen}\n\n"
            f"HÃY TRÌNH BÀY KẾT QUẢ THEO ĐÚNG CẤU TRÚC SAU:\n\n"
            f"🎬 PHẦN I: 11 CHỐT KHÓA ĐẠO DIỄN ĐIỆN ẢNH\n"
            f"1. Thể loại & Tone màu chủ đạo (Color Grading).\n"
            f"2. Cấu trúc nhịp điệu & Tiết tấu khung hình.\n"
            f"3. Xây dựng nhân vật & Điểm chạm cảm xúc.\n"
            f"4. Thiết kế không gian & Bối cảnh (Atmosphere).\n"
            f"5. Góc máy & Chuyển động camera đặc trưng.\n"
            f"6. Nghệ thuật ánh sáng & Đổ bóng (Chiaroscuro).\n"
            f"7. Xử lý âm thanh hiện trường & Khoảng lặng đắt giá.\n"
            f"8. Điểm thắt nút kịch bản (Climax).\n"
            f"9. Thông điệp ngầm & Lớp lang triết lý.\n"
            f"10. Phong cách dàn dựng (Mise-en-scène).\n"
            f"11. Tiêu chuẩn kiểm duyệt điểm số (Đạt chuẩn >= 90/100).\n\n"
            f"🎨 PHẦN II: BỘ VISUAL PROMPT (KEYFRAME HÌNH ẢNH)\n"
            f"- Cung cấp các câu lệnh prompt tiếng Anh tối giản, sắc bén, độc bản cho AI tạo ảnh (Midjourney/Stable Diffusion) để dựng Keyframe.\n\n"
            f"🎵 PHẦN III: MÃ LỆNH SUNO AI AUDIOPHILE (STEREO 3D)\n"
            f"- Tích hợp từ khóa: Binaural 3D spatial audio, holographic soundstage, dynamic left-right hard panning, crystal clear 24-bit audiophile.\n"
            f"- Chia làm 2 phần rõ rệt (Part 1 & Part 2) bằng 100% tiếng Anh chuyên nghiệp để copy-paste dễ dàng vào Suno AI."
        )
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2000}
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
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
            
    raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {last_error}")
    
