import os
import random
import requests
import hashlib
import secrets
import json
import html
from datetime import datetime
from fastapi import FastAPI, Request, Form, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="CineAI Studio Pro 3.0 - Production Backend", version="13.2")

# --- 1. KẾT NỐI SUPABASE CLOUD DATABASE VĨNH VIỄN ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://djkxwtkhmjpehgqvhkee.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def load_users():
    if not SUPABASE_KEY:
        print("⚠️ Chưa cấu hình SUPABASE_KEY, dùng bộ nhớ tạm!")
        return {}
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store?id=eq.1&select=payload"
        response = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0].get("payload", {})
    except Exception as e:
        print("Lỗi tải từ Supabase:", e)
    return {}

def save_users():
    if not SUPABASE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store"
        payload = {"id": 1, "payload": USERS_DB}
        headers = get_supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print("Lỗi lưu lên Supabase:", e)

USERS_DB = load_users()
ACTIVE_SESSIONS = {} # {session_token: username}

# --- 2. CÀI ĐẶT API KEYS ---
GEMINI_KEYS_RAW = os.getenv("GEMINI_API_KEYS", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_RAW.split(",") if k.strip()]

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
        payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
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

def hash_password(password: str, salt: str = None):
    if not salt:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pwd_hash, salt

# --- 3. ĐIỀU HƯỚNG & XỬ LÝ NGHIỆP VỤ ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, session_token: str = Cookie(None), view: str = "studio", edit_id: str = None):
    username = ACTIVE_SESSIONS.get(session_token)
    if not username:
        return render_auth_page(error="")
    
    user_projects = USERS_DB.get(username, {}).get("projects", [])
    current_story = ""
    result_html = "<div style='color: #94a3b8; font-size: 15px; padding: 10px;'>👋 Chào mừng bạn đến với Cine AI Studio Pro 3.0. Nhập ý tưởng kịch bản bên dưới để Đạo diễn ảo bắt đầu vận hành 12 tầng...</div>"
    
    if edit_id:
        for p in user_projects:
            if p["id"] == edit_id:
                current_story = p["story"]
                result_html = f"""
                <div style="background: #0f172a; padding: 20px; border-radius: 12px; border-left: 5px solid #22c55e; margin-top: 20px;">
                    <h3 style="color: #22c55e; margin-top: 0; font-size: 18px;">📂 Đang tải dự án nháp: {p['title']}</h3>
                    <div style="color: #f8fafc; line-height: 1.7; font-size: 15px;">{p['result']}</div>
                </div>
                """
                break

    return render_studio_dashboard(username, current_story, result_html, user_projects, active_tab=view)

@app.post("/auth/register", response_class=HTMLResponse)
async def register(username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    if not username or not password:
        return render_auth_page(error="Vui lòng điền đầy đủ thông tin!")
    if username in USERS_DB:
        return render_auth_page(error="Tài khoản này đã tồn tại trên hệ thống! Vui lòng đăng nhập.")
    
    pwd_hash, salt = hash_password(password)
    USERS_DB[username] = {"password_hash": pwd_hash, "salt": salt, "projects": []}
    save_users() # Lưu vĩnh viễn lên Supabase
    return render_auth_page(error="", success="✨ Đăng ký thành công! Bạn có thể đăng nhập ngay bên dưới.")

@app.post("/auth/login", response_class=HTMLResponse)
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    user_data = USERS_DB.get(username)
    if not user_data:
        return render_auth_page(error="Tài khoản chưa tồn tại! Vui lòng bấm sang tab Đăng Ký để tạo tài khoản mới.")
    
    pwd_hash, _ = hash_password(password, user_data["salt"])
    if pwd_hash != user_data["password_hash"]:
        return render_auth_page(error="Mật khẩu không chính xác! Vui lòng kiểm tra lại.")
    
    session_token = secrets.token_hex(32)
    ACTIVE_SESSIONS[session_token] = username
    
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="session_token", value=session_token, httponly=True)
    return resp

