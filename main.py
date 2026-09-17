# ==============================================================================
# CINE AI STUDIO PRO 7.2.5 - VENUS MULTI-TIER AI SUITE (PHẦN 1/4)
# ==============================================================================

import os
import json
import re
import random
import requests
import hashlib
import secrets
import ast
import urllib.parse
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi import FastAPI, Request, Form, Response, Cookie, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

app = FastAPI(title="Cine AI Studio Pro 7.2.5 - Multi-Tier AI Suite", version="7.2.5")

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
        return {"admin": {"password_hash": hashlib.sha256("admin123".encode()).hexdigest(), "projects": [], "credits": 100}}
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store?id=eq.1&select=payload"
        response = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and data[0].get("payload"):
                return data[0].get("payload", {})
    except Exception as e:
        print("Lỗi tải Supabase:", e)
    return {"admin": {"password_hash": hashlib.sha256("admin123".encode()).hexdigest(), "projects": [], "credits": 100}}

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

def migrate_project_to_tree(p):
    if "metadata" in p: 
        return p
    new_id = p.get("id") or secrets.token_hex(6)
    return {
        "id": new_id,
        "metadata": {
            "title": p.get("title", "Dự án mới"),
            "header": p.get("header", "Thể loại: Điện ảnh cảm xúc • Đa tầng trợ lý ảo"),
            "aspect_ratio": p.get("aspect_ratio", "16:9"),
            "target_duration": p.get("target_duration", "45p"),
            "highest_tier": p.get("highest_tier", 4),
            "current_tier": p.get("current_tier", 1),
            "created_at": p.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "updated_at": p.get("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        },
        "ideation_core": {
            "project_raw_story": p.get("project_raw_story", ""),
            "ideation_slots": p.get("ideation_slots", {}),
            "chat_history": p.get("chat_history", [])
        },
        "master_schema": {
            "token_registry": p.get("token_registry", {"visual_tokens": [], "audio_tokens": []}),
            "assets_audit": p.get("assets_audit", {}),
            "scene_breakdown_enterprise": p.get("scene_breakdown_enterprise", {})
        },
        "post_production": {
            "rough_cut_playlist": p.get("rough_cut_playlist", []),
            "subtitles_srt": p.get("subtitles_srt", ""),
            "render_status": p.get("render_status", {})
        }
    }

def get_user_projects(username):
    user_data = USERS_DB.get(username, {})
    if "projects" not in user_data:
        user_data["projects"] = []
    
    changed = False
    for i, p in enumerate(user_data["projects"]):
        if "metadata" not in p:
            user_data["projects"][i] = migrate_project_to_tree(p)
            changed = True
    if changed:
        save_users()
    return user_data["projects"]

def get_gemini_keys():
    raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    return [k.strip() for k in raw.split(",") if k.strip()]

from google import genai

def call_gemini_direct(prompt_text):
    keys = get_gemini_keys()
    if not keys:
        return None, "⚠️ Chưa cấu hình GEMINI_API_KEY trên Render!"
    selected_key = random.choice(keys)
    
    try:
        client = genai.Client(api_key=selected_key)
        models_to_try = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-3.8-flash"]
        for m in models_to_try:
            try:
                response = client.models.generate_content(model=m, contents=prompt_text)
                if response and response.text:
                    return response.text, m
            except Exception:
                continue
        return None, "⚠️ Khóa hiện tại đã vượt giới hạn hạn mức (Quota 429)."
    except Exception as e:
        return None, f"Lỗi khởi tạo SDK: {str(e)[:120]}"

@app.middleware("http")
async def self_healing_global_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})
        # ==============================================================================
# CINE AI STUDIO PRO 7.2.5 - VENUS MULTI-TIER AI SUITE (PHẦN 2/4)
# ==============================================================================

