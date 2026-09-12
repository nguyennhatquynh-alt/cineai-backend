from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os
import requests
import json

app = FastAPI(title="CineAI Studio - Autonomous Director", version="3.3")

class ScriptRequest(BaseModel):
    project_name: str
    story_prompt: str
    art_style: str
    mood: str
    shots: int
    api_key: str = ""

def call_ai_with_fallback(prompt: str, api_key: str = "") -> dict:
    # Lấy key ưu tiên từ ô nhập trực tiếp trên giao diện, nếu trống mới tìm trong biến môi trường
    gemini_key = api_key.strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                res_data = response.json()
                text_result = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return {"source": "Gemini-1.5-Flash (Live AI)", "content": text_result}
            else:
                print(f"Gemini API lỗi code {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Lỗi kết nối Gemini API: {e}")

    # Fallback dự phòng an toàn nếu chưa nhập key
    fallback_content = f"""
    [PHÂN TÍCH 11 CHỐT KHÓA ĐẠO DIỄN - HỆ THỐNG DỰ PHÒNG TỰ ĐỘNG]
    1. Tiền đề & Chủ đề: Khắc họa chiều sâu ký ức và bản chất con người.
    2. DNA Nhân vật: Tâm lý nội tâm biến động, mang khát vọng tĩnh lặng.
    3. Không gian & Bối cảnh: Đậm chất điện ảnh, không gian đa chiều, thực thực hư hư.
    4. Phong cách thị giác: Cinematic 3D Epic kết hợp hoài niệm.
    5. Gam màu & Ánh sáng: Tông trầm ấm áp, ánh sáng ven (rim light) tách nền nghệ thuật.
    6. Chuyển động máy quay: Slow-pan kết hợp tracking mượt mà, tạo độ sâu trường ảnh (depth of field).
    7. Âm thanh & Tiết tấu: Ambient sound tự nhiên kết hợp nhịp điệu chậm rãi, sâu lắng.
    8. Xung đột chủ đạo: Sự giao thoa giữa thời gian thực tại và ký ức tiềm thức.
    9. Điểm nhấn cảm xúc (The Hook): Chạm trực diện vào tâm thức khán giả ngay từ giây đầu tiên.
    10. Thông điệp truyền tải: Sự chữa lành và tiếng vọng của tâm hồn.
    11. Bản vẽ Visual Prompt: Photorealistic, 8k resolution, volumetric lighting, masterpiece cinematic shot.
    """
    return {"source": "Autonomous-Fallback-Engine (Chưa có API Key)", "content": fallback_content}

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CineAI Studio - Autonomous Director</title>
    <style>
        :root {
            --bg-color: #0f1117;
            --card-bg: #161b22;
            --accent-color: #58a6ff;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --border-color: #30363d;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-main); padding: 16px; line-height: 1.5; }
        .container { max-width: 650px; margin: 0 auto; padding-bottom: 40px; }
        header { text-align: center; margin-bottom: 24px; }
        header h1 { font-size: 1.8rem; font-weight: 700; color: #ffffff; margin-bottom: 6px; }
        header p { font-size: 0.9rem; color: var(--text-muted); }
        
        .card { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; margin-bottom: 16px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 0.85rem; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
        
        input[type="text"], textarea, select {
            width: 100%; padding: 12px; background-color: #0d1117; border: 1px solid var(--border-color);
            border-radius: 8px; color: var(--text-main); font-size: 1rem; outline: none; transition: border-color 0.2s;
        }
        input[type="text"]:focus, textarea:focus, select:focus { border-color: var(--accent-color); }
        textarea { resize: vertical; min-height: 100px; }
        
        .row { display: flex; gap: 12px; }
        .col { flex: 1; }

        .btn {
            display: block; width: 100%; padding: 14px; background: linear-gradient(135deg, #238636, #2ea043);
            color: white; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer;
            text-align: center; transition: opacity 0.2s; box-shadow: 0 4px 12px rgba(46, 160, 67, 0.3);
        }
        .btn:active { opacity: 0.8; }
        
        #result-area { display: none; margin-top: 20px; }
        .box { background-color: #0d1117; border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; margin-bottom: 12px; font-size: 0.95rem; white-space: pre-line; color: #c9d1d9; }
        .loading { text-align: center; color: var(--accent-color); font-weight: 500; margin: 15px 0; display: none; }
        .badge { display: inline-block; padding: 4px 8px; font-size: 0.75rem; background: #30363d; color: var(--accent-color); border-radius: 4px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>CineAI Studio</h1>
            <p>Xưởng Phim Điện Ảnh 11 Chốt Khóa Đạo Diễn</p>
        </header>

        <div class="card">
            <div class="form-group">
                <label>Tên Dự Án Phim</label>
                <input type="text" id="project_name" value="Mùi khói bếp đầu mùa">
            </div>

            <div class="form-group">
                <label>Cốt Truyện Thô / Nguyên Liệu Đời Thực</label>
                <textarea id="story_prompt">Chiều cuối năm, gió bắc tràn về qua những kẽ lá, mang theo cái lạnh se sắt của miền quê nghèo.</textarea>
            </div>

            <div class="row">
                <div class="col">
                    <div class="form-group">
                        <label>Phong Cách Đạo Diễn</label>
                        <select id="art_style">
                            <option value="Cinematic 3D Epic">Cinematic 3D Epic</option>
                            <option value="Watercolor Memoir">Watercolor Memoir</option>
                            <option value="Dark Noir Thriller">Dark Noir Thriller</option>
                        </select>
                    </div>
                </div>
                <div class="col">
                    <div class="form-group">
                        <label>Số Lượng Phân Cảnh</label>
                        <input type="text" id="shots" value="4">
                    </div>
                </div>
            </div>

            <div class="form-group">
                <label>Gemini API Key (Dán trực tiếp mã AQ... vào đây)</label>
                <input type="text" id="api_key" placeholder="Dán khóa API của bạn vào đây...">
            </div>

            <button class="btn" onclick="runDirector()">🎬 KHỞI CHẠY HỆ THỐNG ĐẠO DIỄN</button>
        </div>

        <div id="loading" class="loading">Bộ não AI đang phân rã 11 chốt khóa điện ảnh...</div>

        <div id="result-area">
            <div class="card">
                <div class="badge" id="model-badge">Mô hình: Đang xác định</div>
                <label style="color: var(--accent-color); margin-bottom: 8px; display:block; font-weight:600;">KẾT QUẢ ĐẠO DIỄN & 11 CHỐT KHÓA</label>
                <div class="box" id="director-output">Đang xử lý dữ liệu...</div>
            </div>
        </div>
    </div>

    <script>
        async function runDirector() {
            const data = {
                project_name: document.getElementById('project_name').value,
                story_prompt: document.getElementById('story_prompt').value,
                art_style: document.getElementById('art_style').value,
                mood: "Hoài niệm",
                shots: parseInt(document.getElementById('shots').value) || 4,
                api_key: document.getElementById('api_key').value
            };

            document.getElementById('loading').style.display = 'block';
            document.getElementById('result-area').style.display = 'none';

            try {
                let response = await fetch('/api/direct', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                let res = await response.json();
                
                document.getElementById('model-badge').innerText = `Mô hình kích hoạt: ${res.model_used}`;
                document.getElementById('director-output').innerText = res.result;

                document.getElementById('result-area').style.display = 'block';
            } catch (err) {
                alert('Có lỗi xảy ra khi kết nối tới máy chủ đạo diễn!');
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
    </script>
</body>
</html>
    """

@app.post("/api/direct")
async def api_direct(req: ScriptRequest):
    master_prompt = (
        f"Đóng vai là một đạo diễn điện ảnh thiên tài. Hãy phân rã cốt truyện sau thành kịch bản "
        f"với đầy đủ 11 Chốt Khóa Đạo Diễn (Từ tiền đề, DNA nhân vật, không gian, phong cách thị giác, "
        f"gam màu, chuyển động máy quay, âm thanh, xung đột, điểm nhấn cảm xúc, thông điệp đến prompt hình ảnh):\n\n"
        f"Tên dự án: {req.project_name}\n"
        f"Phong cách: {req.art_style}\n"
        f"Số lượng phân cảnh: {req.shots}\n"
        f"Cốt truyện thô: {req.story_prompt}"
    )

    ai_response = call_ai_with_fallback(master_prompt, req.api_key)

    return {
        "model_used": ai_response["source"],
        "result": ai_response["content"]
    }
    
