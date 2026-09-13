import os
import random
import requests
import hashlib
import secrets
import json
import html
from datetime import datetime
from fastapi import FastAPI, Request, Form, Response, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse


app = FastAPI(title="CineAI Studio Pro 3.0 - Production Backend", version="14.9")


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
        return {}
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store?id=eq.1&select=payload"
        response = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and data[0].get("payload"):
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
        print("Lỗi lưu Supabase:", e)


USERS_DB = load_users()
ACTIVE_SESSIONS = {}


# --- HÀM GỌI GEMINI: BẮT LỖI CHI TIẾT TỪ GOOGLE ---
def get_gemini_keys():
    raw = os.getenv("GEMINI_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def call_gemini_direct(prompt_text):
    keys = get_gemini_keys()
    if not keys:
        return None, "Chưa cấu hình GEMINI_API_KEYS trên Render!"
    
    selected_key = random.choice(keys)
    models_to_try = ['gemini-1.5-flash', 'gemini-pro']
    
    for model_name in models_to_try:
        headers = {"Content-Type": "application/json"}
        # Tự động nhận diện định dạng Token/Key
        if selected_key.startswith("AQ."):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers["Authorization"] = f"Bearer {selected_key}"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={selected_key}"
            
        payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                text_result = data["candidates"][0]["content"]["parts"][0]["text"]
                return text_result, model_name
            else:
                # Nếu lỗi, ép trả về nguyên văn thông báo lỗi của Google
                try:
                    error_detail = response.json().get("error", {}).get("message", response.text)
                    return None, f"Google báo lỗi ({response.status_code}): {error_detail}"
                except:
                    return None, f"Google báo lỗi HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return None, f"Lỗi hệ thống khi gọi mạng: {str(e)}"
            
    return None, "Lỗi gọi Gemini API không xác định"


@app.post("/api/cineai/chat")
async def chat_with_director(data: dict):
    user_message = data.get("message", "")
    if not user_message:
        return JSONResponse({"reply": "Vui lòng nhập nội dung trao đổi!"})
    
    prompt = (
        "Bạn là Đạo diễn ảo chuyên nghiệp của hệ thống Cine AI Studio Pro 3.0. "
        "Hãy phản hồi trực tiếp, tư vấn và cùng người dùng thảo luận kịch bản phim ngắn "
        "tại Tầng 7 & 8 một cách gần gũi, chuyên nghiệp và chi tiết.\n\n"
        f"Yêu cầu từ người dùng: {user_message}"
    )
    
    reply_text, err_msg = call_gemini_direct(prompt)
    if not reply_text:
        reply_text = f"⚠️ {err_msg}"
        
    return JSONResponse({"reply": reply_text})


def hash_password(password: str, salt: str = None):
    if not salt:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pwd_hash, salt
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, session_token: str = Cookie(None), view: str = "studio", edit_id: str = None):
    global USERS_DB
    USERS_DB = load_users()
    
    username = ACTIVE_SESSIONS.get(session_token)
    if not username:
        return render_auth_page(error="")
    
    user_projects = USERS_DB.get(username, {}).get("projects", [])
    current_title = ""
    current_edit_id = edit_id if edit_id else ""
    chat_initial_html = (
        "<div style='background: #0284c7; color: white; padding: 10px 14px; border-radius: 10px; max-width: 85%; align-self: flex-start; font-size: 14px;'>"
        "🎬 Chào anh! Em là Đạo diễn ảo đây. Chúng ta hãy cùng trò chuyện, bàn về ý tưởng hoặc gọt giũa kịch bản trực tiếp tại Tầng 7 & 8 nhé. Anh muốn bắt đầu câu chuyện thế nào ạ?"
        "</div>"
    )
    
    if edit_id:
        for p in user_projects:
            if p["id"] == edit_id:
                current_edit_id = p["id"]
                current_title = p["title"]
                if p.get("result"):
                    chat_initial_html = p["result"]
                break


    return render_studio_dashboard(username, current_edit_id, current_title, chat_initial_html, user_projects, active_tab=view)


