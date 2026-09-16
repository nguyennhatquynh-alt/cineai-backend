# ==============================================================================
# CINE AI STUDIO PRO 7.2.5 - VENUS SUITE (PHẦN 1/2)
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

app = FastAPI(title="Cine AI Studio Pro 7.2.5 - Venus Production Suite", version="7.2.5")

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
            "header": p.get("header", "Thể loại: Điện ảnh cảm xúc • Tự do sáng tạo"),
            "aspect_ratio": p.get("aspect_ratio", "16:9"),
            "target_duration": p.get("target_duration", "45p"),
            "highest_tier": p.get("highest_tier", 1),
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
        target_project["metadata"]["highest_tier"] = max(target_project["metadata"].get("highest_tier", 1), target_tier)
        target_project["metadata"]["current_tier"] = target_tier
        target_project["metadata"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"💾 Đã cập nhật dự án '{new_title}' thành công!"
    else:
        new_id = secrets.token_hex(6)
        target_project = migrate_project_to_tree({
            "id": new_id, "title": new_title, "header": project_header,
            "project_raw_story": project_story, "aspect_ratio": aspect_ratio,
            "target_duration": target_duration, "highest_tier": target_tier, "current_tier": target_tier
        })
        projects.append(target_project)
        msg = f"💾 Đã tạo dự án mới '{new_title}' thành công!"
        
    USERS_DB[username]["projects"] = projects
    save_users()
    return JSONResponse({
        "status": "success", "message": msg, "saved_id": target_project["id"],
        "saved_title": target_project["metadata"]["title"], "highest_tier": target_project["metadata"]["highest_tier"]
    })

@app.post("/api/cineai/audit-script-assets")
async def audit_script_assets(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    project_id = data.get("id", "")
    projects = get_user_projects(username)
    target_project = next((p for p in projects if p.get("id") == project_id), None)
    if not target_project:
        return JSONResponse({"status": "error", "message": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    raw_story = target_project["ideation_core"].get("project_raw_story", "")
    if not raw_story:
        return JSONResponse({"status": "error", "message": "⚠️ Kịch bản còn trống!"}, status_code=400)
    
    system_prompt = (
        "Bạn là Tổng Đạo Diễn của Cine AI Studio Pro 7.2.5. Quét kịch bản theo Master Schema gồm:\n"
        "1. Entities (Nhân vật), Locations (Bối cảnh), Props (Đạo cụ), Audio Signatures (Âm thanh).\n"
        "2. Temporal State Matrix & Evolution Item Tokens.\n"
        "Trả về DUY NHẤT chuỗi JSON hợp lệ:\n"
        "{\n"
        '  "time_jumps_detected": [],\n'
        '  "visual_style_lock": {"color_grading": "", "lens_language": "", "emotional_archetype": ""},\n'
        '  "entities": [{"id": "E1", "name": "...", "archetype": "...", "temporal_states": [], "description": "..."}],\n'
        '  "locations": [{"id": "L1", "name": "...", "temporal_states": [], "description": "..."}],\n'
        '  "props": [{"id": "P1", "name": "...", "evolution_lineage": [], "description": "..."}],\n'
        '  "audio_signatures": [{"id": "A1", "name": "...", "audio_signature": "..."}]\n'
        "}"
    )
    raw_res, err_msg = call_gemini_direct(system_prompt + f"\n\nKịch bản:\n{raw_story}")
    if not raw_res:
        return JSONResponse({"status": "error", "message": err_msg}, status_code=500)
    
    try:
        clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
        parsed_audit = json.loads(clean_json)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
        
    target_project["master_schema"]["assets_audit"] = {"audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data": parsed_audit}
    save_users()
    return JSONResponse({"status": "success", "audit_data": parsed_audit})

@app.post("/api/cineai/chat")
async def chat_with_director(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"reply": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    user_message = data.get("message", "")
    
    system_persona = (
        "Bạn là Đạo diễn ảo thấu cảm của Cine AI Studio Pro 7.2.5. Trả về DUY NHẤT JSON:\n"
        "{\n"
        '  "message": "Câu nói tâm tình chạm cảm xúc (1-2 câu)",\n'
        '  "extracted_slots": {"SLOT": "Giá trị"},\n'
        '  "quick_chips": ["Ý 1", "Ý 2", "Ý 3"],\n'
        '  "is_ready_for_script": true\n'
        "}"
    )
    raw_res, err_msg = call_gemini_direct(system_persona + f"\nUser: {user_message}")
    if raw_res:
        try:
            clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
            parsed = json.loads(clean_json)
            return JSONResponse({"reply": parsed.get("message", "Đã tiếp nhận."), "chips": parsed.get("quick_chips", []), "ready": True})
        except Exception:
            pass
    return JSONResponse({"reply": raw_res or err_msg, "chips": ["Tiếng mưa rơi", "Ký ức cũ"], "ready": True})

@app.post("/api/cineai/generate-script-from-slots")
async def generate_script_from_slots(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "Phiên hết hạn"}, status_code=401)
    data = await request.json()
    project_id = data.get("id", "")
    
    projects = get_user_projects(username)
    target_project = next((p for p in projects if p.get("id") == project_id), None)
    slots = target_project["ideation_core"].get("ideation_slots", {}) if target_project else {}
    
    prompt = f"Dựa vào các slots tâm lý sau, viết kịch bản 3 hồi hoàn chỉnh dạng JSON gồm title, header, story:\n{json.dumps(slots, ensure_ascii=False)}"
    raw_res, err = call_gemini_direct(prompt)
    if not raw_res:
        return JSONResponse({"status": "error", "message": err}, status_code=500)
    try:
        clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
        res_data = json.loads(clean_json)
    except Exception:
        res_data = {"title": "Dự án mới", "header": "Thể loại: Tâm lý", "story": raw_res}
        
    if target_project:
        target_project["metadata"]["title"] = res_data.get("title", "Dự án mới")
        target_project["metadata"]["header"] = res_data.get("header", "")
        target_project["ideation_core"]["project_raw_story"] = res_data.get("story", "")
        save_users()
    return JSONResponse({"status": "success", "data": res_data})
   # ==============================================================================
# CINE AI STUDIO PRO 7.2.5 - VENUS SUITE (PHẦN 2/2)
# ==============================================================================

@app.post("/api/cineai/breakdown-scenes-enterprise")
async def breakdown_scenes_enterprise(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "Phiên hết hạn"}, status_code=401)
    data = await request.json()
    project_id = data.get("id", "")
    projects = get_user_projects(username)
    target_project = next((p for p in projects if p.get("id") == project_id), None)
    raw_story = target_project["ideation_core"].get("project_raw_story", "") if target_project else ""
    
    pro_prompt = f"Phân tích kịch bản và chia nhịp 3 hồi (Act I, Act II, Act III) dạng JSON:\n{raw_story}"
    raw_res, err_msg = call_gemini_direct(pro_prompt)
    parsed_scenes = None
    if raw_res:
        try:
            clean_json_str = re.sub(r"^```json\s*|\s*
            