@app.get("/auth/logout", response_class=HTMLResponse)
async def logout(session_token: str = Cookie(None)):
    if session_token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_token]
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(key="session_token")
    return resp

@app.post("/produce", response_class=HTMLResponse)
async def produce_film(request: Request, story: str = Form(""), session_token: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_token)
    if not username:
        return RedirectResponse(url="/", status_code=303)

    if not story.strip():
        return render_studio_dashboard(username, "", "<p style='color: #ef4444; font-size: 16px;'>❌ Vui lòng nhập nội dung cốt truyện!</p>", USERS_DB.get(username, {}).get("projects", []))

    director_prompt = f"""
    Bạn là Đạo diễn ảo của Cine AI Studio Pro 3.0. Dựa trên cốt truyện: "{story}", 
    hãy thiết kế hồ sơ sản xuất chi tiết qua 12 tầng điện ảnh (Tầng 1 đến 12):
    - Phân tích cốt truyện, bối cảnh, nhân vật, góc máy, visual prompt, âm thanh Audiophile 3D.
    """

    raw_text, info_hint = call_gemini_direct(director_prompt)
    if not raw_text:
        output_html = f"<p style='color: #ef4444; font-size: 16px;'>❌ {info_hint}</p>"
    else:
        formatted_text = raw_text.replace("\n", "<br>")
        output_html = f"""
        <div style="background: #0f172a; padding: 20px; border-radius: 12px; border-left: 5px solid #38bdf8; margin-top: 20px;">
            <h3 style="color: #38bdf8; margin-top: 0; font-size: 18px;">✨ HỒ SƠ 12 TẦNG SẢN XUẤT (Model: {info_hint}):</h3>
            <div style="color: #f8fafc; line-height: 1.7; font-size: 15px;">{formatted_text}</div>
        </div>
        """

    return render_studio_dashboard(username, story, output_html, USERS_DB.get(username, {}).get("projects", []))

@app.post("/project/save", response_class=HTMLResponse)
async def save_project(story: str = Form(""), result_html: str = Form(""), session_token: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_token)
    if not username:
        return RedirectResponse(url="/", status_code=303)
    
    if not story.strip():
        return RedirectResponse(url="/?view=studio", status_code=303)
    
    project_id = secrets.token_hex(4)
    title = story[:35] + "..." if len(story) > 35 else story
    time_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if not result_html or "HỒ SƠ 12 TẦNG" not in result_html:
        result_html = f"<div style='color: #94a3b8; font-size: 15px;'>📝 <b>Ý tưởng thô:</b> {html.escape(story)}</div>"

    new_proj = {
        "id": project_id,
        "title": title,
        "story": story,
        "result": result_html,
        "time": time_str
    }
    
    if username not in USERS_DB:
        USERS_DB[username] = {"password_hash": "", "salt": "", "projects": []}
    
    USERS_DB[username]["projects"].insert(0, new_proj)
    save_users() # Lưu vĩnh viễn lên Supabase
    return RedirectResponse(url="/?view=library", status_code=303)