@app.post("/auth/register", response_class=HTMLResponse)
async def register(username: str = Form(...), password: str = Form(...)):
    global USERS_DB
    USERS_DB = load_users()
    username = username.strip()
    if not username or not password:
        return render_auth_page(error="Vui lòng điền đầy đủ thông tin!")
    if username in USERS_DB:
        return render_auth_page(error="Tài khoản đã tồn tại!")
    
    pwd_hash, salt = hash_password(password)
    USERS_DB[username] = {"password_hash": pwd_hash, "salt": salt, "projects": []}
    save_users()
    return render_auth_page(error="", success="✨ Đăng ký thành công! Vui lòng đăng nhập.")


@app.post("/auth/login", response_class=HTMLResponse)
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    global USERS_DB
    USERS_DB = load_users()
    username = username.strip()
    user_data = USERS_DB.get(username)
    if not user_data:
        return render_auth_page(error="Tài khoản chưa tồn tại!")
    
    pwd_hash, _ = hash_password(password, user_data["salt"])
    if pwd_hash != user_data["password_hash"]:
        return render_auth_page(error="Mật khẩu không chính xác!")
    
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


@app.post("/project/save", response_class=HTMLResponse)
async def save_project(edit_id: str = Form(""), title: str = Form(""), chat_html: str = Form(""), session_token: str = Cookie(None)):
    global USERS_DB
    USERS_DB = load_users()
    username = ACTIVE_SESSIONS.get(session_token)
    if not username:
        return RedirectResponse(url="/", status_code=303)
    
    clean_title = title.strip() if title.strip() else "Dự án phòng chat không tên"
    time_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if username not in USERS_DB:
        USERS_DB[username] = {"password_hash": "", "salt": "", "projects": []}
    user_projects = USERS_DB[username]["projects"]


    updated = False
    if edit_id:
        for p in user_projects:
            if p["id"] == edit_id:
                p["title"] = clean_title
                p["result"] = chat_html
                p["time"] = time_str
                updated = True
                break


    if not updated:
        project_id = secrets.token_hex(4)
        new_proj = {
            "id": project_id,
            "title": clean_title,
            "result": chat_html,
            "time": time_str
        }
        user_projects.insert(0, new_proj)


    save_users()
    return RedirectResponse(url="/?view=library", status_code=303)


@app.post("/project/delete", response_class=HTMLResponse)
async def delete_project(project_id: str = Form(...), session_token: str = Cookie(None)):
    global USERS_DB
    USERS_DB = load_users()
    username = ACTIVE_SESSIONS.get(session_token)
    if not username:
        return RedirectResponse(url="/", status_code=303)
    
    if username in USERS_DB:
        projects = USERS_DB[username].get("projects", [])
        USERS_DB[username]["projects"] = [p for p in projects if p["id"] != project_id]
        save_users()
        
    return RedirectResponse(url="/?view=library", status_code=303)