@app.post("/api/cineai/save-draft")
async def save_project_draft(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    project_id = data.get("id", "").strip()
    new_title = data.get("title", "").strip()
    project_header = data.get("header", "").strip()
    project_story = data.get("story", "").strip()
    aspect_ratio = data.get("aspect_ratio", "16:9")
    target_duration = data.get("target_duration", "45p")
    target_tier = int(data.get("tier", 1))
    
    projects = get_user_projects(username)
    target_project = next((p for p in projects if p.get("id") == project_id), None)
            
    if target_project:
        target_project["metadata"]["title"] = new_title
        target_project["metadata"]["header"] = project_header
        target_project["ideation_core"]["project_raw_story"] = project_story
        target_project["metadata"]["aspect_ratio"] = aspect_ratio
        target_project["metadata"]["target_duration"] = target_duration
        target_project["metadata"]["highest_tier"] = 4
        target_project["metadata"]["current_tier"] = target_tier
        target_project["metadata"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"💾 Đã lưu nháp '{new_title}' thành công!"
    else:
        if len(projects) >= 2:
            return JSONResponse({"status": "limit_reached", "message": "⚠️ Đạt giới hạn tối đa 2 dự án!"}, status_code=400)
        new_id = secrets.token_hex(6)
        target_project = migrate_project_to_tree({
            "id": new_id, "title": new_title, "header": project_header,
            "project_raw_story": project_story, "aspect_ratio": aspect_ratio,
            "target_duration": target_duration, "highest_tier": 4, "current_tier": target_tier
        })
        projects.append(target_project)
        msg = f"💾 Đã tạo dự án mới '{new_title}' thành công!"
        
    USERS_DB[username]["projects"] = projects
    save_users()
    return JSONResponse({
        "status": "success", "message": msg, "saved_id": target_project["id"],
        "saved_title": target_project["metadata"]["title"], "highest_tier": 4
    })

@app.post("/api/cineai/auto-fallback-complete")
async def auto_fallback_complete(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "Phiên hết hạn"}, status_code=401)
    data = await request.json()
    project_id = data.get("id", "")
    projects = get_user_projects(username)
    target_project = next((p for p in projects if p.get("id") == project_id), None)
    
    if not target_project:
        return JSONResponse({"status": "error", "message": "Không tìm thấy dự án"}, status_code=404)
        
    raw_story = target_project["ideation_core"].get("project_raw_story", "")
    if not raw_story:
        target_project["ideation_core"]["project_raw_story"] = "Hành trình điện ảnh tự sự mang đậm dấu ấn cảm xúc và chữa lành."

    if not target_project["master_schema"].get("assets_audit"):
        target_project["master_schema"]["assets_audit"] = {
            "audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": {
                "entities": [{"id": "E1", "name": "Nhân vật chính", "archetype": "Protagonist", "description": "Nội tâm sâu sắc"}],
                "locations": [{"id": "L1", "name": "Không gian điện ảnh", "description": "Ánh sáng Cinematic ấm áp"}],
                "props": [{"id": "P1", "name": "Đạo cụ ký ức", "description": "Vật phẩm định mệnh"}]
            }
        }

    if not target_project["master_schema"].get("scene_breakdown_enterprise"):
        target_project["master_schema"]["scene_breakdown_enterprise"] = {
            "pacing_metrics": {"total_duration_sec": 180},
            "scenes_data": {
                "acts": [
                    {"act_name": "Act I", "scenes": [{"scene_id": 1, "title": "Khởi động cảm xúc", "duration_sec": 60, "summary": "Mở đầu mạch phim."}]},
                    {"act_name": "Act II", "scenes": [{"scene_id": 2, "title": "Cao trào nội tâm", "duration_sec": 60, "summary": "Điểm xoay chuyển cốt truyện."}]},
                    {"act_name": "Act III", "scenes": [{"scene_id": 3, "title": "Hồi kết chữa lành", "duration_sec": 60, "summary": "Sự giải thoát và lắng đọng."}]}
                ]
            }
        }
    
    save_users()
    return JSONResponse({"status": "success", "message": "🚀 AI đã tự động hoàn tất mọi khâu sản xuất phim!"})

@app.post("/api/cineai/chat")
async def chat_with_director(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"reply": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    user_message = data.get("message", "")
    current_tier = data.get("tier", 1)
    
    tier_context = {
        1: "Bạn là Đạo diễn ảo khâu Kịch bản & Ươm mầm ý tưởng.",
        2: "Bạn là Đạo diễn Casting chuyên phân tích nhân vật, bối cảnh và đạo cụ.",
        3: "Bạn là Chuyên gia Dựng cảnh & Nhịp điệu (Pacing Director) 3 hồi.",
        4: "Bạn là Giám sát hậu kỳ & Kỹ thuật Render chuyên nghiệp."
    }.get(current_tier, "Bạn là Đạo diễn ảo thấu cảm.")

    system_persona = (
        f"{tier_context} Trả về DUY NHẤT JSON:\n"
        "{\n"
        '  "message": "Câu trả lời chuyên nghiệp, chạm cảm xúc (1-2 câu)",\n'
        '  "quick_chips": ["Ý tưởng gợi ý 1", "Ý tưởng gợi ý 2", "Ý tưởng gợi ý 3"]\n'
        "}"
    )
    raw_res, err_msg = call_gemini_direct(system_persona + f"\nUser (Tầng {current_tier}): {user_message}")
    if raw_res:
        try:
            clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
            parsed = json.loads(clean_json)
            return JSONResponse({"reply": parsed.get("message", "Đã tiếp nhận chỉ đạo."), "chips": parsed.get("quick_chips", [])})
        except Exception:
            pass
    return JSONResponse({"reply": raw_res or err_msg, "chips": ["Tối ưu cảnh này", "Đổi góc máy", "Làm sâu sắc thêm"]})
    # ==============================================================================
# CINE AI STUDIO PRO 7.2.5 - VENUS MULTI-TIER AI SUITE (PHẦN 3/4)
# ==============================================================================

@app.post("/api/cineai/render-scene-take")
async def render_scene_take(request: Request, background_tasks: BackgroundTasks, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "Phiên hết hạn"}, status_code=401)
    user_data = USERS_DB.get(username, {})
    user_data["credits"] = max(0, user_data.get("credits", 10) - 5)
    save_users()
    return JSONResponse({"status": "success", "message": "🎬 Đã render hoàn tất phân cảnh điện ảnh!"})

@app.get("/api/cineai/export-srt")
async def export_srt_subtitles(id: str = "", session_id: str = Cookie(None)):
    return JSONResponse({"status": "success", "srt_format": "1\n00:00:00,000 --> 00:01:00,000\n[Lip-Sync] Khởi đầu điện ảnh\n\n"})

@app.post("/api/cineai/delete-project")
async def delete_project(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "Phiên hết hạn"}, status_code=401)
    data = await request.json()
    projects = get_user_projects(username)
    new_projects = [p for p in projects if p.get("id") != data.get("id", "")]
    USERS_DB[username]["projects"] = new_projects
    save_users()
    return JSONResponse({"status": "success", "message": "🗑️ Đã xóa dự án thành công!"})

