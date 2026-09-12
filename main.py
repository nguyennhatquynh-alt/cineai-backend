import os
import random
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import google.generativeai as genai

app = FastAPI(title="CineAI Studio Production Backend", version="11.0")

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

# --- 2. HÀM XOAY VÒNG KHÓA GEMINI CHO ĐẠO DIỄN ---
def get_gemini_client_and_key():
    if not GEMINI_KEYS:
        return None, "Chưa cấu hình GEMINI_API_KEYS"
    selected_key = random.choice(GEMINI_KEYS)
    genai.configure(api_key=selected_key)
    key_hint = f"...{selected_key[-4:]}" if len(selected_key) > 4 else "Key"
    return genai.GenerativeModel('gemini-1.5-flash'), key_hint

# --- 3. GIAO DIỆN WEB DASHBOARD & ĐIỀU KHIỂN ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render_dashboard(
        story="", 
        result_html="<p style='color: #94a3b8;'>Nhập cốt truyện hoặc ý tưởng phim ngắn bên dưới để Đạo diễn Gemini tiến hành phân rã 11 chốt khóa...</p>"
    )

@app.post("/produce", response_class=HTMLResponse)
async def produce_film(request: Request, story: str = Form(...)):
    model, key_hint = get_gemini_client_and_key()
    
    if not model:
        output_html = "<p style='color: #ef4444;'>❌ Lỗi: Chưa cấu hình khóa Gemini trong hệ thống biến môi trường!</p>"
        return render_dashboard(story, output_html)

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

    try:
        response = model.generate_content(director_prompt)
        raw_text = response.text
        formatted_text = raw_text.replace("\n", "<br>")
        
        output_html = f"""
        <div style="background: #0f172a; padding: 15px; border-radius: 8px; border-left: 4px solid #38bdf8; margin-top: 15px;">
            <h3 style="color: #38bdf8; margin-top: 0;">✨ KẾT QUẢ PHÂN RÃ TỪ ĐẠO DIỄN (Sử dụng Gemini {key_hint}):</h3>
            <div style="color: #f8fafc; line-height: 1.6; font-size: 14px;">{formatted_text}</div>
        </div>
        """
    except Exception as e:
        output_html = f"<p style='color: #ef4444;'>❌ Lỗi gọi API Gemini: {str(e)}</p>"

    return render_dashboard(story, output_html)

def render_dashboard(story: str, result_html: str):
    s_stab = "🟩 Đã kết nối" if STABILITY_KEY else "⚠️ Chưa cấu hình"
    s_rep = "🟩 Đã kết nối (Khóa nhân vật/bối cảnh)" if REPLICATE_KEY else "⚠️ Chưa cấu hình"
    s_runway = "🟩 Đã kết nối" if RUNWAY_KEY else "⚠️ Chưa cấu hình"
    s_eleven = "🟩 Đã kết nối" if ELEVENLABS_KEY else "⚠️ Chưa cấu hình"
    s_openai = "🟩 Đã kết nối" if OPENAI_KEY else "⚠️ Chưa cấu hình"
    s_gemini = f"🟩 Sẵn sàng ({len(GEMINI_KEYS)} Key xoay vòng)" if GEMINI_KEYS else "⚠️ Chưa có key"

    return HTMLResponse(content=f"""
    <html>
        <head>
            <title>CineAI Studio - Trạm Sản Xuất Phim Ngắn</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
                .container {{ max-width: 850px; margin: auto; }}
                .card {{ background: #1e293b; padding: 25px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); margin-bottom: 20px; }}
                h2 {{ color: #38bdf8; margin-top: 0; }}
                .status-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px; background: #0f172a; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                textarea {{ width: 100%; height: 100px; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 8px; padding: 12px; font-size: 14px; box-sizing: border-box; resize: vertical; }}
                button {{ background: #0ea5e9; color: white; border: none; padding: 12px 20px; font-size: 15px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%; margin-top: 10px; transition: background 0.2s; }}
                button:hover {{ background: #0284c7; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h2>🎬 CineAI Studio v11.0 - Trạm Điều Khiển Toàn Diện</h2>
                    <p style="color: #94a3b8; font-size: 14px;">Hệ thống sản xuất phim ngắn tự động hóa 11 tầng tích hợp AI đa mô hình.</p>
                    
                    <div class="status-grid">
                        <div><strong>Đạo diễn Gemini:</strong> {s_gemini}</div>
                        <div><strong>Replicate (Khóa nhân vật):</strong> {s_rep}</div>
                        <div><strong>Stability AI (Keyframe):</strong> {s_stab}</div>
                        <div><strong>Runway Gen-3 (Video):</strong> {s_runway}</div>
                        <div><strong>ElevenLabs (Lồng tiếng):</strong> {s_eleven}</div>
                        <div><strong>OpenAI Whisper (Phụ đề):</strong> {s_openai}</div>
                    </div>

                    <form action="/produce" method="post">
                        <label style="font-weight: bold; font-size: 14px; display: block; margin-bottom: 8px;">Nhập cốt truyện / Ý tưởng phim ngắn:</label>
                        <textarea name="story" placeholder="Nhập ý tưởng tại đây (Ví dụ: Một buổi chiều mưa ở phố cổ...)">{story}</textarea>
                        <button type="submit">🚀 Kích Hoạt Đạo Diễn & Sản Xuất Toàn Bộ</button>
                    </form>

                    {result_html}
                </div>
            </div>
        </body>
    </html>
    """)

# --- 4. KHỞI ĐỘNG SERVER UVICORN ---
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