def render_auth_page(error="", success=""):
    err_div = "<div style='background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #fca5a5; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 14px;'>" + error + "</div>" if error else ""
    suc_div = "<div style='background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; color: #86efac; padding: 12px; border-radius: 8px; margin-bottom: 15px; font-size: 14px;'>" + success + "</div>" if success else ""
    
    html_content = (
        "<html>"
        "<head>"
        "<title>Cine AI Studio Pro 3.0 - Đăng Nhập</title>"
        "<meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<style>"
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 15px; box-sizing: border-box; }"
        ".auth-card { background: #1e293b; padding: 25px; border-radius: 16px; width: 100%; max-width: 400px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); border: 1px solid #334155; }"
        "h2 { color: #38bdf8; text-align: center; margin-top: 0; font-size: 22px; }"
        "input { width: 100%; background: #0f172a; color: #fff; border: 2px solid #475569; border-radius: 10px; padding: 14px; font-size: 16px; margin-bottom: 15px; box-sizing: border-box; }"
        "input:focus { border-color: #38bdf8; outline: none; }"
        "button { background: #0284c7; color: white; border: none; padding: 16px; font-size: 16px; font-weight: bold; border-radius: 10px; cursor: pointer; width: 100%; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4); }"
        "button:hover { background: #0369a1; }"
        ".tabs { display: flex; margin-bottom: 20px; border-bottom: 2px solid #334155; }"
        ".tab { flex: 1; text-align: center; padding: 12px; cursor: pointer; color: #94a3b8; font-weight: bold; font-size: 15px; }"
        ".tab.active { color: #38bdf8; border-bottom: 2px solid #38bdf8; margin-bottom: -2px; }"
        "</style>"
        "</head>"
        "<body>"
        "<div class='auth-card'>"
        "<h2>🎬 Cine AI Studio Pro</h2>"
        "<p style='text-align: center; color: #94a3b8; font-size: 13px; margin-top: -5px; margin-bottom: 20px;'>Hệ thống sản xuất phim ngắn tự động</p>"
        + err_div + suc_div +
        "<div class='tabs'>"
        "<div id='tab-login' class='tab active' onclick=\"switchTab('login')\">Đăng Nhập</div>"
        "<div id='tab-reg' class='tab' onclick=\"switchTab('reg')\">Đăng Ký</div>"
        "</div>"
        "<form id='form-login' action='/auth/login' method='post'>"
        "<input type='text' name='username' placeholder='Tên đăng nhập / Email' required>"
        "<input type='password' name='password' placeholder='Mật khẩu' required>"
        "<button type='submit'>🔑 Đăng Nhập Hệ Thống</button>"
        "</form>"
        "<form id='form-reg' action='/auth/register' method='post' style='display:none;'>"
        "<input type='text' name='username' placeholder='Tên đăng nhập mới' required>"
        "<input type='password' name='password' placeholder='Mật khẩu bảo mật' required>"
        "<button type='submit' style='background: #0d9488;'>✨ Tạo Tài Khoản Mới</button>"
        "</form>"
        "</div>"
        "<script>"
        "function switchTab(t) {"
        "  if(t=='login') {"
        "    document.getElementById('form-login').style.display='block';"
        "    document.getElementById('form-reg').style.display='none';"
        "    document.getElementById('tab-login').classList.add('active');"
        "    document.getElementById('tab-reg').classList.remove('active');"
        "  } else {"
        "    document.getElementById('form-login').style.display='none';"
        "    document.getElementById('form-reg').style.display='block';"
        "    document.getElementById('tab-reg').classList.add('active');"
        "    document.getElementById('tab-login').classList.remove('active');"
        "  }"
        "}"
        "</script>"
        "</body>"
        "</html>"
    )
    return HTMLResponse(content=html_content)