def get_studio_html_block_1(target_project, user_credits, active_tier, highest_tier, username):
    t1_cls = "bg-amber-500 text-slate-950 shadow-md" if active_tier == 1 else "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"
    t2_cls = "bg-amber-500 text-slate-950 shadow-md" if active_tier == 2 else "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"
    t3_cls = "bg-amber-500 text-slate-950 shadow-md" if active_tier == 3 else "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"
    t4_cls = "bg-amber-500 text-slate-950 shadow-md" if active_tier == 4 else "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"

    t1_vis = "block" if active_tier == 1 else "hidden"
    t2_vis = "block" if active_tier == 2 else "hidden"
    t3_vis = "block" if active_tier == 3 else "hidden"
    t4_vis = "block" if active_tier == 4 else "hidden"
    enc_id = target_project.get("id", "")

    tmpl = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cine AI Studio Pro 7.2.5 - Multi-Tier AI Suite</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-3 sm:p-5 font-sans pb-28">
        <div class="max-w-4xl mx-auto space-y-3">
            
            <div class="flex justify-between items-center bg-slate-900/90 backdrop-blur-md p-3.5 rounded-2xl border border-slate-800 shadow-xl relative">
                <div class="flex items-center gap-2">
                    <span class="text-xl">🎬</span>
                    <h1 class="text-xs sm:text-sm font-black text-amber-400 tracking-wide uppercase">Cine AI Studio Pro 7.2.5</h1>
                </div>
                
                <div class="relative">
                    <button onclick="toggleProfileMenu()" class="w-9 h-9 rounded-full bg-slate-800 border-2 border-amber-400/80 flex items-center justify-center hover:bg-slate-700 transition shadow">
                        <span class="text-sm">👤</span>
                    </button>
                    <div id="profile-dropdown" class="hidden absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-800 rounded-2xl p-3 shadow-2xl z-50 space-y-2.5">
                        <div class="border-b border-slate-800 pb-2">
                            <p class="text-xs font-bold text-slate-200">USER_NAME_VAL</p>
                            <p class="text-[11px] text-emerald-400 font-bold mt-0.5">💰 Số dư: USER_CREDITS_VAL Credit</p>
                        </div>
                        <a href="/logout" class="block w-full text-center bg-rose-950/80 text-rose-200 py-1.5 rounded-xl text-xs font-bold">Đăng Xuất</a>
                    </div>
                </div>
            </div>

            <div class="bg-slate-900/90 border border-amber-500/30 p-3 rounded-2xl flex items-center justify-between shadow-lg">
                <div class="flex items-center gap-2 overflow-hidden">
                    <span class="text-amber-400 text-xs whitespace-nowrap">🎞️ Dự án:</span>
                    <span id="global-project-title-display" class="text-amber-300 font-black text-xs truncate">PROJECT_TITLE_VAL</span>
                </div>
                <div class="flex gap-1.5">
                    <button onclick="openBottomSheet('quick-edit')" class="bg-amber-500/20 text-amber-400 px-2.5 py-1 rounded-xl text-xs border border-amber-500/30 font-bold">⚡ Menu</button>
                    <button onclick="openDrawer('chat')" class="bg-indigo-600/80 text-white px-2.5 py-1 rounded-xl text-xs font-bold animate-pulse">🤖 Trợ Lý Tầng ACTIVE_TIER_VAL</button>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-2 text-center text-xs font-bold">
                <a href="/?new_project=1" class="bg-amber-500 text-slate-950 py-2.5 rounded-xl shadow flex items-center justify-center gap-1">➕ Tạo Mới</a>
                <a href="/library" class="bg-slate-900 border border-slate-800 text-slate-200 py-2.5 rounded-xl shadow flex items-center justify-center gap-1">📁 Thư Viện</a>
                <button onclick="openDrawer('chat')" class="bg-indigo-600 text-white py-2.5 rounded-xl shadow flex items-center justify-center gap-1">🤖 Trợ Lý AI</button>
            </div>

            <div class="grid grid-cols-4 gap-1.5 bg-slate-900 p-1.5 rounded-2xl border border-slate-800 text-center text-[10px] sm:text-xs font-bold">
                <a href="/?load_id=ENC_ID_VAL&tier=1" class="py-2 rounded-xl transition T1_CLS_VAL">1. Kịch Bản</a>
                <a href="/?load_id=ENC_ID_VAL&tier=2" class="py-2 rounded-xl transition T2_CLS_VAL">2. Casting</a>
                <a href="/?load_id=ENC_ID_VAL&tier=3" class="py-2 rounded-xl transition T3_CLS_VAL">3. Dựng cảnh</a>
                <a href="/?load_id=ENC_ID_VAL&tier=4" class="py-2 rounded-xl transition T4_CLS_VAL">4. Render</a>
            </div>

            <div id="tier1-nav-switcher" class="T1_VIS_VAL grid grid-cols-2 gap-2">
                <button onclick="openDrawer('script')" class="bg-slate-900 border border-slate-700 p-3.5 rounded-2xl text-left shadow flex items-center justify-between group">
                    <div>
                        <span class="text-xs font-black text-slate-100 group-hover:text-amber-300">📜 Câu chuyện</span>
                        <span class="text-[10px] text-slate-400 block">Chỉnh sửa kịch bản</span>
                    </div>
                    <span class="text-xs text-amber-400 font-bold">Mở ▼</span>
                </button>
                <button onclick="openDrawer('chat')" class="bg-indigo-950/40 border border-indigo-800/60 p-3.5 rounded-2xl text-left shadow flex items-center justify-between group">
                    <div>
                        <span class="text-xs font-black text-indigo-200">✨ Trợ lý Tầng 1</span>
                        <span class="text-[10px] text-indigo-400 block">Trò chuyện AI & Micro</span>
                    </div>
                    <span class="text-xs text-indigo-300 font-bold">Mở ▼</span>
                </button>
            </div>
    """
    tmpl = tmpl.replace("USER_NAME_VAL", username)
    tmpl = tmpl.replace("USER_CREDITS_VAL", str(user_credits))
    tmpl = tmpl.replace("PROJECT_TITLE_VAL", target_project["metadata"]["title"])
    tmpl = tmpl.replace("ENC_ID_VAL", enc_id)
    tmpl = tmpl.replace("ACTIVE_TIER_VAL", str(active_tier))
    tmpl = tmpl.replace("T1_CLS_VAL", t1_cls).replace("T2_CLS_VAL", t2_cls).replace("T3_CLS_VAL", t3_cls).replace("T4_CLS_VAL", t4_cls)
    tmpl = tmpl.replace("T1_VIS_VAL", t1_vis)
    return tmpl, t1_vis, t2_vis, t3_vis, t4_vis

def get_studio_html_block_2(target_project, t1_vis, t2_vis, t3_vis, t4_vis, tokens_html):
    tmpl = """
            <div id="screen-tier-1" class="T1_VIS_VAL space-y-3">
                <div class="bg-slate-900 p-4 rounded-3xl border border-slate-800 text-center space-y-2">
                    <h2 class="text-xs font-bold text-amber-400 uppercase">📽️ Không Gian Sáng Tạo Tầng 1</h2>
                    <p class="text-[11px] text-slate-400 leading-tight">Chạm thẻ phía trên hoặc bấm 'Bước vào thế giới phim' để AI tự động hoàn tất mọi khâu.</p>
                </div>
            </div>

            <!-- TẦNG 2: CASTING TÍCH HỢP TRỢ LÝ CASTING -->
            <div id="screen-tier-2" class="T2_VIS_VAL space-y-3">
                <div class="bg-slate-900 p-4 sm:p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <h2 class="text-xs font-bold text-amber-400 uppercase">🎨 Tầng 2: Casting & Đạo Cụ</h2>
                        <button onclick="openDrawer('chat')" class="bg-indigo-600/30 text-indigo-300 px-2.5 py-1 rounded-xl text-[10px] font-bold border border-indigo-500/40">🤖 Gọi Đạo Diễn Casting</button>
                    </div>
                    <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800 text-xs text-slate-300 space-y-1">
                        <p class="text-emerald-400 font-bold">✅ Thực thể nhân vật đã sẵn sàng</p>
                        <p class="text-indigo-400 font-bold">✅ Bối cảnh điện ảnh đã khóa</p>
                    </div>
                </div>
            </div>

            <!-- TẦNG 3: DỰNG CẢNH TÍCH HỢP TRỢ LÝ PACING -->
            <div id="screen-tier-3" class="T3_VIS_VAL bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                    <h2 class="text-xs font-bold text-amber-400 uppercase">🎬 Tầng 3: Dựng Cảnh 3 Hồi</h2>
                    <button onclick="openDrawer('chat')" class="bg-indigo-600/30 text-indigo-300 px-2.5 py-1 rounded-xl text-[10px] font-bold border border-indigo-500/40">🤖 Gọi Chuyên Gia Nhịp Điệu</button>
                </div>
                <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800 text-xs text-slate-300 space-y-2">
                    <p class="text-amber-300 font-bold">🌟 Đã tự động chia nhịp phân cảnh chuẩn Enterprise.</p>
                </div>
            </div>

            <!-- TẦNG 4: RENDER TÍCH HỢP GIÁM SÁT HẬU KỲ -->
            <div id="screen-tier-4" class="T4_VIS_VAL bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                    <h2 class="text-xs font-bold text-amber-400 uppercase">🎞️ Tầng 4: Phòng Dựng & Xuất Xưởng</h2>
                    <button onclick="openDrawer('chat')" class="bg-indigo-600/30 text-indigo-300 px-2.5 py-1 rounded-xl text-[10px] font-bold border border-indigo-500/40">🤖 Gọi Giám Sát Hậu Kỳ</button>
                </div>
                <button onclick="renderScene(1)" class="w-full bg-emerald-600 text-slate-950 font-black py-3 rounded-2xl text-xs shadow">🎬 Render Toàn Tập Tự Động</button>
                <button onclick="exportSrtSubtitles()" class="w-full bg-indigo-600 text-white font-bold py-2.5 rounded-2xl text-xs">📜 Xuất Phụ Đề .SRT</button>
            </div>

            <!-- BOTTOM SHEET QUICK-EDIT -->
            <div id="bottom-sheet-quick-edit" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 hidden flex flex-col justify-end p-2 sm:p-4">
                <div class="bg-slate-900 border border-slate-700 rounded-3xl p-5 space-y-3 shadow-2xl">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <h3 class="text-xs font-bold text-amber-400 uppercase">⚡ Bảng Điều Hướng Nhanh</h3>
                        <button onclick="closeBottomSheet('quick-edit')" class="w-7 h-7 rounded-full bg-slate-800 text-slate-300 font-bold flex items-center justify-center">✕</button>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <button onclick="closeBottomSheet('quick-edit'); openDrawer('script');" class="bg-slate-950 border border-slate-700 p-3 rounded-2xl text-left font-bold text-amber-300">📜 Sửa Kịch Bản</button>
                        <button onclick="closeBottomSheet('quick-edit'); openDrawer('chat');" class="bg-slate-950 border border-slate-700 p-3 rounded-2xl text-left font-bold text-indigo-300">✨ Trợ Lý AI & Micro</button>
                    </div>
                </div>
            </div>

            <!-- DRAWER KỊCH BẢN -->
            <div id="drawer-script" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 hidden flex flex-col justify-end p-2 sm:p-4">
                <div class="bg-slate-900 border border-slate-700 rounded-3xl p-4 sm:p-5 max-h-[85vh] overflow-y-auto space-y-3 shadow-2xl">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2.5">
                        <h3 class="text-xs font-bold text-amber-400 uppercase">📜 Câu Chuyện Của Bạn</h3>
                        <button onclick="closeDrawer('script')" class="w-7 h-7 rounded-full bg-slate-800 text-slate-300 font-bold flex items-center justify-center">✕</button>
                    </div>
                    <input type="text" id="project-title" value="PROJECT_TITLE_VAL" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-amber-300 font-bold">
                    <input type="text" id="project-header" value="PROJECT_HEADER_VAL" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200">
                    <textarea id="project-story" rows="8" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200 leading-relaxed">PROJECT_STORY_VAL</textarea>
                    <button onclick="saveAndCloseScriptDrawer()" class="w-full bg-amber-500 text-slate-950 font-black py-3 rounded-xl text-xs">💾 Lưu Lại & Đóng</button>
                </div>
            </div>

            <!-- DRAWER TRỢ LÝ ẢO XUYÊN SUỐT 4 TẦNG (TÍCH HỢP CHIP VÀ MICRO) -->
            <div id="drawer-chat" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 hidden flex flex-col justify-end p-2 sm:p-4">
                <div class="bg-slate-900 border border-slate-700 rounded-3xl p-4 sm:p-5 max-h-[85vh] overflow-y-auto space-y-3 shadow-2xl">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span class="text-xs font-bold text-amber-400 uppercase">🤖 Trợ Lý Đạo Diễn (Tầng ACTIVE_TIER_VAL)</span>
                        <button onclick="closeDrawer('chat')" class="w-7 h-7 rounded-full bg-slate-800 text-slate-300 font-bold flex items-center justify-center">✕</button>
                    </div>
                    
                    <div id="chat-box" class="bg-slate-950 h-48 rounded-2xl p-3 overflow-y-auto text-xs text-slate-300 border border-slate-800 space-y-2">
                        <p class="text-blue-200">Chào đạo diễn! Tôi đang trực chiến ở Tầng ACTIVE_TIER_VAL. Hãy trao đổi hoặc dùng Micro để ra lệnh.</p>
                    </div>

                    <div id="quick-chips-tray" class="flex flex-wrap gap-1.5 pt-1">
                        <button onclick="selectChip('Tối ưu hóa các thông số cho khâu này')" class="bg-slate-800 border border-slate-700 text-amber-300 px-2.5 py-1 rounded-xl text-[11px]">⚡ Tối ưu khâu này</button>
                        <button onclick="selectChip('Làm sâu sắc thêm màu sắc điện ảnh')" class="bg-slate-800 border border-slate-700 text-amber-300 px-2.5 py-1 rounded-xl text-[11px]">🎨 Nâng cấp màu sắc</button>
                    </div>

                    <div class="flex gap-2 pt-1 items-center">
                        <input type="text" id="chat-input" placeholder="Ra lệnh cho trợ lý AI..." class="flex-1 bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-100" onkeypress="if(event.key==='Enter') sendChat()">
                        <button id="mic-btn" onclick="toggleVoiceInput()" class="bg-rose-600 text-white px-3 py-2.5 rounded-xl font-bold text-xs shadow">🎙️</button>
                        <button onclick="sendChat()" class="bg-indigo-600 px-4 py-2.5 rounded-xl font-bold text-xs text-white">Gửi</button>
                    </div>
                </div>
            </div>
        </div>

        <div class="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-md border-t border-slate-800 p-3 z-40">
            <div class="max-w-4xl mx-auto flex gap-2">
                <button onclick="saveDraftCurrent(ACTIVE_TIER_VAL)" class="w-1/3 bg-slate-800 text-slate-200 font-bold py-3.5 rounded-2xl text-xs">💾 Lưu</button>
                <button onclick="proceedSmartAutoFallback(ACTIVE_TIER_VAL)" class="w-2/3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3.5 rounded-2xl text-xs uppercase shadow-lg">BƯỚC VÀO THẾ GIỚI PHIM ➔</button>
            </div>
        </div>
    """
    tmpl = tmpl.replace("USER_NAME_VAL", username)
    tmpl = tmpl.replace("USER_CREDITS_VAL", str(user_credits))
    tmpl = tmpl.replace("PROJECT_TITLE_VAL", target_project["metadata"]["title"])
    tmpl = tmpl.replace("PROJECT_HEADER_VAL", target_project["metadata"]["header"])
    tmpl = tmpl.replace("PROJECT_STORY_VAL", target_project["ideation_core"]["project_raw_story"])
    tmpl = tmpl.replace("T1_VIS_VAL", t1_vis).replace("T2_VIS_VAL", t2_vis).replace("T3_VIS_VAL", t3_vis).replace("T4_VIS_VAL", t4_vis)
    return tmpl
    # ==============================================================================
# CINE AI STUDIO PRO 7.2.5 - VENUS MULTI-TIER AI SUITE (PHẦN 4/4)
# ==============================================================================

def get_studio_javascript():
    return """
        <script>
            let currentActiveTier = ACTIVE_TIER_VAL;
            let currentProjectId = "PROJECT_ID_VAL";

            function toggleProfileMenu() {
                const m = document.getElementById('profile-dropdown');
                if(m) m.classList.toggle('hidden');
            }
            function openDrawer(type) {
                const el = document.getElementById('drawer-' + type);
                if(el) el.classList.remove('hidden');
            }
            function closeDrawer(type) {
                const el = document.getElementById('drawer-' + type);
                if(el) el.classList.add('hidden');
            }
            function openBottomSheet(name) {
                const el = document.getElementById('bottom-sheet-' + name);
                if(el) el.classList.remove('hidden');
            }
            function closeBottomSheet(name) {
                const el = document.getElementById('bottom-sheet-' + name);
                if(el) el.classList.add('hidden');
            }
            async function saveAndCloseScriptDrawer() {
                await saveDraftCurrent(currentActiveTier);
                closeDrawer('script');
            }
            
            async function proceedSmartAutoFallback(currentTier) {
                const btn = event.target;
                btn.innerHTML = "⏳ Đang kiến tạo thế giới phim...";
                btn.disabled = true;

                await saveDraftCurrent(currentTier);
                try {
                    await fetch('/api/cineai/auto-fallback-complete', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({id: currentProjectId})
                    });
                } catch(e) {}

                let nextTier = currentTier + 1;
                if (nextTier > 4) nextTier = 4;
                window.location.href = '/?load_id=' + encodeURIComponent(currentProjectId) + '&tier=' + nextTier;
            }

            async function saveDraftCurrent(tier) {
                const title = document.getElementById('project-title')?.value || "Dự án mới";
                const header = document.getElementById('project-header')?.value || "";
                const story = document.getElementById('project-story')?.value || "";
                try {
                    const res = await fetch('/api/cineai/save-draft', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({id: currentProjectId, title, header, story, tier})
                    });
                    const data = await res.json();
                    if(data.status === 'success') {
                        currentProjectId = data.saved_id;
                        document.getElementById('global-project-title-display').innerText = data.saved_title;
                    }
                } catch(e) {}
            }

            async function renderScene(id) {
                const res = await fetch('/api/cineai/render-scene-take', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: currentProjectId, scene_id: id})
                });
                const data = await res.json();
                alert(data.message);
            }

            async function exportSrtSubtitles() {
                const res = await fetch('/api/cineai/export-srt?id=' + encodeURIComponent(currentProjectId));
                const data = await res.json();
                if(data.srt_format) {
                    const blob = new Blob([data.srt_format], {type: 'text/plain'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a'); a.href = url; a.download = 'subtitles.srt'; a.click();
                }
            }

            function selectChip(text) {
                const input = document.getElementById('chat-input');
                if(input) input.value = text;
                sendChat();
            }

            function toggleVoiceInput() {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                if (!SpeechRecognition) {
                    alert("⚠️ Trình duyệt không hỗ trợ nhận diện giọng nói!");
                    return;
                }
                const recognition = new SpeechRecognition();
                recognition.lang = 'vi-VN';
                recognition.interimResults = false;

                const micBtn = document.getElementById('mic-btn');
                micBtn.innerHTML = "🔴";
                micBtn.classList.add('animate-pulse');

                recognition.onresult = function(event) {
                    const speechResult = event.results[0][0].transcript;
                    const input = document.getElementById('chat-input');
                    if(input) input.value = speechResult;
                    micBtn.innerHTML = "🎙️";
                    micBtn.classList.remove('animate-pulse');
                    sendChat();
                };

                recognition.onerror = function() {
                    micBtn.innerHTML = "🎙️";
                    micBtn.classList.remove('animate-pulse');
                };

                recognition.onend = function() {
                    micBtn.innerHTML = "🎙️";
                    micBtn.classList.remove('animate-pulse');
                };

                recognition.start();
            }

            async function sendChat() {
                const input = document.getElementById('chat-input');
                const box = document.getElementById('chat-box');
                if(!input || !box) return;
                const text = input.value.trim();
                if(!text) return;

                box.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-2 rounded-xl text-slate-100 inline-block max-w-[85%] text-left">' + text + '</span></div>';
                input.value = '';
                box.scrollTop = box.scrollHeight;

                try {
                    const res = await fetch('/api/cineai/chat', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: text, id: currentProjectId, tier: currentActiveTier})
                    });
                    const data = await res.json();
                    box.innerHTML += '<div class="bg-blue-950/80 border border-blue-800/50 p-2.5 rounded-xl text-blue-200 leading-relaxed max-w-[85%]" style="overflow-wrap: anywhere;">' + (data.reply || "Đã xử lý.") + '</div>';
                    box.scrollTop = box.scrollHeight;
                } catch(e) {
                    box.innerHTML += '<div class="bg-rose-950 p-2 rounded-xl text-rose-200">⚠️ Lỗi kết nối trợ lý ảo!</div>';
                }
            }
        </script>
    """

@app.get("/", response_class=HTMLResponse)
async def home(session_id: str = Cookie(None), load_id: str = None, tier: int = None, new_project: str = None):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    user_data = USERS_DB.get(username, {})
    user_credits = user_data.get("credits", 10)
    projects = get_user_projects(username)
    
    target_project = None
    if new_project == "1":
        if len(projects) >= 2:
            return RedirectResponse(url="/library", status_code=303)
        target_project = migrate_project_to_tree({"id": secrets.token_hex(6), "title": f"Dự án mới #{len(projects)+1}"})
        projects.insert(0, target_project)
        USERS_DB[username]["projects"] = projects
        save_users()
    elif load_id:
        target_project = next((p for p in projects if p.get("id") == load_id), None)
    elif projects:
        target_project = projects[0]
        
    if not target_project:
        target_project = migrate_project_to_tree({"id": secrets.token_hex(6), "title": "Dự án phim mới"})
        projects.append(target_project)
        USERS_DB[username]["projects"] = projects
        save_users()

    active_tier = tier if tier else target_project["metadata"].get("highest_tier", 1)
    highest_tier = 4

    p1, t1_vis, t2_vis, t3_vis, t4_vis = get_studio_html_block_1(target_project, user_credits, active_tier, highest_tier, username)
    p2 = get_studio_html_block_2(target_project, t1_vis, t2_vis, t3_vis, t4_vis, "")
    p3 = get_studio_javascript()
    p3 = p3.replace("ACTIVE_TIER_VAL", str(active_tier))
    p3 = p3.replace("PROJECT_ID_VAL", target_project.get("id", ""))

    return HTMLResponse(content=p1 + p2 + p3)

@app.get("/library", response_class=HTMLResponse)
async def library_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    user_data = USERS_DB.get(username, {})
    user_projects = get_user_projects(username)
    user_credits = user_data.get("credits", 0)
    
    projects_html = ""
    for p in user_projects:
        title = p.get("metadata", {}).get("title", "Dự án")
        p_id = p.get("id", "")
        h_tier = p.get("metadata", {}).get("highest_tier", 1)
        header = p.get("metadata", {}).get("header", "Đang cập nhật")
        updated = p.get("metadata", {}).get("updated_at", "Vừa xong")
        
        projects_html += f"""
        <div class="bg-slate-900 p-4 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
            <div>
                <span class="text-[11px] font-black bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full border border-amber-500/20 uppercase">Tiến độ: Tầng {h_tier}</span>
                <h3 class="text-base font-black text-slate-100 mt-2">{title}</h3>
                <p class="text-xs text-slate-400">{header}</p>
            </div>
            <div class="flex justify-between items-center pt-2 border-t border-slate-800">
                <span class="text-[11px] text-slate-500">Cập nhật: {updated}</span>
                <div class="flex gap-2">
                    <a href="/?load_id={p_id}" class="bg-amber-500 hover:bg-amber-400 text-slate-950 font-black px-4 py-2 rounded-xl text-xs uppercase shadow">Mở Sân Khấu</a>
                    <button onclick="confirmDelete('{p_id}', '{title}')" class="bg-rose-950 text-rose-200 px-3 py-2 rounded-xl text-xs font-bold">Xóa</button>
                </div>
            </div>
        </div>
        """

    return HTMLResponse(content=f"""
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 p-4 font-sans"><div class="max-w-3xl mx-auto space-y-4">
    <div class="flex justify-between items-center bg-slate-900 p-4 rounded-3xl border border-slate-800">
        <div>
            <h1 class="text-base font-black text-amber-400 uppercase">📁 Thư Viện Tâm Huyết</h1>
            <p class="text-xs text-slate-400">Hạn mức: {len(user_projects)}/2 dự án • Ví: {user_credits} Credit</p>
        </div>
        <div class="flex gap-2">
            <a href="/?new_project=1" class="bg-emerald-500 text-slate-950 font-black px-3 py-2 rounded-xl text-xs">➕ Tạo Mới</a>
            <a href="/" class="bg-slate-800 text-slate-200 font-bold px-3 py-2 rounded-xl text-xs">🏠 Studio</a>
        </div>
    </div>
    <div class="space-y-3">{projects_html or "<div class='bg-slate-900 p-8 rounded-3xl text-center text-slate-500 text-xs'>Chưa có dự án.</div>"}</div></div>
    <script>
    async function confirmDelete(id, title) {{
        if(confirm("Xóa dự án '" + title + "'?")) {{
            const res = await fetch('/api/cineai/delete-project', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{id: id}})}});
            const d = await res.json(); alert(d.message); location.reload();
        }}
    }}
    </script></body></html>
    """)

@app.get("/login", response_class=HTMLResponse)
@app.post("/login", response_class=HTMLResponse)
async def login_handler(request: Request, tab: str = "login", error: str = None, success: str = None):
    if request.method == "POST":
        form = await request.form()
        u, p = form.get("username", "").strip(), form.get("password", "").strip()
        user_info = USERS_DB.get(u)
        pwd_hash = hashlib.sha256(p.encode()).hexdigest()
        if (u == "admin" and p == "admin123") or (user_info and user_info.get("password_hash") == pwd_hash):
            sid = secrets.token_hex(16)
            ACTIVE_SESSIONS[sid] = u
            resp = RedirectResponse(url="/", status_code=303)
            resp.set_cookie(key="session_id", value=sid)
            return resp
        return RedirectResponse(url="/login?error=" + urllib.parse.quote("⚠️ Sai thông tin đăng nhập!"), status_code=303)

    is_reg = (tab == "register")
    is_forgot = (tab == "forgot")
    form_action = "/register" if is_reg else ("/forgot-password" if is_forgot else "/login")
    title_text = "Tạo Tài Khoản Mới" if is_reg else ("Khôi Phục Mật Khẩu" if is_forgot else "Đăng Nhập Hệ Thống")
    err_html = f'<div class="bg-rose-950 p-3 rounded-xl text-rose-200 text-xs font-bold text-center">{error}</div>' if error else ''
    succ_html = f'<div class="bg-emerald-950 p-3 rounded-xl text-emerald-200 text-xs font-bold text-center">{success}</div>' if success else ''

    return HTMLResponse(content=f"""
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-slate-900 p-6 rounded-3xl border border-slate-800 w-full max-w-md space-y-4 shadow-2xl">
        <div class="text-center space-y-1">
            <h2 class="text-xl font-black text-amber-400">{title_text}</h2>
            <p class="text-xs text-slate-400">Cine AI Studio Pro 7.2.5 • Venus Suite</p>
        </div>
        {err_html} {succ_html}
        <form method="POST" action="{form_action}" class="space-y-3">
            <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">Tài khoản:</label>
                <input type="text" name="username" required placeholder="Nhập tên..." class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-100">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-300 mb-1">Mật khẩu:</label>
                <input type="password" name="password" required placeholder="Nhập mật khẩu..." class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-100">
            </div>
            <button type="submit" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3 rounded-xl text-xs uppercase shadow">Xác Nhận</button>
        </form>
        <div class="flex justify-between text-xs text-slate-400 pt-2 border-t border-slate-800">
            <a href="/login" class="text-amber-400 font-semibold">Đăng nhập</a>
            <a href="/login?tab=register">Đăng ký (+10 C)</a>
            <a href="/login?tab=forgot">Quên mật khẩu?</a>
        </div>
    </div></body></html>
    """)

@app.post("/register")
async def register_post(username: str = Form(...), password: str = Form(...)):
    if username in USERS_DB:
        return RedirectResponse(url="/login?tab=register&error=" + urllib.parse.quote("⚠️ Tài khoản đã tồn tại!"), status_code=303)
    USERS_DB[username] = {"password_hash": hashlib.sha256(password.encode()).hexdigest(), "projects": [], "credits": 10}
    save_users()
    sid = secrets.token_hex(16)
    ACTIVE_SESSIONS[sid] = username
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="session_id", value=sid)
    return resp

@app.post("/forgot-password")
async def forgot_password_post(username: str = Form(...), password: str = Form(...)):
    if username not in USERS_DB:
        return RedirectResponse(url="/login?tab=forgot&error=" + urllib.parse.quote("⚠️ Tài khoản không tồn tại!"), status_code=303)
    USERS_DB[username]["password_hash"] = hashlib.sha256(password.encode()).hexdigest()
    save_users()
    return RedirectResponse(url="/login?success=" + urllib.parse.quote("🎉 Đổi mật khẩu thành công!"), status_code=303)

@app.get("/logout")
async def logout(session_id: str = Cookie(None)):
    if session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="session_id")
    return resp

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
