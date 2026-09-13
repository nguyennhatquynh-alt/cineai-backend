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


app = FastAPI(title="CineAI Studio Pro 3.0 - Full Production Backend", version="15.5")


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
        return {"admin": {"password_hash": hashlib.sha256("admin123".encode()).hexdigest(), "salt": "", "projects": []}}
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store?id=eq.1&select=payload"
        response = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and data[0].get("payload"):
                return data[0].get("payload", {})
    except Exception as e:
        print("Lỗi tải từ Supabase:", e)
    return {"admin": {"password_hash": hashlib.sha256("admin123".encode()).hexdigest(), "salt": "", "projects": []}}


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
                return text_result, model_name
        except Exception:
            pass
            
    return None, "Lỗi kết nối Gemini API. Vui lòng kiểm tra lại key AQ."


@app.post("/api/cineai/chat")
async def chat_with_director(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"reply": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    user_message = data.get("message", "")
    project_title = data.get("title", "Dự án mới")
    
    if not user_message:
        return JSONResponse({"reply": "Vui lòng nhập nội dung trao đổi!"})
    
    prompt = (
        "Bạn là Đạo diễn ảo chuyên nghiệp của hệ thống Cine AI Studio Pro 3.0. "
        "Hãy phản hồi trực tiếp, tư vấn và cùng người dùng thảo luận kịch bản phim ngắn, "
        "xây dựng góc quay, phân cảnh nghệ thuật tại Tầng 7 & 8 một cách gần gũi, chuyên nghiệp và chi tiết.\n\n"
        f"Dự án: {project_title}\nYêu cầu từ người dùng: {user_message}"
    )
    
    reply_text, err_msg = call_gemini_direct(prompt)
    if not reply_text:
        reply_text = f"⚠️ {err_msg}"
        
    return JSONResponse({"reply": reply_text, "project": project_title})
@app.get("/", response_class=HTMLResponse)
async def home(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cine AI Studio Pro 3.0 - Production Suite</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-4">
        <div class="max-w-4xl mx-auto space-y-4">
            <div class="flex justify-between items-center bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-lg">
                <div>
                    <h1 class="text-xl font-bold text-amber-400">🎬 Cine AI Studio Pro 3.0</h1>
                    <p class="text-xs text-slate-400">Hệ thống sản xuất Kịch bản & Đạo diễn ảo đa tầng</p>
                </div>
                <div class="flex items-center space-x-3">
                    <span class="text-sm text-slate-300 font-medium">👤 Chị Cún</span>
                    <a href="/logout" class="bg-rose-600 hover:bg-rose-700 px-3 py-1.5 rounded-lg text-sm font-medium transition shadow">Đăng xuất</a>
                </div>
            </div>


            <div class="flex flex-wrap gap-2">
                <a href="/" class="bg-amber-500 text-slate-950 px-4 py-2 rounded-lg font-semibold text-sm shadow">⚡ Phòng Chat Studio</a>
                <a href="/library" class="bg-slate-800 text-slate-300 hover:bg-slate-700 px-4 py-2 rounded-lg font-semibold text-sm transition">📁 Thư Viện Nhớp & Quản Lý Dự Án</a>
            </div>


            <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 space-y-4 shadow-xl">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Tiêu đề dự án / Phân cảnh:</label>
                    <input type="text" id="project-title" placeholder="Nhập tiêu đề dự án hoặc tên phân cảnh nghệ thuật..." class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:border-amber-500 transition">
                </div>
                
                <div class="flex justify-between items-center">
                    <span class="text-xs font-semibold uppercase tracking-wider text-amber-400">💬 Phòng Trò Chuyện Trực Tiếp Với Đạo Diễn Âo (Tầng 7 & 8)</span>
                    <span class="text-xs text-slate-500">Cloud DB: Supabase Synced</span>
                </div>


                <div id="chat-box" class="bg-slate-950 h-96 rounded-lg p-4 overflow-y-auto border border-slate-800 space-y-3 text-sm">
                    <div class="bg-blue-950/60 border border-blue-800/50 p-3.5 rounded-xl text-blue-200 shadow-sm">
                        🎬 Chào anh! Em là Đạo diễn ảo đây. Chúng ta hãy cùng trò chuyện, bàn về ý tưởng, thiết kế soundstage hoặc gọt giũa kịch bản trực tiếp tại Tầng 7 & 8 nhé. Anh muốn bắt đầu câu chuyện thế nào ạ?
                    </div>
                </div>


                <div class="flex gap-2">
                    <input type="text" id="user-input" placeholder="Nhập ý tưởng, trao đổi hoặc yêu cầu đạo diễn gọt giũa kịch bản..." class="flex-1 bg-slate-950 border border-slate-700 rounded-lg p-3.5 text-sm focus:outline-none focus:border-amber-500 transition" onkeypress="if(event.key==='Enter') sendMessage()">
                    <button onclick="sendMessage()" class="bg-indigo-600 hover:bg-indigo-700 px-6 py-3.5 rounded-lg font-semibold text-sm transition shadow">Gửi</button>
                </div>


                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                    <button onclick="sendMessage()" class="bg-purple-600 hover:bg-purple-700 py-3 rounded-lg font-semibold text-sm transition text-center shadow">💬 Gửi Trao Đổi (Real-time Chat)</button>
                    <button onclick="saveLibrary()" class="bg-emerald-600 hover:bg-emerald-700 py-3 rounded-lg font-semibold text-sm transition text-center shadow">💾 Lưu Dự Án Vào Thư Viện Supabase</button>
                </div>
            </div>
        </div>


        <script>
            async function sendMessage() {
                const input = document.getElementById('user-input');
                const chatBox = document.getElementById('chat-box');
                const titleInput = document.getElementById('project-title');
                const text = input.value.trim();
                if(!text) return;


                chatBox.innerHTML += `<div class="text-right"><span class="bg-slate-800 p-3.5 rounded-xl inline-block text-slate-100 max-w-[85%] text-left shadow-sm">${text}</span></div>`;
                input.value = '';
                chatBox.scrollTop = chatBox.scrollHeight;


                try {
                    const res = await fetch('/api/cineai/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: text, title: titleInput.value})
                    });
                    const data = await res.json();
                    chatBox.innerHTML += `<div class="bg-blue-950/60 border border-blue-800/50 p-3.5 rounded-xl text-blue-200 max-w-[85%] shadow-sm">${data.reply}</div>`;
                    chatBox.scrollTop = chatBox.scrollHeight;
                } catch(e) {
                    chatBox.innerHTML += `<div class="bg-rose-950/60 border border-rose-800/50 p-3.5 rounded-xl text-rose-200 shadow-sm">⚠️ Lỗi kết nối máy chủ!</div>`;
                }
            }


            async function saveLibrary() {
                const title = document.getElementById('project-title').value || "Dự án không tên";
                const chatContent = document.getElementById('chat-box').innerHTML;
                try {
                    const res = await fetch('/api/cineai/save', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({title: title, content: chatContent})
                    });
                    const data = await res.json();
                    alert(data.message || "Đã lưu dự án vào Supabase thành công!");
                } catch(e) {
                    alert("⚠️ Lỗi lưu dự án vào cơ sở dữ liệu!");
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
@app.post("/api/cineai/save")
async def save_project_api(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Chưa đăng nhập!"}, status_code=401)
    
    data = await request.json()
    title = data.get("title", "Dự án mới")
    content = data.get("content", "")
    
    if username not in USERS_DB:
        USERS_DB[username] = {"projects": []}
    if "projects" not in USERS_DB[username]:
        USERS_DB[username]["projects"] = []
        
    USERS_DB[username]["projects"].insert(0, {
        "title": title,
        "content": content,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_users()
    return JSONResponse({"message": f"💾 Đã lưu dự án '{title}' lên Supabase Cloud thành công!"})


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Đăng nhập - Cine AI Studio Pro 3.0</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4">
        <form method="POST" action="/login" class="bg-slate-900 p-8 rounded-2xl border border-slate-800 w-full max-w-md space-y-5 shadow-2xl">
            <div class="text-center space-y-1">
                <h2 class="text-2xl font-bold text-amber-400">🔐 Cine AI Studio Pro</h2>
                <p class="text-xs text-slate-400">Đăng nhập không gian sáng tạo độc lập</p>
            </div>
            <div>
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">Tên đăng nhập:</label>
                <input type="text" name="username" required class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3.5 text-sm focus:outline-none focus:border-amber-500 transition">
            </div>
            <div>
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">Mật khẩu:</label>
                <input type="password" name="password" required class="w-full bg-slate-950 border border-slate-700 rounded-lg p-3.5 text-sm focus:outline-none focus:border-amber-500 transition">
            </div>
            <button type="submit" class="w-full bg-amber-500 text-slate-950 font-bold py-3.5 rounded-lg hover:bg-amber-400 transition shadow-lg">Đăng Nhập Hệ Thống</button>
        </form>
    </body>
    </html>
    """)


@app.post("/login")
async def login_post(username: str = Form(...), password: str = Form(...)):
    user_info = USERS_DB.get(username)
    # Tài khoản mặc định admin/admin123 hoặc kiểm tra trong DB
    if (username == "admin" and password == "admin123") or (user_info and user_info.get("password_hash") == hashlib.sha256(password.encode()).hexdigest()):
        session_id = secrets.token_hex(16)
        ACTIVE_SESSIONS[session_id] = username
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id)
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/logout")
async def logout(session_id: str = Cookie(None)):
    if session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_id")
    return response


@app.get("/library", response_class=HTMLResponse)
async def library_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    user_projects = USERS_DB.get(username, {}).get("projects", [])
    projects_html = ""
    if not user_projects:
        projects_html = '<p class="text-sm text-slate-500">Chưa có dự án nào được lưu trữ trong cơ sở dữ liệu Supabase.</p>'
    else:
        for p in user_projects:
            projects_html += f"""
            <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                <div class="flex justify-between items-center">
                    <h3 class="font-bold text-amber-400 text-sm">📌 {p.get('title')}</h3>
                    <span class="text-xs text-slate-500">{p.get('time')}</span>
                </div>
                <div class="text-xs text-slate-300 bg-slate-900 p-3 rounded-lg max-h-32 overflow-y-auto">{p.get('content')}</div>
            </div>
            """


    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thư Viện Nhớp - Cine AI Studio Pro</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-4">
        <div class="max-w-4xl mx-auto space-y-4">
            <div class="flex justify-between items-center bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-lg">
                <div>
                    <h1 class="text-xl font-bold text-amber-400">📁 Thư Viện Nhớp & Dự Án Lưu Trữ</h1>
                    <p class="text-xs text-slate-400">Kho lưu trữ kịch bản đồng bộ từ Supabase Cloud</p>
                </div>
                <a href="/" class="bg-amber-500 text-slate-950 px-4 py-2 rounded-lg font-semibold text-sm shadow">⚡ Quay lại Studio</a>
            </div>
            <div class="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4 shadow-xl">
                <h2 class="text-sm font-semibold uppercase tracking-wider text-amber-400">Danh sách dự án đã lưu của {username}:</h2>
                <div class="space-y-3">
                    {projects_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)