# --- 4. GIAO DIỆN HTML ---
def render_auth_page(error="", success=""):
    err_div = f"<div style='background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #fca5a5; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 14px;'>{error}</div>" if error else ""
    suc_div = f"<div style='background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; color: #86efac; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 14px;'>{success}</div>" if success else ""
    return HTMLResponse(content=f"""
    <html>
        <head>
            <title>Cine AI Studio Pro 3.0 - Đăng Nhập / Đăng Ký</title>
            <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 15px; box-sizing: border-box; }}
                .auth-card {{ background: #1e293b; padding: 25px; border-radius: 16px; width: 100%; max-width: 400px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); border: 1px solid #334155; }}
                h2 {{ color: #38bdf8; text-align: center; margin-top: 0; font-size: 22px; }}
                input {{ width: 100%; background: #0f172a; color: #fff; border: 2px solid #475569; border-radius: 10px; padding: 14px; font-size: 16px; margin-bottom: 15px; box-sizing: border-box; }}
                input:focus {{ border-color: #38bdf8; outline: none; }}
                button {{ background: #0284c7; color: white; border: none; padding: 16px; font-size: 16px; font-weight: bold; border-radius: 10px; cursor: pointer; width: 100%; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4); }}
                button:hover {{ background: #0369a1; }}
                .tabs {{ display: flex; margin-bottom: 20px; border-bottom: 2px solid #334155; }}
                .tab {{ flex: 1; text-align: center; padding: 12px; cursor: pointer; color: #94a3b8; font-weight: bold; font-size: 15px; }}
                .tab.active {{ color: #38bdf8; border-bottom: 2px solid #38bdf8; margin-bottom: -2px; }}
            </style>
        </head>
        <body>
            <div class="auth-card">
                <h2>🎬 Cine AI Studio Pro</h2>
                <p style="text-align: center; color: #94a3b8; font-size: 13px; margin-top: -5px; margin-bottom: 20px;">Hệ thống sản xuất phim ngắn 12 tầng tự động</p>
                {err_div}{suc_div}
                <div class="tabs">
                    <div id="tab-login" class="tab active" onclick="switchTab('login')">Đăng Nhập</div>
                    <div id="tab-reg" class="tab" onclick="switchTab('reg')">Đăng Ký</div>
                </div>
                <form id="form-login" action="/auth/login" method="post">
                    <input type="text" name="username" placeholder="Tên đăng nhập / Email" required>
                    <input type="password" name="password" placeholder="Mật khẩu" required>
                    <button type="submit">🔑 Đăng Nhập Hệ Thống</button>
                </form>
                <form id="form-reg" action="/auth/register" method="post" style="display:none;">
                    <input type="text" name="username" placeholder="Tên đăng nhập mới" required>
                    <input type="password" name="password" placeholder="Mật khẩu bảo mật" required>
                    <button type="submit" style="background: #0d9488; box-shadow: 0 4px 12px rgba(13, 148, 136, 0.4);">✨ Tạo Tài Khoản Mới</button>
                </form>
            </div>
            <script>
                function switchTab(t) {{
                    if(t=='login') {{
                        document.getElementById('form-login').style.display='block';
                        document.getElementById('form-reg').style.display='none';
                        document.getElementById('tab-login').classList.add('active');
                        document.getElementById('tab-reg').classList.remove('active');
                    }} else {{
                        document.getElementById('form-login').style.display='none';
                        document.getElementById('form-reg').style.display='block';
                        document.getElementById('tab-reg').classList.add('active');
                        document.getElementById('tab-login').classList.remove('active');
                    }}
                }}
            </script>
        </body>
    </html>
    """)

