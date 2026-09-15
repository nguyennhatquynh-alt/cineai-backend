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


app = FastAPI(title="Cine AI Studio Pro 6.7.6 - Enterprise Ultimate Suite", version="6.7.6")


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


def get_gemini_keys():
    raw = os.getenv("GEMINI_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def call_gemini_direct(prompt_text):
    keys = get_gemini_keys()
    if not keys:
        return None, "⚠️ Chưa cấu hình GEMINI_API_KEYS trên Render!"
    selected_key = random.choice(keys)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={selected_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"], "gemini-2.5-flash"
        else:
            return None, f"Lỗi Google API ({response.status_code})"
    except Exception as e:
        return None, "Lỗi kết nối: " + str(e)
def get_cloud_cache(cache_key: str):
    if not SUPABASE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_cache?key=eq.{cache_key}&select=value"
        res = requests.get(url, headers=get_supabase_headers(), timeout=5)
        if res.status_code == 200 and res.json():
            return res.json()[0].get("value")
    except Exception:
        pass
    return None


def set_cloud_cache(cache_key: str, value_data):
    if not SUPABASE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_cache"
        payload = {"key": cache_key, "value": value_data, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        headers = get_supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        requests.post(url, json=payload, headers=headers, timeout=5)
    except Exception:
        pass


@app.middleware("http")
async def self_healing_global_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        error_trace = str(exc)
        print(f"🔥 [SELF-HEALING CAUGHT EXCEPTION]: {error_trace}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "self_healing_intercepted",
                "message": "⚠️ Hệ thống đã tự động bắt lỗi Runtime, cô lập vùng đệm và ghi log an toàn.",
                "error_details": error_trace
            }
        )


def validate_python_code_ast(code_snippet: str) -> bool:
    try:
        ast.parse(code_snippet)
        return True
    except SyntaxError:
        return False
@app.post("/api/cineai/save-draft")
async def save_project_draft(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    old_title = data.get("old_title", "").strip()
    new_title = data.get("title", "").strip()
    project_header = data.get("header", "").strip()
    project_story = data.get("story", "").strip()
    aspect_ratio = data.get("aspect_ratio", "16:9")
    target_duration = data.get("target_duration", "45p")
    target_tier = int(data.get("tier", 1))
    
    if not new_title:
        return JSONResponse({"status": "error", "message": "⚠️ Tên dự án không được để trống!"}, status_code=400)
    
    user_data = USERS_DB.get(username, {})
    if "projects" not in user_data:
        user_data["projects"] = []
    
    projects = user_data["projects"]
    target_project = None
    
    for p in projects:
        if p.get("title") == old_title or p.get("title") == new_title:
            target_project = p
            break
            
    if target_project:
        target_project["title"] = new_title
        target_project["header"] = project_header
        target_project["project_raw_story"] = project_story
        target_project["aspect_ratio"] = aspect_ratio
        target_project["target_duration"] = target_duration
        current_highest = target_project.get("highest_tier", 1)
        target_project["highest_tier"] = max(current_highest, target_tier)
        target_project["current_tier"] = target_tier
        target_project["tierProgress"] = f"Tầng {target_project['highest_tier']} ({aspect_ratio} • {target_duration})"
        target_project["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"💾 Đã lưu thành công Tầng {target_tier} ({aspect_ratio} • {target_duration}) cho dự án '{new_title}'!"
    else:
        if len(projects) >= 2:
            return JSONResponse({"status": "limit_reached", "message": "⚠️ Đã đạt giới hạn tối đa 2 dự án thương mại cho mỗi user!"}, status_code=400)
        target_project = {
            "title": new_title,
            "header": project_header,
            "project_raw_story": project_story,
            "aspect_ratio": aspect_ratio,
            "target_duration": target_duration,
            "token_registry": {"visual_tokens": [], "audio_tokens": []},
            "assets_audit": {},
            "scene_matrix": {},
            "ideation_slots": {},
            "highest_tier": target_tier,
            "current_tier": target_tier,
            "tierProgress": f"Tầng {target_tier} (Mới tạo)",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        projects.append(target_project)
        msg = f"💾 Đã tạo và lưu nháp dự án mới '{new_title}' thành công!"
        
    save_users()
    return JSONResponse({
        "status": "success", 
        "message": msg, 
        "saved_title": new_title,
        "highest_tier": target_project.get("highest_tier", 1),
        "current_tier": target_tier
    })
@app.post("/api/cineai/audit-script-assets")
async def audit_script_assets(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    project_title = data.get("title", "Dự án mới")
    
    target_project = None
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                target_project = p
                break
                
    if not target_project:
        return JSONResponse({"status": "error", "message": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    raw_story = target_project.get("project_raw_story", "")
    if not raw_story:
        return JSONResponse({"status": "error", "message": "⚠️ Kịch bản còn trống. Vui lòng hoàn tất kịch bản tại Tầng 1!"}, status_code=400)
    
    cache_key = hashlib.md5(raw_story.encode()).hexdigest()
    cached_audit = get_cloud_cache(cache_key)
    if cached_audit:
        target_project["assets_audit"] = {"audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data": cached_audit}
        save_users()
        return JSONResponse({"status": "success", "message": "⚡ [Cache Hit] Đã nạp Master Schema từ Cloud Cache!", "audit_data": cached_audit})


    system_prompt = (
        "Bạn là Tổng Đạo Diễn và Giám Đốc Sản Xuất cấp cao của Cine AI Studio Pro 6.7.6 Enterprise.\n"
        "Nhiệm vụ: Quét sâu kịch bản theo Master Schema toàn diện gồm:\n"
        "1. 4 Tầng Lưới Lọc Cốt Lõi: Entities (Vạn vật hữu linh/nhân vật), Locations (Bối cảnh), Props (Đạo cụ định mệnh), Audio Signatures (Âm thanh 3D).\n"
        "2. Ma Trận Biến Thiên Thời Gian (Temporal State Matrix): Phát hiện bước nhảy thời gian ('time_jumps_detected') và phân rã các trạng thái ('temporal_states') theo độ tuổi hoặc sự lão hóa/biến đổi.\n"
        "3. Khóa Tiến Trình Trạng Thái Đồ Vật (Evolution Item Tokens): Thiết lập chuỗi 'evolution_lineage' cho các vật phẩm có sự nâng cấp, luyện khí, hư hỏng hoặc sửa chữa theo sự kiện.\n"
        "4. 3 Tầng Khóa Phong Cách Thị Giác ('visual_style_lock'): Định hình Color Grading, Lens Language và Emotional Archetype.\n\n"
        "Quy tắc phản hồi: Trả về DUY NHẤT một chuỗi JSON thuần hợp lệ (không kèm markdown):\n"
        "{\n"
        '  "time_jumps_detected": ["Mốc thời gian 1", "Mốc thời gian 2"],\n'
        '  "visual_style_lock": {\n'
        '    "color_grading": "Mô tả bảng màu và ánh sáng chủ đạo",\n'
        '    "lens_language": "Mô tả ngôn ngữ ống kính và chuyển động máy",\n'
        '    "emotional_archetype": "Mô tả thần thái và biểu cảm cốt lõi"\n'
        '  },\n'
        '  "entities": [{"id": "ASSET_ENT_01", "name": "...", "archetype": "...", "temporal_states": ["Trẻ", "Trưởng thành"], "description": "..."}],\n'
        '  "locations": [{"id": "ASSET_LOC_01", "name": "...", "temporal_states": ["Mới", "Hoang phế"], "description": "..."}],\n'
        '  "props": [{"id": "ASSET_PROP_01", "name": "...", "evolution_lineage": ["TOKEN_1", "TOKEN_2"], "description": "..."}],\n'
        '  "audio_signatures": [{"id": "ASSET_AUD_01", "name": "...", "audio_signature": "Mô tả âm trường 3D"}]\n'
        "}"
    )
    
    prompt = system_prompt + f"\n\nKịch bản phim [{project_title}]:\n{raw_story}"
    raw_res, err_msg = call_gemini_direct(prompt)
    
    if not raw_res:
        return JSONResponse({"status": "error", "message": f"Lỗi phân tích kịch bản: {err_msg}"}, status_code=500)
        
    try:
        clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
        parsed_audit = json.loads(clean_json)
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Không thể giải mã dữ liệu kiểm kê: {str(e)}"}, status_code=500)
        
    set_cloud_cache(cache_key, parsed_audit)


    existing_tokens = target_project.get("token_registry", {})
    target_project["assets_audit"] = {
        "audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": parsed_audit
    }
    save_users()
    
    return JSONResponse({
        "status": "success",
        "message": "✅ Đã kiểm kê và trích xuất Master Schema 6.7.6 thành công!",
        "audit_data": parsed_audit,
        "existing_tokens": existing_tokens
    })
@app.post("/api/cineai/generate-asset-concept-prompt")
async def generate_asset_concept_prompt(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
        
    data = await request.json()
    asset_name = data.get("asset_name", "")
    asset_desc = data.get("asset_description", "")
    user_tweak = data.get("user_tweak", "")
    
    prompt = (
        f"Bạn là Đạo diễn nghệ thuật (Art Director). Hãy viết 1 visual prompt ngắn gọn (100% tiếng Anh) "
        f"dùng để tạo ảnh concept mẫu đại diện cho đối tượng sau:\n"
        f"Đối tượng: {asset_name}\n"
        f"Mô tả: {asset_desc}\n"
        f"Ghi chú bổ sung: {user_tweak}\n"
        f"Yêu cầu: Phong cách điện ảnh cinematic masterpiece 4K, ánh sáng nghệ thuật, "
        f"nêu bật chi tiết nhận dạng độc bản không bị nhầm lẫn."
    )
    raw_res, err_msg = call_gemini_direct(prompt)
    return JSONResponse({"status": "success", "concept_prompt": raw_res or err_msg})


@app.post("/api/cineai/delete-project")
async def delete_project(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    project_title = data.get("title", "").strip()
    user_data = USERS_DB.get(username, {})
    projects = user_data.get("projects", [])
    
    new_projects = [p for p in projects if p.get("title") != project_title]
    if len(new_projects) == len(projects):
        return JSONResponse({"status": "error", "message": "⚠️ Không tìm thấy dự án cần xóa!"}, status_code=404)
        
    user_data["projects"] = new_projects
    save_users()
    return JSONResponse({"status": "success", "message": f"🗑️ Đã xóa vĩnh viễn dự án '{project_title}' thành công!"})


@app.post("/api/cineai/upload-asset-explicit")
async def upload_asset_explicit(
    file: UploadFile = File(...), 
    project_title: str = Form("Dự án mới"),
    session_id: str = Cookie(None)
):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    file_name = file.filename.lower()
    file_content = await file.read()
    if not (file_name.endswith(".txt") or file_name.endswith(".md")):
        return JSONResponse({"status": "error", "message": "⚠️ Vui lòng chọn đúng tệp kịch bản (.txt hoặc .md)!"}, status_code=400)
    
    try:
        extracted_text = file_content.decode("utf-8", errors="ignore")
    except Exception as e:
        extracted_text = f"Lỗi đọc tệp: {str(e)}"
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                p["project_raw_story"] = extracted_text
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
    
    return JSONResponse({
        "status": "success",
        "message": f"✅ Nạp và lưu thành công kịch bản từ tệp '{file.filename}'!",
        "extracted_content": extracted_text
    })


@app.post("/api/cineai/upload-visual-token")
async def upload_visual_token(
    file: UploadFile = File(...),
    token_category: str = Form("character"),
    token_name: str = Form(""),
    project_title: str = Form("Dự án mới"),
    session_id: str = Cookie(None)
):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    file_name = file.filename.lower()
    if not (file_name.endswith(".png") or file_name.endswith(".jpg") or file_name.endswith(".jpeg")):
        return JSONResponse({"status": "error", "message": "⚠️ Vui lòng chọn tệp hình ảnh (.png, .jpg)!"}, status_code=400)
    
    clean_cat = token_category.upper()
    token_id = f"TOKEN_{clean_cat}_{secrets.token_hex(3).upper()}"
    mock_url = f"https://cdn.cineai.studio/tokens/{username}/{project_title.replace(' ', '_')}/{file.filename}"
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                if "token_registry" not in p:
                    p["token_registry"] = {"visual_tokens": [], "audio_tokens": []}
                p["token_registry"]["visual_tokens"].append({
                    "token_id": token_id,
                    "category": token_category,
                    "name": token_name or file.filename,
                    "file_url": mock_url,
                    "file_name": file.filename,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                p["highest_tier"] = max(p.get("highest_tier", 1), 2)
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({
        "status": "success", 
        "message": f"🖼️ Khóa mẫu hình ảnh thành công với mã định danh [{token_id}]!", 
        "token_id": token_id, 
        "file_name": file.filename
    })
@app.post("/api/cineai/upload-audio-token")
async def upload_audio_token(
    file: UploadFile = File(...),
    token_category: str = Form("bgm"),
    token_name: str = Form(""),
    project_title: str = Form("Dự án mới"),
    session_id: str = Cookie(None)
):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    file_name = file.filename.lower()
    if not (file_name.endswith(".mp3") or file_name.endswith(".wav")):
        return JSONResponse({"status": "error", "message": "⚠️ Vui lòng chọn tệp âm thanh (.mp3, .wav)!"}, status_code=400)
    
    clean_cat = token_category.upper()
    token_id = f"TOKEN_AUDIO_{clean_cat}_{secrets.token_hex(3).upper()}"
    mock_url = f"https://cdn.cineai.studio/audio/{username}/{project_title.replace(' ', '_')}/{file.filename}"
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                if "token_registry" not in p:
                    p["token_registry"] = {"visual_tokens": [], "audio_tokens": []}
                p["token_registry"]["audio_tokens"].append({
                    "token_id": token_id,
                    "category": token_category,
                    "name": token_name or file.filename,
                    "file_url": mock_url,
                    "file_name": file.filename,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                p["highest_tier"] = max(p.get("highest_tier", 1), 2)
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({
        "status": "success", 
        "message": f"🎵 Khóa mẫu âm thanh thành công với mã định danh [{token_id}]!", 
        "token_id": token_id, 
        "file_name": file.filename
    })


@app.post("/api/cineai/chat")
async def chat_with_director(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"reply": "⚠️ Phiên đăng nhập hết hạn! Vui lòng tải lại trang."}, status_code=401)
    data = await request.json()
    user_message = data.get("message", "")
    project_title = data.get("title", "Dự án mới")
    tier = int(data.get("tier", 1))
    
    if not user_message:
        return JSONResponse({"reply": "Vui lòng nhập nội dung trao đổi với Đạo diễn ảo!"})
    
    if tier == 1:
        target_project = None
        if username in USERS_DB and "projects" in USERS_DB[username]:
            for p in USERS_DB[username]["projects"]:
                if p.get("title") == project_title:
                    target_project = p
                    break
        current_slots = target_project.get("ideation_slots", {}) if target_project else {}
        system_persona = (
            "Bạn là Đạo diễn ảo thấu cảm của Cine AI Studio Pro 6.7.6. "
            "Nhiệm vụ: Trò chuyện tâm tình hoặc trò chơi 'Nếu như...' để khai thác các biến số điện ảnh:\n"
            "1. ATMOSPHERE (Không gian, màu sắc, thời tiết, âm thanh)\n"
            "2. CORE_WOUND (Nỗi đau, vết thương lòng nhân vật)\n"
            "3. TRIGGER_PROP (Đạo cụ định mệnh, vật kích hoạt biến cố)\n"
            "4. DILEMMA (Điểm xoay giữa phim, lựa chọn đánh đổi sinh tử)\n"
            "5. CATHARSIS (Hồi kết mong muốn: Chữa lành, Day dứt, hay Bi tráng)\n\n"
            f"Các Slots hiện có: {json.dumps(current_slots, ensure_ascii=False)}\n"
            "Quy tắc phản hồi: Trả về DUY NHẤT một chuỗi JSON hợp lệ:\n"
            "{\n"
            '  "message": "Câu nói tâm tình ngắn gọn, chạm cảm xúc (1-2 câu)",\n'
            '  "extracted_slots": {"TÊN_SLOT": "Giá trị trích xuất"},\n'
            '  "quick_chips": ["Lựa chọn 1", "Lựa chọn 2", "Lựa chọn 3"],\n'
            '  "is_ready_for_script": true/false\n'
            "}"
        )
        prompt = system_persona + f"\nUser vừa chia sẻ: {user_message}"
        raw_res, err_msg = call_gemini_direct(prompt)
        parsed = None
        if raw_res:
            try:
                clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
                parsed = json.loads(clean_json)
            except Exception:
                parsed = None
        if parsed and isinstance(parsed, dict):
            new_slots = parsed.get("extracted_slots", {})
            if target_project and new_slots:
                if "ideation_slots" not in target_project:
                    target_project["ideation_slots"] = {}
                target_project["ideation_slots"].update(new_slots)
                save_users()
            return JSONResponse({
                "reply": parsed.get("message", "Tôi rất thấu hiểu cảm xúc bạn gửi gắm."),
                "chips": parsed.get("quick_chips", ["Một người sẽ biến mất", "Bí mật bị chôn giấu", "Tha thứ cho quá khứ"]),
                "ready": True
            })
        else:
            return JSONResponse({
                "reply": raw_res or f"⚠️ {err_msg}",
                "chips": ["Tiếng mưa rơi trên mái tôn", "Bức ảnh cũ phai màu", "Một lời xin lỗi muộn màng"],
                "ready": True
            })


    mode_instructions = {
        2: "Khóa mẫu Thực thể Vạn Vật Hữu Linh, bối cảnh, đạo cụ và âm thanh Audiophile 3D.",
        3: "Bóc tách kịch bản thành các Scene 30s-150s, ma trận 3 Hồi và Pacing Graph.",
        4: "Render toàn tập, Alternate Takes, Timeline Rough-Cut và xuất file phụ đề .SRT."
    }
    system_persona = (
        f"Bạn là Đạo diễn ảo của Cine AI Studio Pro 6.7.6. Trạng thái: {mode_instructions.get(tier, '')} "
        "Hãy phản hồi ngắn gọn, sắc sảo, chuyên nghiệp.\n"
        f"Dự án: {project_title}\n"
    )
    reply_text, err_msg = call_gemini_direct(system_persona + f"Ý kiến: {user_message}")
    return JSONResponse({"reply": reply_text or f"⚠️ {err_msg}", "chips": []})
@app.post("/api/cineai/generate-script-from-slots")
async def generate_script_from_slots(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    project_title = data.get("title", "Dự án mới")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    target_duration = data.get("target_duration", "45p")
    
    target_project = None
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                target_project = p
                break
                
    slots = target_project.get("ideation_slots", {}) if target_project else {}
    slots_text = json.dumps(slots, ensure_ascii=False) if slots else "Ý tưởng tự do về tình cảm và chia ly dưới mưa."
    
    prompt = (
        "Bạn là Nhà biên kịch điện ảnh của Cine AI Studio Pro 6.7.6. Dựa vào các biến số tâm lý:\n"
        f"{slots_text}\n"
        f"Định dạng yêu cầu: Khung hình [{aspect_ratio}], Thời lượng [{target_duration}].\n"
        "Hãy tạo kịch bản 3 Hồi hoàn chỉnh. Trả về DUY NHẤT một chuỗi JSON hợp lệ:\n"
        "{\n"
        '  "title": "Tên phim gợi ý đầy chất thơ",\n'
        '  "header": "Thể loại: ... • Khung hình: ' + aspect_ratio + ' • Thời lượng: ' + target_duration + '",\n'
        '  "story": "Nội dung câu chuyện 3 Hồi hoàn chỉnh (khoảng 600 - 1200 từ), nêu rõ tên nhân vật chính, đạo cụ then chốt, bối cảnh và cao trào."\n'
        "}"
    )
    raw_res, err = call_gemini_direct(prompt)
    if not raw_res:
        return JSONResponse({"status": "error", "message": f"⚠️ {err}"}, status_code=500)
        
    try:
        clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
        res_data = json.loads(clean_json)
    except Exception:
        res_data = {
            "title": project_title,
            "header": f"Thể loại: Tâm lý điện ảnh • {aspect_ratio} • {target_duration}",
            "story": raw_res
        }
        
    if target_project:
        target_project["title"] = res_data.get("title", project_title)
        target_project["header"] = res_data.get("header", "")
        target_project["project_raw_story"] = res_data.get("story", "")
        target_project["aspect_ratio"] = aspect_ratio
        target_project["target_duration"] = target_duration
        save_users()
        
    return JSONResponse({"status": "success", "data": res_data})


@app.post("/api/cineai/breakdown-scenes-enterprise")
async def breakdown_scenes_enterprise(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    project_title = data.get("title", "Dự án mới")
    raw_story = data.get("raw_story", "")
    
    if not raw_story and username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                raw_story = p.get("project_raw_story", "")
                break
                    
    if not raw_story:
        return JSONResponse({"reply": "⚠️ Chưa có nội dung kịch bản thô. Vui lòng hoàn thiện kịch bản tại Tầng 1!"}, status_code=400)
    
    keys = get_gemini_keys()
    if not keys:
        return JSONResponse({"reply": "⚠️ Chưa cấu hình GEMINI_API_KEYS trên Render!"}, status_code=500)
    
    selected_key = random.choice(keys)
    model_name = "gemini-2.5-pro"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={selected_key}"
    
    pro_prompt = (
        "Bạn là Tổng đạo diễn của Cine AI Studio Pro 6.7.6 Enterprise. Hãy phân tích kịch bản sau và trả về DUY NHẤT một chuỗi JSON hợp lệ, "
        "được chia theo cấu trúc 3 Hồi (Act I, Act II, Act III). Mỗi cảnh 30s-150s và gắn Master Schema Tokens.\n\n"
        f"Kịch bản gốc:\n{raw_story}"
    )
    payload = {"contents": [{"parts": [{"text": pro_prompt}]}], "systemInstruction": {"parts": [{"text": "Luôn luôn trả về định dạng JSON thuần túy chuẩn xác 100%."}]}}
    headers = {"Content-Type": "application/json"}
    
    parsed_scenes = None
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=40)
            data_res = response.json()
            clean_json_str = re.sub(r"^```json\s*|\s*```$", "", data_res["candidates"][0]["content"]["parts"][0]["text"].strip(), flags=re.IGNORECASE)
            parsed_scenes = json.loads(clean_json_str)
            break
        except Exception:
            if attempt == 2:
                parsed_scenes = {"acts": [{"act_name": "Act I", "scenes": [{"scene_id": 1, "title": "Cảnh khởi đầu", "duration_sec": 60, "summary": "Khởi động mạch phim.", "lock_tokens": {"face_id": "CHAR_DEFAULT", "costume": "COSTUME_DEFAULT", "landscape": "LOC_DEFAULT", "color_grading": "CINEMATIC_LUT"}}]}]}


    total_duration = 0
    act_durations = {"Act I": 0, "Act II": 0, "Act III": 0}
    if isinstance(parsed_scenes, dict) and "acts" in parsed_scenes:
        for act in parsed_scenes["acts"]:
            act_name = act.get("act_name", "Act I")
            for sc in act.get("scenes", []):
                dur = sc.get("duration_sec", 60)
                total_duration += dur
                act_durations[act_name] = act_durations.get(act_name, 0) + dur


    structured_data = {
        "schema_version": "6.7.6-Enterprise",
        "routing_model": model_name,
        "self_healing_applied": True,
        "pacing_metrics": {"total_duration_sec": total_duration, "act_breakdown": act_durations},
        "scenes_data": parsed_scenes,
        "alternate_takes": {},
        "active_takes": {},
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                p["scene_breakdown_enterprise"] = structured_data
                p["highest_tier"] = max(p.get("highest_tier", 1), 3)
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({
        "status": "success",
        "message": "🌟 Đã bóc tách phân cảnh kịch bản cấp độ Enterprise 6.7.6!",
        "metrics": structured_data["pacing_metrics"],
        "data": parsed_scenes
    })
async def async_render_background_worker(username, project_title, scene_id, render_cost):
    print(f"🔄 [BACKGROUND JOB STARTED]: Đang render ngầm phân cảnh {scene_id} cho dự án '{project_title}' của user '{username}'...")
    user_data = USERS_DB.get(username, {})
    if "projects" in user_data:
        for p in user_data["projects"]:
            if p.get("title") == project_title:
                enterprise_data = p.get("scene_breakdown_enterprise", {})
                if "alternate_takes" not in enterprise_data:
                    enterprise_data["alternate_takes"] = {}
                scene_key = f"scene_{scene_id}"
                if scene_key not in enterprise_data["alternate_takes"]:
                    enterprise_data["alternate_takes"][scene_key] = []
                current_takes = enterprise_data["alternate_takes"][scene_key]
                new_take_id = len(current_takes) + 1
                
                new_take_object = {
                    "take_id": new_take_id,
                    "status": "rendered_success_async",
                    "media_url": f"https://cdn.cineai.studio/renders/{project_title.replace(' ', '_')}_s{scene_id}_take{new_take_id}.mp4",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                current_takes.append(new_take_object)
                p["highest_tier"] = max(p.get("highest_tier", 1), 4)
                save_users()
                print(f"✅ [BACKGROUND JOB COMPLETED]: Đã hoàn tất render ngầm Scene {scene_id} - Take {new_take_id}!")
                break


@app.post("/api/cineai/render-scene-take")
async def render_scene_take(request: Request, background_tasks: BackgroundTasks, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    user_data = USERS_DB.get(username, {})
    current_credits = user_data.get("credits", 10)
    render_cost = 5
    if current_credits < render_cost:
        return JSONResponse({"status": "payment_required", "message": f"⚠️ Số dư Credit không đủ ({current_credits}/{render_cost} credit). Vui lòng nạp thêm qua menu Avatar để tiếp tục render!"}, status_code=402)
    
    data = await request.json()
    project_title = data.get("title", "Dự án mới")
    scene_id = data.get("scene_id", 1)
    
    user_data["credits"] = current_credits - render_cost
    save_users()


    background_tasks.add_task(async_render_background_worker, username, project_title, scene_id, render_cost)


    return JSONResponse({
        "status": "success",
        "message": f"🎬 Đã đưa Phân cảnh {scene_id} vào hàng đợi xử lý ngầm (Async Queue)! Đã trừ {render_cost} credit (Số dư còn lại: {user_data['credits']} credit).",
        "remaining_credits": user_data["credits"]
    })


@app.post("/api/cineai/set-active-take")
async def set_active_take(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    project_title = data.get("title", "Dự án mới")
    scene_id = data.get("scene_id", 1)
    selected_take_id = data.get("take_id", 1)
    
    project_data = None
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                project_data = p
                break
    if not project_data:
        return JSONResponse({"reply": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    enterprise_data = project_data.get("scene_breakdown_enterprise", {})
    scene_key = f"scene_{scene_id}"
    if "active_takes" not in enterprise_data:
        enterprise_data["active_takes"] = {}
    enterprise_data["active_takes"][scene_key] = selected_take_id
    save_users()
    return JSONResponse({
        "status": "success",
        "message": f"🎯 Đã chọn Take {selected_take_id} làm phiên bản chính thức cho Phân cảnh {scene_id}!",
        "active_takes": enterprise_data["active_takes"]
    })
@app.get("/api/cineai/get-rough-cut")
async def get_rough_cut(title: str = "Dự án mới", session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    project_data = None
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == title:
                project_data = p
                break
    if not project_data:
        return JSONResponse({"reply": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    enterprise_data = project_data.get("scene_breakdown_enterprise", {})
    scenes_json = enterprise_data.get("scenes_data", {})
    active_takes = enterprise_data.get("active_takes", {})
    alternate_takes = enterprise_data.get("alternate_takes", {})
    rough_cut_timeline = []
    total_duration = 0
    
    if "acts" in scenes_json:
        for act in scenes_json["acts"]:
            act_name = act.get("act_name", "Act I")
            for sc in act.get("scenes", []):
                s_id = sc.get("scene_id")
                s_key = f"scene_{s_id}"
                chosen_take_id = active_takes.get(s_key, 1)
                take_info = None
                if s_key in alternate_takes:
                    for t in alternate_takes[s_key]:
                        if t.get("take_id") == chosen_take_id:
                            take_info = t
                            break
                rough_cut_timeline.append({
                    "act": act_name,
                    "scene_id": s_id,
                    "title": sc.get("title"),
                    "duration_sec": sc.get("duration_sec", 60),
                    "active_take_id": chosen_take_id,
                    "media_url": take_info.get("media_url") if take_info else "Chưa render take"
                })
                total_duration += sc.get("duration_sec", 60)


    return JSONResponse({
        "status": "success",
        "total_timeline_duration_sec": total_duration,
        "rough_cut_playlist": rough_cut_timeline
    })


@app.get("/api/cineai/export-srt")
async def export_srt_subtitles(title: str = "Dự án mới", session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    project_data = None
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == title:
                project_data = p
                break
    if not project_data:
        return JSONResponse({"reply": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    enterprise_data = project_data.get("scene_breakdown_enterprise", {})
    scenes_json = enterprise_data.get("scenes_data", {})
    srt_content = ""
    current_time = 0.0
    idx = 1
    
    def format_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


    if "acts" in scenes_json:
        for act in scenes_json["acts"]:
            for sc in act.get("scenes", []):
                dur = float(sc.get("duration_sec", 60))
                summary = sc.get("summary", "")
                srt_content += f"{idx}\n{format_time(current_time)} --> {format_time(current_time + dur)}\n[Lip-Sync] {summary}\n\n"
                current_time += dur
                idx += 1


    return JSONResponse({"status": "success", "srt_format": srt_content})


@app.post("/api/payments/webhook")
async def sepay_payment_webhook(request: Request):
    try:
        data = await request.json()
        content = data.get("content", "")
        transfer_amount = int(data.get("transferAmount", 0))
        match = re.search(r"NAPCREDIT\s+([a-zA-Z0-9_-]+)", content, re.IGNORECASE)
        if match and match.group(1) in USERS_DB:
            target_username = match.group(1)
            credits_to_add = int(transfer_amount / 1000)
            USERS_DB[target_username]["credits"] = USERS_DB[target_username].get("credits", 0) + credits_to_add
            save_users()
            return JSONResponse({"success": True, "message": f"Đã cộng {credits_to_add} credit cho user {target_username}"})
        return JSONResponse({"success": False, "message": "Không khớp cú pháp nạp tiền"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@app.post("/api/payments/stripe-webhook")
async def stripe_payment_webhook(request: Request):
    try:
        event_data = await request.json()
        if event_data.get("type") == "payment_intent.succeeded":
            intent = event_data.get("data", {}).get("object", {})
            metadata = intent.get("metadata", {})
            target_username = metadata.get("username")
            amount_received = int(intent.get("amount_received", 0))
            if target_username and target_username in USERS_DB:
                credits_to_add = int(amount_received / 100 * 10)
                USERS_DB[target_username]["credits"] = USERS_DB[target_username].get("credits", 0) + credits_to_add
                save_users()
                return JSONResponse({"status": "success", "message": f"Đã cộng {credits_to_add} credit qua Apple/Google Pay cho user {target_username}"})
        return JSONResponse({"status": "ignored"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
def get_studio_html_block_1(target_project, user_credits, active_tier, highest_tier, username):
    def get_tier_classes(idx):
        if idx == active_tier:
            return "bg-amber-500 text-slate-950 shadow-md pointer-events-none"
        if idx <= highest_tier:
            return "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"
        return "bg-slate-950 text-slate-600 pointer-events-none opacity-40"


    t1_cls = get_tier_classes(1)
    t2_cls = get_tier_classes(2)
    t3_cls = get_tier_classes(3)
    t4_cls = get_tier_classes(4)
    t1_vis = "block" if active_tier == 1 else "hidden"
    t2_vis = "block" if active_tier == 2 else "hidden"
    t3_vis = "block" if active_tier == 3 else "hidden"
    t4_vis = "block" if active_tier == 4 else "hidden"
    enc_title = urllib.parse.quote(target_project.get("title", ""))


    tmpl = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cine AI Studio Pro 6.7.6 Enterprise</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-3 sm:p-5 font-sans pb-24">
        <div class="max-w-4xl mx-auto space-y-3">
            
            <!-- HEADER DÒNG 1: LOGO TRẢI DÀI & AVATAR CÁ NHÂN TÍCH HỢP NẠP CREDIT -->
            <div class="flex justify-between items-center bg-slate-900/90 backdrop-blur-md p-3.5 rounded-2xl border border-slate-800 shadow-xl relative">
                <div class="flex items-center gap-2">
                    <span class="text-xl">🎬</span>
                    <h1 class="text-sm sm:text-base font-black text-amber-400 tracking-wide uppercase">Cine AI Studio Pro 6.7.6</h1>
                </div>
                
                <div class="relative">
                    <button onclick="toggleProfileMenu()" class="w-9 h-9 rounded-full bg-slate-800 border-2 border-amber-400/80 flex items-center justify-center hover:bg-slate-700 transition shadow">
                        <span class="text-sm">👤</span>
                    </button>
                    <!-- DROPDOWN MENU TÍCH HỢP NẠP CREDIT -->
                    <div id="profile-dropdown" class="hidden absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-800 rounded-2xl p-3 shadow-2xl z-50 space-y-2.5">
                        <div class="border-b border-slate-800 pb-2">
                            <p class="text-xs font-bold text-slate-200">USER_NAME_VAL</p>
                            <p class="text-[11px] text-emerald-400 font-bold mt-0.5">💰 Số dư: USER_CREDITS_VAL Credit</p>
                        </div>
                        <button onclick="openTopUpModal()" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-2 rounded-xl text-xs transition shadow flex items-center justify-center gap-1">
                            💳 Nạp Thêm Credit
                        </button>
                        <a href="/logout" class="block w-full text-center bg-rose-950/80 hover:bg-rose-900 border border-rose-800/80 text-rose-200 py-1.5 rounded-xl text-xs font-bold transition">Đăng Xuất</a>
                    </div>
                </div>
            </div>


            <!-- HEADER DÒNG 2: 3 NÚT TIỆN ÍCH (+ DỰ ÁN MỚI, THƯ VIỆN, TRỢ LÝ ẢO) -->
            <div class="grid grid-cols-3 gap-2 text-center text-xs font-bold">
                <a href="/?new_project=1" class="bg-amber-500 hover:bg-amber-400 text-slate-950 py-2 rounded-xl transition shadow flex items-center justify-center gap-1">➕ Dự Án Mới</a>
                <a href="/library" class="bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 py-2 rounded-xl transition shadow flex items-center justify-center gap-1">📁 Thư Viện</a>
                <button onclick="toggleVirtualAssistantModal()" class="bg-indigo-600/80 hover:bg-indigo-600 text-white py-2 rounded-xl transition shadow flex items-center justify-center gap-1">🤖 Trợ Lý Ảo</button>
            </div>


            <!-- HEADER DÒNG 3: BREADCRUMB 4 TẦNG THU GỌN -->
            <div class="grid grid-cols-4 gap-1.5 bg-slate-900 p-1.5 rounded-2xl border border-slate-800 text-center text-xs font-bold">
                <a href="/?load_project=ENC_TITLE_VAL&tier=1" class="py-2 rounded-xl transition T1_CLS_VAL">1. Kịch Bản</a>
                <a href="/?load_project=ENC_TITLE_VAL&tier=2" class="py-2 rounded-xl transition T2_CLS_VAL">2. Khóa Token</a>
                <a href="/?load_project=ENC_TITLE_VAL&tier=3" class="py-2 rounded-xl transition T3_CLS_VAL">3. Bóc Tách</a>
                <a href="/?load_project=ENC_TITLE_VAL&tier=4" class="py-2 rounded-xl transition T4_CLS_VAL">4. Render</a>
            </div>


            <!-- HEADER DÒNG 4: TAB SWITCHER 2 LUỒNG (TRONG TẦNG 1) -->
            <div id="tier1-nav-switcher" class="T1_VIS_VAL bg-slate-900 p-1 rounded-2xl border border-slate-800 grid grid-cols-2 gap-1 text-xs font-bold">
                <button id="tab-btn-stream1" onclick="switchStream(1)" class="py-2 rounded-xl bg-amber-500 text-slate-950 transition shadow">📄 Đã Có Kịch Bản</button>
                <button id="tab-btn-stream2" onclick="switchStream(2)" class="py-2 rounded-xl text-slate-400 hover:text-slate-200 transition">✨ Nhờ Đạo Diễn Ảo</button>
            </div>
    """
    tmpl = tmpl.replace("USER_NAME_VAL", username)
    tmpl = tmpl.replace("USER_CREDITS_VAL", str(user_credits))
    tmpl = tmpl.replace("PROJECT_TITLE_VAL", target_project.get("title", ""))
    tmpl = tmpl.replace("ENC_TITLE_VAL", enc_title)
    tmpl = tmpl.replace("T1_CLS_VAL", t1_cls).replace("T2_CLS_VAL", t2_cls).replace("T3_CLS_VAL", t3_cls).replace("T4_CLS_VAL", t4_cls)
    tmpl = tmpl.replace("T1_VIS_VAL", t1_vis)
    return tmpl, t1_vis, t2_vis, t3_vis, t4_vis
def get_studio_html_block_2(target_project, t1_vis, t2_vis, t3_vis, t4_vis, tokens_html):
    tmpl = """
            <!-- ===================== MÀN HÌNH TẦNG 1: 2 LUỒNG TÁCH BIỆT ===================== -->
            <div id="screen-tier-1" class="T1_VIS_VAL space-y-3">
                <div id="stream-1-container" class="bg-slate-900 p-4 sm:p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Tên Dự Án Phim:</label>
                        <input type="text" id="project-title" value="PROJECT_TITLE_VAL" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-amber-300 font-bold">
                    </div>
                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Đề Mục / Logline:</label>
                        <input type="text" id="project-header" value="PROJECT_HEADER_VAL" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200">
                    </div>
                    <div class="p-3 bg-slate-950/80 rounded-2xl border border-slate-800 space-y-2">
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-[10px] font-bold text-amber-400 uppercase mb-1">🎬 Khung Hình:</label>
                                <select id="film-aspect-ratio" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-200 font-semibold">
                                    <option value="16:9">16:9 • Điện Ảnh</option>
                                    <option value="9:16">9:16 • Dọc (Reels/Shorts)</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-[10px] font-bold text-amber-400 uppercase mb-1">⏱️ Thời Lượng:</label>
                                <select id="film-duration" onchange="updateEstimateBadge()" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-200 font-semibold">
                                    <option value="45p">45 Phút (~30 cảnh)</option>
                                    <option value="15p">15 Phút (~10 cảnh)</option>
                                    <option value="3p">3 Phút (~3 cảnh)</option>
                                </select>
                            </div>
                        </div>
                        <div id="cost-estimate-badge" class="text-[10px] bg-indigo-950/60 border border-indigo-800/60 p-2 rounded-xl text-indigo-300 leading-tight">
                            💡 <b>Dự toán quy mô:</b> Phim 45 phút cần ~30 phân cảnh (ước tính ~150 Credit).
                        </div>
                    </div>
                    <div class="p-3 bg-slate-950/60 rounded-2xl border border-slate-800 space-y-2">
                        <span class="text-[11px] text-slate-400 block font-semibold">Nạp tệp kịch bản (.txt, .md):</span>
                        <div class="flex gap-2">
                            <input type="file" id="file-story" accept=".txt,.md" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-1.5 text-xs text-slate-400 cursor-pointer">
                            <button onclick="uploadStoryFile()" class="bg-blue-600 hover:bg-blue-500 px-3.5 py-1.5 rounded-xl text-xs font-bold text-white whitespace-nowrap shadow transition">Nạp File</button>
                        </div>
                    </div>
                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Nội Dung Kịch Bản (Gõ hoặc dán trực tiếp):</label>
                        <textarea id="project-story" rows="6" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 transition">PROJECT_STORY_VAL</textarea>
                    </div>
                </div>


                <div id="stream-2-container" class="hidden bg-slate-900 p-4 sm:p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span class="text-xs font-bold text-amber-400 uppercase">✨ Đạo Diễn Ảo Khơi Mở Ý Tưởng</span>
                        <button onclick="autoGenerateScriptFromSlots()" class="bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 font-black px-3 py-1 rounded-xl text-[10px] shadow transition animate-pulse">✨ Khởi Tạo Ngay</button>
                    </div>
                    <div id="chat-box" class="bg-slate-950 h-36 rounded-2xl p-3 overflow-y-auto text-xs text-slate-300 border border-slate-800 space-y-2 leading-relaxed">
                        <p class="text-blue-200">Chào bạn! Tôi là Đạo diễn ảo. Giờ này bạn đang ngồi ở đâu, và âm thanh bạn nghe thấy lúc này là gì?</p>
                    </div>
                    <div id="quick-chips-tray" class="flex flex-wrap gap-1.5 pt-1">
                        <button onclick="selectChip(this.innerText)" class="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-300 px-2.5 py-1 rounded-xl text-[11px] transition">Tiếng mưa rơi trên mái tôn</button>
                        <button onclick="selectChip(this.innerText)" class="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-300 px-2.5 py-1 rounded-xl text-[11px] transition">Căn phòng đêm tĩnh mịch</button>
                        <button onclick="focusCustomInput()" class="bg-amber-500/10 border border-amber-500/30 text-amber-400 px-2.5 py-1 rounded-xl text-[11px] font-bold transition">✍️ Lựa chọn khác...</button>
                    </div>
                    <div class="flex gap-2 pt-1">
                        <input type="text" id="chat-input" placeholder="Nhập tâm sự hoặc chọn gợi ý..." class="flex-1 bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 focus:outline-none focus:border-amber-500 transition" onkeypress="if(event.key==='Enter') sendChat()">
                        <button onclick="sendChat()" class="bg-indigo-600 hover:bg-indigo-500 px-4 py-2.5 rounded-xl font-bold text-xs text-white transition shadow">Gửi</button>
                    </div>
                </div>
            </div>


            <!-- ===================== MÀN HÌNH TẦNG 2: CHECKLIST DUYỆT KHÓA TOKEN (MASTER SCHEMA) ===================== -->
            <div id="screen-tier-2" class="T2_VIS_VAL space-y-3">
                <div class="bg-slate-900 p-4 sm:p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2.5">
                        <div>
                            <h2 class="text-xs font-bold text-amber-400 uppercase tracking-wider">📋 Tầng 2: Kiểm Kê Master Schema (4 Tầng Lọc & Thời Gian)</h2>
                            <p class="text-[10px] text-slate-400">Khóa mẫu thực thể, bối cảnh, đạo cụ tiến hóa và phong cách thị giác.</p>
                        </div>
                        <button onclick="runAuditAssets()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-3 py-1.5 rounded-xl text-[11px] transition shadow flex items-center gap-1">🔍 Quét Kịch Bản</button>
                    </div>


                    <div id="audit-checklist-tray" class="space-y-2 max-h-72 overflow-y-auto pr-1">
                        <div class="text-center py-6 text-slate-500 text-xs">
                            Bấm nút <b>"🔍 Quét Kịch Bản"</b> để AI trích xuất toàn bộ Master Schema theo 4 tầng lọc!
                        </div>
                    </div>


                    <div class="p-2.5 bg-slate-950/80 rounded-2xl border border-slate-800 space-y-1.5">
                        <span class="text-[10px] font-bold text-slate-400 block uppercase">Kho Token Đã Khóa Của Dự Án:</span>
                        <div id="tokens-tray" class="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto">TOKENS_HTML_VAL</div>
                    </div>
                </div>
            </div>


            <!-- ===================== MÀN HÌNH TẦNG 3 ===================== -->
            <div id="screen-tier-3" class="T3_VIS_VAL bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                <h2 class="text-xs font-bold text-amber-400 uppercase tracking-wider">🎬 Tầng 3: Bóc Tách Phân Cảnh & Ma Trận 3 Hồi</h2>
                <button onclick="runBreakdown()" class="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold py-3 rounded-2xl text-xs shadow-lg transition">🚀 Kích Hoạt AI Bóc Tách Phân Cảnh</button>
                <div id="breakdown-result" class="bg-slate-950 p-3 rounded-2xl border border-slate-800 text-xs text-slate-300 max-h-40 overflow-y-auto">Chưa bóc tách kịch bản. Hãy bấm nút phía trên.</div>
            </div>


            <!-- ===================== MÀN HÌNH TẦNG 4 ===================== -->
            <div id="screen-tier-4" class="T4_VIS_VAL bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                <h2 class="text-xs font-bold text-amber-400 uppercase tracking-wider">🎞️ Tầng 4: Phòng Dựng & Render</h2>
                <button onclick="renderScene(1)" class="w-full bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black py-3 rounded-2xl text-xs shadow transition">🎬 Render Phân Cảnh Mẫu (5 C)</button>
                <button onclick="fetchTimeline()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-2.5 rounded-2xl text-xs transition">🎞️ Xem Timeline Rough-Cut</button>
                <button onclick="exportSrtSubtitles()" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2.5 rounded-2xl text-xs transition">📜 Xuất Phụ Đề .SRT</button>
            </div>
        </div>


        <!-- CỤM 2 NÚT HÀNH ĐỘNG CỐ ĐỊNH ĐÁY -->
        <div class="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur-md border-t border-slate-800 p-3 z-40">
            <div class="max-w-4xl mx-auto flex gap-2">
                <button onclick="saveDraftCurrent(ACTIVE_TIER_VAL)" class="w-1/3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition shadow">💾 Lưu Nháp</button>
                <button onclick="proceedToTier(ACTIVE_TIER_VAL + 1)" class="w-2/3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3.5 rounded-2xl text-xs transition shadow-lg uppercase tracking-wider">Tiếp Tục ➔</button>
            </div>
        </div>
    """
    tmpl = tmpl.replace("PROJECT_TITLE_VAL", target_project.get("title", ""))
    tmpl = tmpl.replace("PROJECT_HEADER_VAL", target_project.get("header", ""))
    tmpl = tmpl.replace("PROJECT_STORY_VAL", target_project.get("project_raw_story", ""))
    tmpl = tmpl.replace("T1_VIS_VAL", t1_vis).replace("T2_VIS_VAL", t2_vis).replace("T3_VIS_VAL", t3_vis).replace("T4_VIS_VAL", t4_vis)
    tmpl = tmpl.replace("TOKENS_HTML_VAL", tokens_html or "<p class='text-slate-500 text-[11px] italic'>Chưa có token nào.</p>")
    return tmpl
def get_studio_javascript():
    return """
        <script>
            let currentActiveTier = ACTIVE_TIER_VAL;
            let currentProjectTitle = "PROJECT_TITLE_VAL";


            function toggleProfileMenu() {
                const m = document.getElementById('profile-dropdown');
                m.classList.toggle('hidden');
            }


            function toggleVirtualAssistantModal() {
                switchStream(2);
            }


            function openTopUpModal() {
                toggleProfileMenu();
                let modal = document.getElementById('topup-modal');
                if (!modal) {
                    modal = document.createElement('div');
                    modal.id = 'topup-modal';
                    modal.className = 'fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50';
                    modal.innerHTML = `
                        <div class="bg-slate-900 border border-slate-800 p-5 rounded-3xl max-w-md w-full space-y-4 shadow-2xl text-slate-100">
                            <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                                <h3 class="text-sm font-bold text-amber-400 uppercase">💳 Nạp Credit Vào Ví Sáng Tạo</h3>
                                <button onclick="document.getElementById('topup-modal').remove()" class="text-slate-400 hover:text-slate-100 font-bold text-sm">✕</button>
                            </div>
                            <div class="space-y-2.5 text-xs text-slate-300">
                                <p class="font-semibold text-slate-200">Chọn phương thức thanh toán nhanh:</p>
                                <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800 space-y-1.5">
                                    <div class="font-bold text-amber-300">🇻🇳 Cổng Nội Địa (SePay & VietQR):</div>
                                    <p class="text-[11px] text-slate-400">Chuyển khoản ngân hàng tự động. Cú pháp: <code class="bg-slate-900 text-amber-400 px-1.5 py-0.5 rounded font-mono">NAPCREDIT TÊN_USER</code> (1.000đ = 1 Credit).</p>
                                </div>
                                <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800 space-y-1.5">
                                    <div class="font-bold text-indigo-400">🌍 Quốc tế (Apple Pay / Google Pay):</div>
                                    <p class="text-[11px] text-slate-400">Thanh toán tự động 1 chạm bảo mật qua Stripe Elements ($1 = 10 Credit).</p>
                                </div>
                            </div>
                            <button onclick="document.getElementById('topup-modal').remove()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-2.5 rounded-xl text-xs transition">Đóng</button>
                        </div>
                    `;
                    document.body.appendChild(modal);
                }
            }


            function switchStream(streamId) {
                const s1 = document.getElementById('stream-1-container');
                const s2 = document.getElementById('stream-2-container');
                const b1 = document.getElementById('tab-btn-stream1');
                const b2 = document.getElementById('tab-btn-stream2');
                if (streamId === 1) {
                    s1.classList.remove('hidden');
                    s2.classList.add('hidden');
                    b1.className = "py-2 rounded-xl bg-amber-500 text-slate-950 transition shadow";
                    b2.className = "py-2 rounded-xl text-slate-400 hover:text-slate-200 transition";
                } else {
                    s1.classList.add('hidden');
                    s2.classList.remove('hidden');
                    b2.className = "py-2 rounded-xl bg-amber-500 text-slate-950 transition shadow";
                    b1.className = "py-2 rounded-xl text-slate-400 hover:text-slate-200 transition";
                }
            }


            function updateEstimateBadge() {
                const dur = document.getElementById('film-duration').value;
                const badge = document.getElementById('cost-estimate-badge');
                if (dur === '45p') badge.innerHTML = '💡 <b>Dự toán quy mô:</b> Phim 45 phút cần ~30 phân cảnh (ước tính ~150 Credit).';
                else if (dur === '15p') badge.innerHTML = '💡 <b>Dự toán quy mô:</b> Phim 15 phút cần ~10 phân cảnh (ước tính ~50 Credit).';
                else badge.innerHTML = '💡 <b>Dự toán quy mô:</b> Phim ngắn 3 phút cần ~3 phân cảnh (ước tính ~15 Credit).';
            }


            function selectChip(text) {
                document.getElementById('chat-input').value = text;
                sendChat();
            }


            function focusCustomInput() {
                const input = document.getElementById('chat-input');
                input.placeholder = "Nhập ý tưởng riêng của bạn...";
                input.focus();
            }


            async function runAuditAssets() {
                const tray = document.getElementById('audit-checklist-tray');
                tray.innerHTML = "<div class='text-center py-4 text-amber-400 text-xs animate-pulse'>⏳ Đang quét Master Schema & Ma Trận Thời Gian...</div>";
                try {
                    const res = await fetch('/api/cineai/audit-script-assets', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({title: currentProjectTitle})
                    });
                    const d = await res.json();
                    if(d.status === 'success') {
                        renderAuditChecklist(d.audit_data);
                    } else {
                        tray.innerHTML = `<div class='text-rose-400 text-xs p-3 text-center'>${d.message}</div>`;
                    }
                } catch(e) {
                    tray.innerHTML = "<div class='text-rose-400 text-xs p-3 text-center'>⚠️ Lỗi kết nối kiểm kê!</div>";
                }
            }
            function renderAuditChecklist(audit) {
                const tray = document.getElementById('audit-checklist-tray');
                let html = '';
                
                if (audit.time_jumps_detected && audit.time_jumps_detected.length > 0) {
                    html += `<div class="bg-indigo-950/40 p-2.5 rounded-xl border border-indigo-800/50 mb-2">
                        <span class="text-[10px] font-bold text-indigo-300 uppercase block">⏳ Bước nhảy thời gian phát hiện:</span>
                        <p class="text-[11px] text-slate-200 mt-0.5">${audit.time_jumps_detected.join(' • ')}</p>
                    </div>`;
                }


                const renderCard = (item, catLabel, catType) => `
                    <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800 space-y-2">
                        <div class="flex justify-between items-start">
                            <div>
                                <span class="text-[10px] font-bold bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded-md border border-indigo-800/60">${catLabel}</span>
                                <h4 class="text-xs font-black text-slate-100 mt-1">${item.name}</h4>
                            </div>
                            <span class="text-[10px] text-amber-400 font-bold bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/60">⚠️ Chưa Khóa</span>
                        </div>
                        <p class="text-[11px] text-slate-400 leading-tight">${item.description || item.audio_signature || ''}</p>
                        ${item.temporal_states ? `<p class='text-[10px] text-emerald-400'>🔄 Trạng thái thời gian: ${item.temporal_states.join(', ')}</p>` : ''}
                        ${item.evolution_lineage ? `<p class='text-[10px] text-purple-400'>⚔️ Tiến trình đồ vật: ${item.evolution_lineage.join(' ➔ ')}</p>` : ''}
                        <div class="flex gap-1.5 pt-1">
                            <label class="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-center py-1.5 rounded-xl text-[10px] font-bold cursor-pointer transition">
                                📁 Tải Tệp Lên
                                <input type="file" class="hidden" onchange="uploadDirectAsset(this, '${catType}', '${item.name}')">
                            </label>
                            <button onclick="requestConcept('${item.name}', '${item.description || ''}')" class="flex-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 py-1.5 rounded-xl text-[10px] font-bold border border-amber-500/30 transition">
                                ✨ AI Phác Họa
                            </button>
                        </div>
                    </div>
                `;


                (audit.entities || []).forEach(e => html += renderCard(e, e.archetype || 'Thực thể', 'character'));
                (audit.locations || []).forEach(l => html += renderCard(l, 'Bối cảnh', 'landscape'));
                (audit.props || []).forEach(p => html += renderCard(p, 'Đạo cụ định mệnh', 'costume'));
                (audit.audio_signatures || []).forEach(a => html += renderCard(a, 'Âm thanh 3D', 'bgm'));


                tray.innerHTML = html || "<div class='text-slate-500 text-xs text-center py-4'>Không phát hiện đối tượng nào.</div>";
            }


            async function uploadDirectAsset(inputElement, category, assetName) {
                if(!inputElement.files || inputElement.files.length === 0) return;
                const file = inputElement.files[0];
                const isAudio = category === 'bgm' || category === 'voice';
                const endpoint = isAudio ? '/api/cineai/upload-audio-token' : '/api/cineai/upload-visual-token';
                const formData = new FormData();
                formData.append('file', file);
                formData.append('token_category', category);
                formData.append('token_name', assetName);
                formData.append('project_title', currentProjectTitle);


                try {
                    const res = await fetch(endpoint, {method: 'POST', body: formData});
                    const d = await res.json();
                    alert(d.message);
                    if(d.status === 'success') location.reload();
                } catch(e) {
                    alert('Lỗi nạp tệp khóa token!');
                }
            }


            async function requestConcept(name, desc) {
                const tweak = prompt(`Nhập yêu cầu bổ sung cho [${name}] (hoặc để trống):`, "Chất lượng điện ảnh 4K, phong cách sâu lắng");
                if (tweak === null) return;
                try {
                    const res = await fetch('/api/cineai/generate-asset-concept-prompt', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({asset_name: name, asset_description: desc, user_tweak: tweak})
                    });
                    const d = await res.json();
                    alert(`🎨 AI đã sinh Visual Prompt khóa mẫu cho [${name}]:\\n\\n${d.concept_prompt}`);
                } catch(e) {
                    alert('Lỗi tạo concept!');
                }
            }
            async function proceedToTier(targetTier) {
                if (targetTier > 4) targetTier = 4;
                const title = document.getElementById('project-title') ? document.getElementById('project-title').value : currentProjectTitle;
                const header = document.getElementById('project-header') ? document.getElementById('project-header').value : "";
                const story = document.getElementById('project-story') ? document.getElementById('project-story').value : "";
                const ratio = document.getElementById('film-aspect-ratio') ? document.getElementById('film-aspect-ratio').value : "16:9";
                const dur = document.getElementById('film-duration') ? document.getElementById('film-duration').value : "45p";
                
                try {
                    const res = await fetch('/api/cineai/save-draft', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({old_title: currentProjectTitle, title: title, header: header, story: story, aspect_ratio: ratio, target_duration: dur, tier: targetTier})
                    });
                    const data = await res.json();
                    if (data.saved_title) currentProjectTitle = data.saved_title;
                } catch(e) {}
                
                window.location.href = '/?load_project=' + encodeURIComponent(currentProjectTitle) + '&tier=' + targetTier;
            }


            async function saveDraftCurrent(tier) {
                const title = document.getElementById('project-title') ? document.getElementById('project-title').value : currentProjectTitle;
                const header = document.getElementById('project-header') ? document.getElementById('project-header').value : "";
                const story = document.getElementById('project-story') ? document.getElementById('project-story').value : "";
                const ratio = document.getElementById('film-aspect-ratio') ? document.getElementById('film-aspect-ratio').value : "16:9";
                const dur = document.getElementById('film-duration') ? document.getElementById('film-duration').value : "45p";
                try {
                    const res = await fetch('/api/cineai/save-draft', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({old_title: currentProjectTitle, title: title, header: header, story: story, aspect_ratio: ratio, target_duration: dur, tier: tier})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if(data.status === 'success') currentProjectTitle = data.saved_title;
                } catch(e) {
                    alert('Lỗi kết nối khi lưu nháp!');
                }
            }


            async function uploadStoryFile() {
                const fileInput = document.getElementById('file-story');
                if(fileInput.files.length === 0) return alert('⚠️ Vui lòng chọn tệp kịch bản (.txt, .md)!');
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('project_title', currentProjectTitle);
                try {
                    const res = await fetch('/api/cineai/upload-asset-explicit', {method: 'POST', body: formData});
                    const data = await res.json();
                    if(data.status === 'success') {
                        document.getElementById('project-story').value = data.extracted_content;
                        alert(data.message);
                        saveDraftCurrent(1);
                    } else alert(data.message);
                } catch(e) { alert('Lỗi nạp tệp kịch bản!'); }
            }


            async function runBreakdown() {
                const box = document.getElementById('breakdown-result');
                box.innerHTML = "⏳ Đang gọi AI bóc tách phân cảnh...";
                const res = await fetch('/api/cineai/breakdown-scenes-enterprise', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title: currentProjectTitle})
                });
                const data = await res.json();
                if(data.status === 'success') {
                    box.innerHTML = "✅ Bóc tách thành công! Tổng thời lượng: " + data.metrics.total_duration_sec + " giây.<br><pre class='text-[10px] text-slate-400 mt-2 whitespace-pre-wrap'>" + JSON.stringify(data.data, null, 2) + "</pre>";
                } else box.innerHTML = data.reply;
            }


            async function renderScene(id) {
                const res = await fetch('/api/cineai/render-scene-take', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title: currentProjectTitle, scene_id: id})
                });
                const data = await res.json();
                alert(data.message);
            }
            async function fetchTimeline() {
                const res = await fetch('/api/cineai/get-rough-cut?title=' + encodeURIComponent(currentProjectTitle));
                const data = await res.json();
                alert('🎞️ Rough-Cut Timeline: ' + data.total_timeline_duration_sec + ' giây.');
            }


            async function exportSrtSubtitles() {
                const res = await fetch('/api/cineai/export-srt?title=' + encodeURIComponent(currentProjectTitle));
                const data = await res.json();
                if(data.srt_format) {
                    const blob = new Blob([data.srt_format], {type: 'text/plain'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = currentProjectTitle + '_subtitles.srt';
                    a.click();
                } else alert('Chưa có dữ liệu phân cảnh để xuất phụ đề!');
            }


            async function sendChat() {
                const input = document.getElementById('chat-input');
                const box = document.getElementById('chat-box');
                const chipsTray = document.getElementById('quick-chips-tray');
                const text = input.value.trim();
                if(!text) return;


                box.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-2.5 rounded-xl inline-block text-slate-100 max-w-[85%] text-left">' + text + '</span></div>';
                input.value = '';
                box.scrollTop = box.scrollHeight;


                try {
                    const res = await fetch('/api/cineai/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({message: text, title: currentProjectTitle, tier: 1})
                    });
                    const data = await res.json();
                    box.innerHTML += '<div class="bg-blue-950/60 border border-blue-800/50 p-3 rounded-xl text-blue-200 leading-relaxed max-w-[85%]" style="overflow-wrap: anywhere;">' + data.reply + '</div>';
                    box.scrollTop = box.scrollHeight;


                    if (data.chips && data.chips.length > 0) {
                        let chipHtml = '';
                        data.chips.forEach(c => {
                            chipHtml += '<button onclick="selectChip(this.innerText)" class="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-300 px-2.5 py-1 rounded-xl text-[11px] transition">' + c + '</button>';
                        });
                        chipHtml += '<button onclick="focusCustomInput()" class="bg-amber-500/10 border border-amber-500/30 text-amber-400 px-2.5 py-1 rounded-xl text-[11px] font-bold transition">✍️ Lựa chọn khác...</button>';
                        chipsTray.innerHTML = chipHtml;
                    }
                } catch(e) {
                    box.innerHTML += '<div class="bg-rose-950/60 p-2.5 rounded-xl text-rose-200">⚠️ Lỗi kết nối Đạo diễn ảo!</div>';
                }
            }


            async function autoGenerateScriptFromSlots() {
                const box = document.getElementById('chat-box');
                const ratio = document.getElementById('film-aspect-ratio').value;
                const dur = document.getElementById('film-duration').value;
                
                box.innerHTML += '<div class="text-amber-300 font-bold">✨ Đang tổng hợp kịch bản [' + ratio + ' • ' + dur + ']...</div>';
                box.scrollTop = box.scrollHeight;
                
                try {
                    const res = await fetch('/api/cineai/generate-script-from-slots', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({title: currentProjectTitle, aspect_ratio: ratio, target_duration: dur})
                    });
                    const resData = await res.json();
                    if (resData.status === 'success') {
                        document.getElementById('project-title').value = resData.data.title;
                        document.getElementById('project-header').value = resData.data.header;
                        document.getElementById('project-story').value = resData.data.story;
                        currentProjectTitle = resData.data.title;
                        switchStream(1);
                        alert('🎉 Kịch bản đã được khởi tạo thành công và đổ vào Luồng 1!');
                    } else alert(resData.message);
                } catch(e) { alert('Lỗi tạo kịch bản tự động!'); }
            }
        </script>
    </body>
    </html>
    ""”
@app.get("/", response_class=HTMLResponse)
async def home(session_id: str = Cookie(None), load_project: str = None, tier: int = None, new_project: str = None):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    user_data = USERS_DB.get(username, {})
    user_credits = user_data.get("credits", 10)
    projects = user_data.get("projects", [])
    
    target_project = None
    if new_project == "1":
        new_title = f"Dự án mới #{len(projects) + 1}"
        target_project = {
            "title": new_title,
            "header": "Thể loại: Điện ảnh cảm xúc • Tự do sáng tạo",
            "project_raw_story": "",
            "aspect_ratio": "16:9",
            "target_duration": "45p",
            "token_registry": {"visual_tokens": [], "audio_tokens": []},
            "assets_audit": {},
            "ideation_slots": {},
            "highest_tier": 1,
            "current_tier": 1
        }
        projects.insert(0, target_project)
        user_data["projects"] = projects[:2]
        save_users()
    elif load_project:
        for p in projects:
            if p.get("title") == load_project:
                target_project = p
                break
    elif projects:
        target_project = projects[0]
        
    if not target_project:
        target_project = {
            "title": "Dự án phim mới",
            "header": "Thể loại: Cổ phong huyền huyễn • Tình cảm tâm lý",
            "project_raw_story": "",
            "aspect_ratio": "16:9",
            "target_duration": "45p",
            "token_registry": {"visual_tokens": [], "audio_tokens": []},
            "assets_audit": {},
            "ideation_slots": {},
            "highest_tier": 1,
            "current_tier": 1
        }
        projects.append(target_project)
        user_data["projects"] = projects
        save_users()


    if tier:
        target_project["highest_tier"] = max(target_project.get("highest_tier", 1), tier)
        active_tier = tier
        save_users()
    else:
        active_tier = target_project.get("highest_tier", 1)
    highest_tier = target_project.get("highest_tier", 1)


    tokens_html = ""
    visual_tokens = target_project.get("token_registry", {}).get("visual_tokens", [])
    audio_tokens = target_project.get("token_registry", {}).get("audio_tokens", [])
    for vt in visual_tokens:
        tokens_html += f'<span class="bg-indigo-950 border border-indigo-800 text-indigo-300 text-[10px] px-2 py-0.5 rounded-full font-bold">🖼️ {vt.get("token_id")} ({vt.get("name") or vt.get("category")})</span>'
    for at in audio_tokens:
        tokens_html += f'<span class="bg-emerald-950 border border-emerald-800 text-emerald-300 text-[10px] px-2 py-0.5 rounded-full font-bold">🎵 {at.get("token_id")} ({at.get("name") or at.get("category")})</span>'


    p1, t1_vis, t2_vis, t3_vis, t4_vis = get_studio_html_block_1(target_project, user_credits, active_tier, highest_tier, username)
    p2 = get_studio_html_block_2(target_project, t1_vis, t2_vis, t3_vis, t4_vis, tokens_html)
    p3 = get_studio_javascript()
    p3 = p3.replace("ACTIVE_TIER_VAL", str(active_tier))
    p3 = p3.replace("HIGHEST_TIER_VAL", str(highest_tier))
    p3 = p3.replace("PROJECT_TITLE_VAL", target_project.get("title", ""))


    return HTMLResponse(content=p1 + p2 + p3)


@app.get("/library", response_class=HTMLResponse)
async def library_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    user_data = USERS_DB.get(username, {})
    user_projects = user_data.get("projects", [])
    user_credits = user_data.get("credits", 0)
    
    projects_html = ""
    for p in user_projects:
        title = p.get("title", "Dự án")
        h_tier = p.get("highest_tier", 1)
        projects_html += f"""<div class="bg-slate-950 p-5 rounded-3xl border border-slate-800 flex justify-between items-center gap-3"><div><span class="text-[10px] font-bold bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full border border-amber-500/20">Tien do: Tang {h_tier}</span><h3 class="text-base font-black text-slate-100 mt-2">{title}</h3><p class="text-xs text-slate-400 italic">{p.get("header", "")}</p></div><div class="flex gap-2"><a href="/?load_project={urllib.parse.quote(title)}" class="bg-amber-500 text-slate-950 font-black px-4 py-3 rounded-2xl text-xs uppercase shadow transition">Mo</a><button onclick="confirmDelete('{title}')" class="bg-rose-900/60 hover:bg-rose-700 text-rose-200 px-3 py-3 rounded-2xl text-xs font-bold transition">Xoa</button></div></div>"""


    library_template = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Thu Vien - Cine AI 6.7.6</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-950 text-slate-100 min-h-screen p-4 font-sans"><div class="max-w-4xl mx-auto space-y-4"><div class="flex justify-between items-center bg-slate-900 p-5 rounded-3xl border border-slate-800 shadow-xl"><div><h1 class="text-lg font-bold text-amber-400">Thu Vien Du An</h1><p class="text-xs text-slate-400">Han muc: PROJECT_COUNT_VAL/2 du an - Vi Credit: USER_CREDITS_VAL C</p></div><div class="flex gap-2"><a href="/?new_project=1" class="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black px-4 py-2.5 rounded-2xl text-xs transition shadow-md">Tao Du An Moi</a><a href="/" class="bg-slate-800 text-slate-200 px-4 py-2.5 rounded-2xl text-xs transition">Studio</a></div></div><div class="bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3">PROJECTS_LIST_VAL</div></div><script>async function confirmDelete(title) {if(confirm("Ban co chac chan muon xoa vinh vien du an '" + title + "' khong?")) {const res = await fetch('/api/cineai/delete-project', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:title})});const d = await res.json();alert(d.message);location.reload();}}</script></body></html>"""
    
    library_template = library_template.replace("PROJECT_COUNT_VAL", str(len(user_projects)))
    library_template = library_template.replace("USER_CREDITS_VAL", str(user_credits))
    library_template = library_template.replace("PROJECTS_LIST_VAL", projects_html or "<p class='text-slate-500 text-xs text-center py-6'>Chưa có dự án nào.</p>")
    return HTMLResponse(content=library_template)


@app.get("/login", response_class=HTMLResponse)
async def login_page(tab: str = "login", error: str = None, success: str = None):
    is_reg = (tab == "register")
    is_forgot = (tab == "forgot")
    form_action = "/register" if is_reg else ("/forgot-password" if is_forgot else "/login")
    title_text = "📝 Tạo Tài Khoản Mới" if is_reg else ("🔑 Khôi Phục Mật Khẩu" if is_forgot else "🔐 Đăng Nhập Hệ Thống")
    
    err_html = f'<div class="bg-rose-950/80 border border-rose-800 p-3.5 rounded-2xl text-rose-200 text-xs font-bold text-center">{error}</div>' if error else ''
    succ_html = f'<div class="bg-emerald-950/80 border border-emerald-800 p-3.5 rounded-2xl text-emerald-200 text-xs font-bold text-center">{success}</div>' if success else ''


    login_template = """
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Xác Thực - Cine AI 6.7.6 Enterprise</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4 sm:p-6 font-sans">
        <div class="bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-800 w-full max-w-sm sm:max-w-md space-y-6 shadow-2xl">
            <div class="text-center space-y-1">
                <h2 class="text-xl sm:text-2xl font-black text-amber-400">PAGE_TITLE_VAL</h2>
                <p class="text-xs text-slate-400">Cine AI Studio Pro 6.7.6 Enterprise</p>
            </div>
            ALERT_ERR_VAL ALERT_SUCC_VAL
            <form method="POST" action="FORM_ACTION_VAL" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-1.5">👤 Tên tài khoản:</label>
                    <input type="text" name="username" required placeholder="Nhập tên đăng nhập..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-4 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition shadow-inner">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-1.5">🔑 Mật khẩu:</label>
                    <input type="password" name="password" required placeholder="Nhập mật khẩu..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-4 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition shadow-inner">
                </div>
                <button type="submit" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-4 rounded-2xl text-sm uppercase shadow-xl transition tracking-wider">Xác Nhận</button>
            </form>
            <div class="flex justify-between text-xs text-slate-400 pt-3 border-t border-slate-800">
                <a href="/login" class="hover:underline text-amber-400 font-semibold">Đăng nhập</a>
                <a href="/login?tab=register" class="hover:underline">Đăng ký (+10 C)</a>
                <a href="/login?tab=forgot" class="hover:underline">Quên mật khẩu?</a>
            </div>
        </div>
    </body></html>
    """
    login_template = login_template.replace("PAGE_TITLE_VAL", title_text)
    login_template = login_template.replace("ALERT_ERR_VAL", err_html)
    login_template = login_template.replace("ALERT_SUCC_VAL", succ_html)
    login_template = login_template.replace("FORM_ACTION_VAL", form_action)
    return HTMLResponse(content=login_template)


@app.post("/login")
async def login_post(username: str = Form(...), password: str = Form(...)):
    user_info = USERS_DB.get(username)
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    if (username == "admin" and password == "admin123") or (user_info and user_info.get("password_hash") == pwd_hash):
        session_id = secrets.token_hex(16)
        ACTIVE_SESSIONS[session_id] = username
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(key="session_id", value=session_id)
        return resp
    return RedirectResponse(url="/login?error=" + urllib.parse.quote("⚠️ Sai tên đăng nhập hoặc mật khẩu!"), status_code=303)


@app.post("/register")
async def register_post(username: str = Form(...), password: str = Form(...)):
    if username in USERS_DB:
        return RedirectResponse(url="/login?tab=register&error=" + urllib.parse.quote("⚠️ Tên tài khoản đã tồn tại!"), status_code=303)
    USERS_DB[username] = {"password_hash": hashlib.sha256(password.encode()).hexdigest(), "projects": [], "credits": 10}
    save_users()
    session_id = secrets.token_hex(16)
    ACTIVE_SESSIONS[session_id] = username
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="session_id", value=session_id)
    return resp


@app.post("/forgot-password")
async def forgot_password_post(username: str = Form(...), password: str = Form(...)):
    if username not in USERS_DB:
        return RedirectResponse(url="/login?tab=forgot&error=" + urllib.parse.quote("⚠️ Tên tài khoản không tồn tại!"), status_code=303)
    USERS_DB[username]["password_hash"] = hashlib.sha256(password.encode()).hexdigest()
    save_users()
    return RedirectResponse(url="/login?success=" + urllib.parse.quote("🎉 Đổi mật khẩu thành công! Vui lòng đăng nhập."), status_code=303)


@app.get("/logout")
async def logout(session_id: str = Cookie(None)):
    if session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="session_id")
    return resp


@app.get("/community", response_class=HTMLResponse)
async def community_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content="""
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Cộng Đồng - Cine AI 6.7.6</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-5 font-sans">
        <div class="max-w-4xl mx-auto space-y-4">
            <div class="flex justify-between items-center bg-slate-900 p-5 rounded-3xl border border-slate-800 shadow-xl">
                <h1 class="text-lg font-bold text-amber-400">🌍 Cộng Đồng Phim Public Pro 6.7.6</h1>
                <a href="/" class="bg-amber-500 text-slate-950 font-bold px-4 py-2 rounded-2xl text-xs shadow">⚡ Quay lại Studio</a>
            </div>
            <div class="bg-slate-900 p-6 rounded-3xl border border-slate-800 text-xs text-slate-400 text-center py-10">Bảng tin cộng đồng đang kết nối API mạng xã hội...</div>
        </div>
    </body></html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)