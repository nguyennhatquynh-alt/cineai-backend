from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os

app = FastAPI(title="CineAI Studio", version="2.0")

class ScriptRequest(BaseModel):
    project_name: str
    story_prompt: str
    art_style: str
    mood: str
    shots: int

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CineAI Studio - Xưởng Phim Tự Động</title>
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
        .container { max-width: 600px; margin: 0 auto; padding-bottom: 40px; }
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
        .dna-box, .shot-box { background-color: #0d1117; border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; margin-bottom: 12px; }
        .shot-box h3 { font-size: 1rem; color: var(--accent-color); margin-bottom: 8px; }
        .loading { text-align: center; color: var(--accent-color); font-weight: 500; margin: 15px 0; display: none; }
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
                <input type="text" id="project_name" value="Tiếng Vọng Sông Đắk Bla">
            </div>

            <div class="form-group">
                <label>Cốt Truyện Thô / Nguyên Liệu Đời Thực</label>
                <textarea id="story_prompt">Chiều cuối năm, gió bắc thổi lùa qua những mái ngói rêu phong ở phố núi Kon Tum.</textarea>
            </div>

            <div class="row">
                <div class="col">
                    <div class="form-group">
                        <label>Phong Cách</label>
                        <select id="art_style">
                            <option value="Cinematic 3D Epic">Cinematic 3D Epic</option>
                            <option value="Watercolor Memoir">Watercolor Memoir</option>
                            <option value="Dark Noir Thriller">Dark Noir Thriller</option>
                        </select>
                    </div>
                </div>
                <div class="col">
                    <div class="form-group">
                        <label>Số Lượng Shots</label>
                        <input type="text" id="shots" value="4">
                    </div>
                </div>
            </div>

            <button class="btn" onclick="runDirector()">🎬 BẮT ĐẦU ĐẠO DIỄN</button>
        </div>

        <div id="loading" class="loading">Đạo diễn AI đang phân rã kịch bản...</div>

        <div id="result-area">
            <div class="card">
                <label style="color: var(--accent-color); margin-bottom: 8px; display:block; font-weight:600;">DNA NHÂN VẬT & KHÔNG GIAN</label>
                <div class="dna-box" id="dna-content">Đang cập nhật...</div>
                
                <label style="color: var(--accent-color); margin: 16px 0 8px 0; display:block; font-weight:600;">KỊCH BẢN PHÂN CẢNH (11 CHỐT KHÓA)</label>
                <div id="shots-container"></div>
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
                shots: parseInt(document.getElementById('shots').value) || 4
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
                
                document.getElementById('dna-content').innerText = res.dna;
                
                let container = document.getElementById('shots-container');
                container.innerHTML = '';
                res.shots_list.forEach((shot, index) => {
                    container.innerHTML += `
                        <div class="shot-box">
                            <h3>Phân cảnh ${index + 1}: ${shot.title}</h3>
                            <p style="font-size: 0.9rem; color: #c9d1d9;">${shot.description}</p>
                        </div>
                    `;
                });

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
    return {
        "dna": f"Không gian chủ đạo tại '{req.project_name}' với phong cách {req.art_style}, khắc họa chiều sâu nội tâm và âm hưởng tự nhiên.",
        "shots_list": [
            {"title": "Mở đầu sương sớm", "description": f"Toàn cảnh phố núi Kon Tum theo cốt truyện: {req.story_prompt[:50]}... Ánh sáng vàng ấm áp xuyên qua làn sương."},
            {"title": "Nhịp sống bên dòng sông", "description": "Cận cảnh dòng nước Đắk Bla cuộn chảy nhẹ nhàng dưới chân cầu treo, nhịp sống chậm rãi bắt đầu."},
            {"title": "Góc phố hoài niệm", "description": "Góc máy ngang tầm mắt ghi lại mái ngói rêu phong và tiếng vọng thời gian qua từng khung hình."},
            {"title": "Khoảnh khắc đọng lại", "description": "Khung hình khép lại với sắc thái cảm xúc sâu lắng, hoàn thiện thước phim ngắn nghệ thuật."}
        ]
    }
    