def render_studio_dashboard(username: str, edit_id: str, title: str, chat_html: str, projects: list, active_tab: str = "studio"):
    proj_html = ""
    if not projects:
        proj_html = "<p style='color: #94a3b8; text-align: center; padding: 30px; font-size: 14px;'>Chưa có dự án nào trong thư viện.</p>"
    else:
        for p in projects:
            proj_html += (
                "<div style='background: #0f172a; padding: 15px; border-radius: 12px; margin-bottom: 12px; border: 1px solid #334155; display: flex; justify-content: space-between; align-items: center;'>"
                "<div style='overflow: hidden; padding-right: 10px;'>"
                "<div style='color: #38bdf8; font-weight: bold; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>" + html.escape(p['title']) + "</div>"
                "<div style='color: #94a3b8; font-size: 12px; margin-top: 4px;'>🕒 " + p['time'] + "</div>"
                "</div>"
                "<div style='display: flex; gap: 8px; flex-shrink: 0;'>"
                "<a href='/?view=studio&edit_id=" + p['id'] + "' style='background: #0284c7; color: white; padding: 8px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;'>📂 Mở</a>"
                "<form action='/project/delete' method='post' onsubmit=\"return confirm('⚠️ Xóa vĩnh viễn dự án này?');\" style='margin:0;'>"
                "<input type='hidden' name='project_id' value='" + p['id'] + "'>"
                "<button type='submit' style='background: #ef4444; color: white; border: none; padding: 8px 10px; border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; width: auto;'>🗑️ Xóa</button>"
                "</form>"
                "</div>"
                "</div>"
            )


    studio_display = "block" if active_tab == "studio" else "none"
    library_display = "block" if active_tab == "library" else "none"
    studio_active = "active" if active_tab == "studio" else ""
    library_active = "active" if active_tab == "library" else ""


    escaped_title = html.escape(title, quote=True)
    len_proj_str = str(len(projects))


    html_content = (
        "<html>"
        "<head>"
        "<title>Cine AI Studio Pro 3.0 - Phòng Chat Đạo Diễn Ảo</title>"
        "<meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<style>"
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0f19; color: #f8fafc; padding: 15px; margin: 0; }"
        ".container { max-width: 900px; margin: auto; }"
        ".card { background: #1e293b; padding: 20px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); margin-bottom: 20px; border: 1px solid #334155; }"
        ".header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #334155; padding-bottom: 12px; }"
        "h2 { color: #38bdf8; margin: 0; font-size: 18px; }"
        ".logout-btn { background: #ef4444; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold; }"
        ".nav-tabs { display: flex; gap: 10px; margin-bottom: 20px; }"
        ".nav-tab { flex: 1; text-align: center; padding: 12px; background: #0f172a; border-radius: 10px; color: #94a3b8; text-decoration: none; font-weight: bold; font-size: 14px; border: 1px solid #334155; }"
        ".nav-tab.active { background: #0284c7; color: white; border-color: #0284c7; }"
        "input[type='text'], textarea { width: 100%; background: #0f172a; color: #fff; border: 2px solid #475569; border-radius: 10px; padding: 12px; font-size: 15px; box-sizing: border-box; margin-bottom: 12px; }"
        "input[type='text']:focus, textarea:focus { border-color: #38bdf8; outline: none; }"
        "button { background: #0284c7; color: white; border: none; padding: 14px; font-size: 15px; font-weight: bold; border-radius: 10px; cursor: pointer; width: 100%; margin-top: 10px; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3); }"
        "button:hover { background: #0369a1; }"
        ".save-btn { background: #10b981 !important; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); }"
        ".save-btn:hover { background: #059669 !important; }"
        "</style>"
        "</head>"
        "<body>"
        "<div class='container'>"
        "<div class='card'>"
        "<div class='header'>"
        "<h2>🎬 Cine AI Pro 3.0</h2>"
        "<div>"
        "<span style='color: #cbd5e1; font-size: 13px; margin-right: 8px;'>" + username + "</span>"
        "<a href='/auth/logout' class='logout-btn'>Thoát</a>"
        "</div>"
        "</div>"
        "<div class='nav-tabs'>"
        "<a href='/?view=studio' class='nav-tab " + studio_active + "'>⚡ Phòng Chat Studio</a>"
        "<a href='/?view=library' class='nav-tab " + library_active + "'>📂 Thư Viện Nháp (" + len_proj_str + ")</a>"
        "</div>"
        
        "<div id='tab-studio' style='display: " + studio_display + ";'>"
        "<label style='font-weight: bold; display: block; margin-bottom: 6px; font-size: 13px; color: #cbd5e1;'>Tiêu đề dự án:</label>"
        "<input type='text' id='project-title' placeholder='Nhập tiêu đề dự án...' value='" + escaped_title + "'>"
        
        "<label style='font-weight: bold; display: block; margin-bottom: 6px; font-size: 13px; color: #cbd5e1;'>💬 Phòng Trò Chuyện Trực Tiếp Với Đạo Diễn Ảo (Tầng 7 & 8):</label>"
        "<div id='chat-box' style='height: 350px; overflow-y: auto; background: #0f172a; padding: 15px; border-radius: 12px; border: 1px solid #475569; margin-bottom: 15px; display: flex; flex-direction: column; gap: 12px;'>"
        + chat_html +
        "</div>"
        
        "<textarea id='chat-input' placeholder='Nhập ý tưởng hoặc trao đổi trực tiếp với Đạo diễn ảo...' style='height: 90px;'></textarea>"
        "<button type='button' onclick='sendChatMessage()' style='background: #8b5cf6; margin-top: 0;'>💬 Gửi Trao Đổi (Real-time Chat)</button>"
        
        "<form action='/project/save' method='post' onsubmit='prepareSaveData()' style='margin-top: 15px;'>"
        "<input type='hidden' name='edit_id' value='" + edit_id + "'>"
        "<input type='hidden' id='save-title' name='title' value=''>"
        "<input type='hidden' id='save-chat-html' name='chat_html' value=''>"
        "<button type='submit' class='save-btn'>💾 Lưu Toàn Bộ Phòng Chat Vào Thư Viện Supabase</button>"
        "</form>"
        "</div>"
        
        "<div id='tab-library' style='display: " + library_display + ";'>"
        "<h3 style='color: #38bdf8; font-size: 16px; margin-top: 0; margin-bottom: 15px;'>📚 Kho Dự Án Nháp Của Bạn</h3>"
        + proj_html +
        "</div>"
        
        "</div>"
        "</div>"
        
        "<script>"
        "async function sendChatMessage() {"
        "  var inputField = document.getElementById('chat-input');"
        "  var message = inputField.value.trim();"
        "  var chatBox = document.getElementById('chat-box');"
        "  if (!message) return;"
        "  "
        "  chatBox.innerHTML += '<div style=\"background: #0d9488; color: white; padding: 10px 14px; border-radius: 10px; max-width: 85%; align-self: flex-end; font-size: 14px;\">' + message + '</div>';"
        "  inputField.value = '';"
        "  chatBox.scrollTop = chatBox.scrollHeight;"
        "  "
        "  var aiMsgId = 'ai-msg-' + Date.now();"
        "  chatBox.innerHTML += '<div id=\"' + aiMsgId + '\" style=\"background: #0284c7; color: white; padding: 10px 14px; border-radius: 10px; max-width: 85%; align-self: flex-start; font-size: 14px;\">⏳ Đạo diễn ảo đang suy nghĩ...</div>';"
        "  chatBox.scrollTop = chatBox.scrollHeight;"
        "  "
        "  try {"
        "    var response = await fetch('/api/cineai/chat', {"
        "      method: 'POST',"
        "      headers: { 'Content-Type': 'application/json' },"
        "      body: JSON.stringify({ message: message })"
        "    });"
        "    var data = await response.json();"
        "    var aiBubble = document.getElementById(aiMsgId);"
        "    aiBubble.innerText = data.reply;"
        "    chatBox.scrollTop = chatBox.scrollHeight;"
        "  } catch (err) {"
        "    document.getElementById(aiMsgId).innerText = '❌ Lỗi kết nối: ' + err.message;"
        "  }"
        "}"
        "function prepareSaveData() {"
        "  var tVal = document.getElementById('project-title').value;"
        "  var cVal = document.getElementById('chat-box').innerHTML;"
        "  document.getElementById('save-title').value = tVal;"
        "  document.getElementById('save-chat-html').value = cVal;"
        "}"
        "</script>"
        "</body>"
        "</html>"
    )
    return HTMLResponse(content=html_content)