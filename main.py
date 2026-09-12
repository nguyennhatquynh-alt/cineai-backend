import os
import random
import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse

app = FastAPI(title="CineAI Studio Production Backend", version="11.5")

# --- 1. TỰ ĐỘNG QUÉT & CÀI ĐẶT API KEYS (FALLBACK THÔNG MINH) ---
GEMINI_KEYS_RAW = os.getenv("GEMINI_API_KEYS", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_RAW.split(",") if k.strip()]

ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
RUNWAY_KEY = os.getenv("RUNWAY_API_KEY", "")
REPLICATE_KEY = os.getenv("REPLICATE_API_TOKEN", "")

STABILITY_KEY = (
    os.getenv("STABILITY_API_KEY") 
    or os.getenv("STABILITY_KEY_1") 
    or os.getenv("STABILITY_KEY_2") 
    or ""
)

OPENAI_KEY = (
    os.getenv("OPENAI_API_KEY") 
    or os.getenv("OPENAI_WHISPER_KEY") 
    or ""
)

# --- 2. HÀM GỌI GEMINI HTTP API CHUẨN V1BETA & XOAY VÒNG KEY ---
def call_gemini_direct(prompt_text):
    if not GEMINI_KEYS:
        return None, "Chưa cấu hình GEMINI_API_KEYS trong biến môi trường!"
    
    selected_key = random.choice(GEMINI_KEYS)
    key_hint = f"...{selected_key[-4:]}" if len(selected_key) > 4 else "Key"
    
    models_to_try = ['gemini-1.5-flash', 'gemini-pro']
    
    last_error = ""
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={selected_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                text_result = data["candidates"][0]["content"]["parts"][0]["text"]
                return text_result, f"{model_name} ({key_hint})"
            else:
                last_error = response.text
        except Exception as e:
            last_error = str(e)
            
    return None, f"Lỗi gọi Gemini API: {last_error}"

# --- 3. ĐIỀU HƯỚNG GỘP (CHỐNG LỖI METHOD NOT ALLOWED TUYỆT ĐỐI) ---
@app.get("/", response_class=HTMLResponse)
@app.post("/", response_class=HTMLResponse)
async def home_or_produce(request: Request, story: str = Form(None)):
    result_html = "<div style='color: #94a3b8; font-size: 16px; padding: 10px;'>👋 Nhập ý tưởng phim ngắn bên dưới để Đạo diễn Gemini tiến hành phân rã 11 chốt khóa sản xuất...</div>"
    
    if request.method == "POST" and story:
        if not story.strip():
            result_html = "<p style='color: #ef4444; font-size: 16px;'>❌ Vui lòng nhập nội dung cốt truyện!</p>"
        else:
            director_prompt = f"""
            Bạn là một đạo diễn điện ảnh gạo cội. Dựa trên cốt truyện sau: "{story}", 
            hãy thiết kế hồ sơ sản xuất chi tiết theo chuẩn CineAI Studio gồm 2 phần:
            
            ### PHẦN 1: 11 CHỐT KHÓA ĐẠO DIỄN (DIRECTOR'S KEY BEATS)
            - Chia cốt truyện thành các phân cảnh từ Beat 1 đến Beat 11 với góc máy, ánh sáng, hành động cụ thể.
            
            ### PHẦN 2: THÔNG SỐ KỸ THUẬT TỪNG TẦNG
            - Visual Prompt cho Stability AI / Replicate (Khóa cứng nhân vật, bối cảnh, phục trang).
            - Prompt chuyển động cho Runway Gen-3.
            - Cấu trúc âm nhạc Audiophile 3D cho Suno.
            """

            raw_text, info_hint = call_gemini_direct(director_prompt)
            
            if not raw_text:
                result_html = f"<p style='color: #ef4444; font-size: 16px;'>❌ {info_hint}</p>"
            else:
                formatted_text = raw_text.replace("\n", "<br>")
                result_html = f"""
                <div style="background: #0f172a; padding: 20px; border-radius: 12px; border-left: 5px solid #38bdf8; margin-top: 20px;">
                    <h3 style="color: #38bdf8; margin-top: 0; font-size: 18px;">✨ KẾT QUẢ PHÂN RÃ TỪ ĐẠO DIỄN (Model: {info_hint}):</h3>
                    <div style="color: #f8fafc; line-height: 1.7; font-size: 15px;">{formatted_text}</div>
                </div>
                """
        current_story = story
    else:
        current_story = ""

    return render_dashboard(current_story, result_html)

def render_dashboard(story: str, result_html: str):
    s_stab = "🟩 Đã kết nối" if STABILITY_KEY else "⚠️ Chưa cấu hình"
    s_rep = "🟩 Đã kết nối" if REPLICATE_KEY else "⚠️ Chưa cấu hình"
    s_runway = "🟩 Đã kết nối" if RUNWAY_KEY else "⚠️ Chưa cấu hình"
    s_eleven = "🟩 Đã kết nối" if ELEVENLABS_KEY else "⚠️ Chưa cấu hình"
    s_openai = "🟩 Đã kết nối" if OPENAI_KEY else "⚠️ Chưa cấu hình"
    s_gemini = f"🟩 Sẵn sàng ({len(GEMINI_KEYS)} Key)" if GEMINI_KEYS else "⚠️ Chưa có key"

    return HTMLResponse(content=f"""
    <html>
        <head>
            <title>CineAI Studio - Trạm Sản Xuất Phim Ngắn</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; padding: 15px; margin: 0; }}
                .container {{ max-width: 900px; margin: auto; }}
                .card {{ background: #1e293b; padding: 20px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); margin-bottom: 20px; }}
                h2 {{ color: #38bdf8; margin-top: 0; font-size: 22px; }}
                .status-grid {{ display: grid; grid-template-columns: 1fr; gap: 8px; font-size: 14px; background: #0f172a; padding: 15px; border-radius: 10px; margin-bottom: 20px; }}
                @media(min-width: 600px) {{ .status-grid {{ grid-template-columns: 1fr 1fr; }} }}
                label {{ font-weight: bold; font-size: 16px; display: block; margin-bottom: 10px; color: #cbd5e1; }}
                textarea {{ width: 100%; height: 140px; background: #0f172a; color: #fff; border: 2px solid #475569; border-radius: 10px; padding: 14px; font-size: 16px; box-sizing: border-box; resize: vertical; }}
                textarea:focus {{ border-color: #38bdf8; outline: none; }}
                button {{ background: #0284c7; color: white; border: none; padding: 16px 20px; font-size: 17px; font-weight: bold; border-radius: 10px; cursor: pointer; width: 100%; margin-top: 15px; transition: background 0.2s; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4); }}
                button:hover {{ background: #0369a1; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h2>🎬 CineAI Studio v11.5 - Trạm Điều Khiển</h2>
                    <p style="color: #94a3b8; font-size: 15px; margin-bottom: 15px;">Hệ thống sản xuất phim ngắn tự động hóa 11 tầng tích hợp AI đa mô hình.</p>
                    
                    <div class="status-grid">
                        <div><strong>Đạo diễn Gemini:</strong> {s_gemini}</div>
                        <div><strong>Replicate:</strong> {s_rep}</div>
                        <div><strong>Stability AI:</strong> {s_stab}</div>
                        <div><strong>Runway Gen-3:</strong> {s_runway}</div>
                        <div><strong>ElevenLabs:</strong> {s_eleven}</div>
                        <div><strong>OpenAI Whisper:</strong> {s_openai}</div>
                    </div>

                    <form action="/" method="post">
                        <label>Nhập cốt truyện / Ý tưởng phim ngắn:</label>
                        <textarea name="story" placeholder="Nhập ý tưởng tại đây...">{story}</textarea>
                        <button type="submit">🚀 Kích Hoạt Đạo Diễn & Sản Xuất Toàn Bộ</button>
                    </form>

                    {result_html}
                </div>
            </div>
        </body>
    </html>
    """)
    