def render_studio_dashboard(username: str, story: str, result_html: str, projects: list, active_tab: str = "studio"):
    proj_html = ""
    if not projects:
        proj_html = "<p style='color: #94a3b8; text-align: center; padding: 30px; font-size: 14px;'>Chưa có dự án nháp nào. Hãy nhập ý tưởng và bấm lưu nhé!</p>"
    else:
        for p in projects:
            proj_html += f"""
            <div style="background: #0f172a; padding: 15px; border-radius: 12px; margin-bottom: 12px; border: 1px solid #334155; display: flex; justify-content: space-between; align-items: center;">
                <div style="overflow: hidden; padding-right: 10px;">
                    <div style="color: #38bdf8; font-weight: bold; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{html.escape(p['title'])}</div>
                    <div style="color: #94a3b8; font-size: 12px; margin-top: 4px;">🕒 {p['time']}</div>
                </div>
                <a href="/?view=studio&edit_id={p['id']}" style="background: #0284c7; color: white; padding: 10px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: bold; white-space: nowrap;">📂 Mở Xem</a>
            </div>
            """

    studio_display = "block" if active_tab == "studio" else "none"
    library_display = "block" if active_tab == "library" else "none"
    studio_active = "active" if active_tab == "studio" else ""
    library_active = "active" if active_tab == "library" else ""

    safe_story = html.escape(story, quote=True)
    safe_result = html.escape(result_html, quote=True)

    return HTMLResponse(content=f"""
    <html>
        <head>
            <title>Cine AI Studio Pro 3.0</title>
            <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; padding: 15px; margin: 0; }}
                .container {{ max-width: 900px; margin: auto; }}
                .card {{ background: #1e293b; padding: 20px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); margin-bottom: 20px; border: 1px solid #334155; }}
                .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 12px; }}
                h2 {{ color: #38bdf8; margin: 0; font-size: 18px; }}
                .logout-btn {{ background: #ef4444; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold; }}
                .nav-tabs {{ display: flex; gap: 10px; margin-bottom: 20px; }}
                .nav-tab {{ flex: 1; text-align: center; padding: 12px; background: #0f172a; border-radius: 10px; color: #94a3b8; text-decoration: none; font-weight: bold; font-size: 14px; border: 1px solid #334155; }}
                .nav-tab.active {{ background: #0284c7; color: white; border-color: #0284c7; }}
                textarea {{ width: 100%; height: 140px; background: #0f172a; color: #fff; border: 2px solid #475569; border-radius: 10px; padding: 14px; font-size: 15px; box-sizing: border-box; resize: vertical; }}
                textarea:focus {{ border-color: #38bdf8; outline: none; }}
                button {{ background: #0284c7; color: white; border: none; padding: 15px; font-size: 16px; font-weight: bold; border-radius: 10px; cursor: pointer; width: 100%; margin-top: 12px; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3); }}
                button:hover {{ background: #0369a1; }}
                .save-btn {{ background: #10b981 !important; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); }}
                .save-btn:hover {{ background: #059669 !important; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h2>🎬 Cine AI Pro 3.0</h2>
                        <div>
                            <span style="color: #cbd5e1; font-size: 13px; margin-right: 8px;">👤 {username}</span>
                            <a href="/auth/logout" class="logout-btn">Thoát</a>
                        </div>
                    </div>

                    <div class="nav-tabs">
                        <a href="/?view=studio" class="nav-tab {studio_active}">⚡ Studio Sản Xuất</a>
                        <a href="/?view=library" class="nav-tab {library_active}">📂 Thư Viện Nháp ({len(projects)})</a>
                    </div>

                    <div id="tab-studio" style="display: {studio_display};">
                        <form action="/produce" method="post">
                            <label style="font-weight: bold; display: block; margin-bottom: 8px; font-size: 14px; color: #cbd5e1;">Nhập cốt truyện / Ý tưởng phim ngắn (12 Tầng):</label>
                            <textarea name="story" placeholder="Nhập ý tưởng của bạn tại đây...">{story}</textarea>
                            <button type="submit">🚀 Kích Hoạt Đạo Diễn Ảo & 12 Tầng</button>
                        </form>

                        <form action="/project/save" method="post" style="margin-top: 5px;">
                            <input type="hidden" name="story" value="{safe_story}">
                            <input type="hidden" name="result_html" value="{safe_result}">
                            <button type="submit" class="save-btn">💾 Lưu Ý Tưởng / Dự Án Nháp Ngay</button>
                        </form>

                        {result_html}
                    </div>

                    <div id="tab-library" style="display: {library_display};">
                        <h3 style="color: #38bdf8; font-size: 16px; margin-top: 0; margin-bottom: 15px;">📚 Kho Dự Án Nháp Của Bạn</h3>
                        {proj_html}
                    </div>
                </div>
            </div>
        </body>
    </html>
    """)
    
