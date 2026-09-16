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


app = FastAPI(title="Cine AI Studio Pro 7.1 - Immortal Tree Enterprise", version="7.1.0")


SUPABASE_URL = os.getenv("SUPABASE_URL", "https://djkxwtkhmjpehgqvhkee.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


ACTIVE_SESSIONS = {}


def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
def get_user_profile_leaf(username):
    if not SUPABASE_KEY: return {"credits": 100, "password_hash": hashlib.sha256("admin123".encode()).hexdigest()}
    url = f"{SUPABASE_URL}/rest/v1/cineai_tree_leaves?username=eq.{username}&project_id=eq.USER_PROFILE&select=payload&order=created_at.desc&limit=1"
    try:
        res = requests.get(url, headers=get_supabase_headers(), timeout=5)
        if res.status_code == 200 and res.json():
            return res.json()[0].get("payload")
    except Exception: pass
    
    default_profile = {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest() if username == "admin" else hashlib.sha256("123456".encode()).hexdigest(),
        "credits": 100 if username == "admin" else 10
    }
    grow_new_leaf(username, "USER_PROFILE", default_profile)
    return default_profile


def save_user_profile_leaf(username, profile_data):
    grow_new_leaf(username, "USER_PROFILE", profile_data)


def get_user_projects(username):
    if not SUPABASE_KEY: return []
    url = f"{SUPABASE_URL}/rest/v1/cineai_tree_leaves?username=eq.{username}&project_id=neq.USER_PROFILE&select=project_id,payload&order=created_at.desc"
    try:
        res = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if res.status_code == 200:
            data = res.json()
            seen_projects = set()
            latest_projects = []
            for leaf in data:
                pid = leaf.get("project_id")
                if pid not in seen_projects:
                    seen_projects.add(pid)
                    payload = leaf.get("payload")
                    if payload and not payload.get("metadata", {}).get("deleted"):
                        latest_projects.append(payload)
            return latest_projects
    except Exception as e: print(f"Lỗi đọc lá: {e}")
    return []


def get_project_latest_leaf(project_id):
    if not SUPABASE_KEY: return None
    url = f"{SUPABASE_URL}/rest/v1/cineai_tree_leaves?project_id=eq.{project_id}&select=payload&order=created_at.desc&limit=1"
    try:
        res = requests.get(url, headers=get_supabase_headers(), timeout=5)
        if res.status_code == 200 and res.json():
            return res.json()[0].get("payload")
    except Exception: pass
    return None


def grow_new_leaf(username, project_id, payload):
    if not SUPABASE_KEY: return False
    url = f"{SUPABASE_URL}/rest/v1/cineai_tree_leaves"
    data = {
        "username": username,
        "project_id": project_id,
        "payload": payload,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        res = requests.post(url, json=data, headers=get_supabase_headers(), timeout=10)
        return res.status_code == 201
    except Exception: return False
def migrate_project_to_tree(p):
    if "metadata" in p: return p
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


def get_gemini_keys():
    raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


from google import genai


def call_gemini_direct(prompt_text):
    keys = get_gemini_keys()
    if not keys: return None, "⚠️ Chưa cấu hình GEMINI_API_KEY trên Render!"
    selected_key = random.choice(keys)
    try:
        client = genai.Client(api_key=selected_key)
        models_to_try = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-3.8-flash"]
        for m in models_to_try:
            try:
                response = client.models.generate_content(model=m, contents=prompt_text)
                if response and response.text: return response.text, m
            except Exception: continue
        return None, "⚠️ Khóa hiện tại đã vượt giới hạn hạn mức."
    except Exception as e:
        return None, f"Lỗi khởi tạo SDK: {str(e)[:120]}"


def get_cloud_cache(cache_key: str):
    if not SUPABASE_KEY: return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_cache?key=eq.{cache_key}&select=value"
        res = requests.get(url, headers=get_supabase_headers(), timeout=5)
        if res.status_code == 200 and res.json(): return res.json()[0].get("value")
    except Exception: pass
    return None


def set_cloud_cache(cache_key: str, value_data):
    if not SUPABASE_KEY: return
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_cache"
        payload = {"key": cache_key, "value": value_data, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        headers = get_supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        requests.post(url, json=payload, headers=headers, timeout=5)
    except Exception: pass


@app.middleware("http")
async def self_healing_global_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        error_trace = str(exc)
        print(f"🔥 [SELF-HEALING CAUGHT EXCEPTION]: {error_trace}")
        return JSONResponse(status_code=500, content={"status": "self_healing_intercepted", "message": "⚠️ Hệ thống đã tự động bắt lỗi Runtime.", "error_details": error_trace})
@app.post("/api/cineai/save-draft")
async def save_project_draft(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    data = await request.json()
    project_id = data.get("id", "").strip()
    new_title = data.get("title", "Dự án mới").strip()
    if not new_title: new_title = "Dự án mới"
    
    if not project_id:
        user_projects = get_user_projects(username)
        if len(user_projects) >= 2: 
            return JSONResponse({"status": "limit_reached", "message": "⚠️ Đã đạt giới hạn 2 dự án thương mại/user!"}, status_code=400)
        
        project_id = secrets.token_hex(6)
        target_tier = int(data.get("tier", 1))
        new_payload = migrate_project_to_tree({
            "id": project_id, "title": new_title, "header": data.get("header", ""),
            "project_raw_story": data.get("story", ""), "aspect_ratio": data.get("aspect_ratio", "16:9"),
            "target_duration": data.get("target_duration", "45p"), "highest_tier": target_tier, "current_tier": target_tier
        })
        grow_new_leaf(username, project_id, new_payload)
        return JSONResponse({"status": "success", "message": f"💾 Đã tạo Cây Dữ Liệu mới '{new_title}'!", "saved_id": project_id, "saved_title": new_title})
    
    target_payload = get_project_latest_leaf(project_id)
    if not target_payload:
        return JSONResponse({"status": "error", "message": "⚠️ Không tìm thấy dự án trên cây!"}, status_code=404)
    
    target_tier = int(data.get("tier", 1))
    target_payload["metadata"]["title"] = new_title
    target_payload["metadata"]["header"] = data.get("header", "").strip()
    target_payload["ideation_core"]["project_raw_story"] = data.get("story", "").strip()
    target_payload["metadata"]["aspect_ratio"] = data.get("aspect_ratio", "16:9")
    target_payload["metadata"]["target_duration"] = data.get("target_duration", "45p")
    target_payload["metadata"]["highest_tier"] = max(target_payload["metadata"].get("highest_tier", 1), target_tier)
    target_payload["metadata"]["current_tier"] = target_tier
    target_payload["metadata"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    grow_new_leaf(username, project_id, target_payload)
    return JSONResponse({"status": "success", "message": f"💾 Đã mọc lá dữ liệu mới cho '{new_title}'!", "saved_id": project_id, "saved_title": new_title})


@app.post("/api/cineai/delete-project")
async def delete_project(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    project_id = data.get("id", "").strip()
    target_payload = get_project_latest_leaf(project_id)
    if not target_payload: return JSONResponse({"status": "error", "message": "⚠️ Không tìm thấy dự án!"}, status_code=404)
    
    target_payload["metadata"]["deleted"] = True
    grow_new_leaf(username, project_id, target_payload)
    return JSONResponse({"status": "success", "message": "🗑️ Đã cô lập cành dự án thành công!"})


@app.post("/api/cineai/audit-script-assets")
async def audit_script_assets(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    project_id = data.get("id", "")
    target_payload = get_project_latest_leaf(project_id)
    if not target_payload: return JSONResponse({"status": "error", "message": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    raw_story = target_payload["ideation_core"].get("project_raw_story", "")
    if not raw_story: return JSONResponse({"status": "error", "message": "⚠️ Kịch bản còn trống!"}, status_code=400)
    
    cache_key = hashlib.md5(raw_story.encode()).hexdigest()
    cached_audit = get_cloud_cache(cache_key)
    if cached_audit:
        target_payload["master_schema"]["assets_audit"] = {"audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data": cached_audit}
        grow_new_leaf(username, project_id, target_payload)
        return JSONResponse({"status": "success", "message": "⚡ Đã nạp Master Schema từ Cloud Cache!", "audit_data": cached_audit})


    system_prompt = (
        "Bạn là Tổng Đạo Diễn Cine AI 7.1 Enterprise. Quét sâu kịch bản theo Master Schema gồm:\n"
        "1. 4 Tầng Lọc: Entities, Locations, Props, Audio Signatures.\n"
        "2. Ma Trận Thời Gian: 'time_jumps_detected', 'temporal_states'.\n"
        "3. Khóa Tiến Trình: 'evolution_lineage'.\n"
        "4. Khóa Phong Cách: 'visual_style_lock'.\n"
        "Trả về DUY NHẤT một JSON:\n"
        '{"time_jumps_detected":["..."],"visual_style_lock":{"color_grading":"...","lens_language":"...","emotional_archetype":"..."},"entities":[{"id":"ENT_01","name":"...","archetype":"...","temporal_states":["..."],"description":"..."}],"locations":[{"id":"LOC_01","name":"...","temporal_states":["..."],"description":"..."}],"props":[{"id":"PROP_01","name":"...","evolution_lineage":["..."],"description":"..."}],"audio_signatures":[{"id":"AUD_01","name":"...","audio_signature":"..."}]}'
    )
    raw_res, err_msg = call_gemini_direct(system_prompt + f"\nKịch bản:\n{raw_story}")
    if not raw_res: return JSONResponse({"status": "error", "message": f"Lỗi AI: {err_msg}"}, status_code=500)
        
    try:
        clean_json = re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE)
        parsed_audit = json.loads(clean_json)
        set_cloud_cache(cache_key, parsed_audit)
        target_payload["master_schema"]["assets_audit"] = {"audited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data": parsed_audit}
        grow_new_leaf(username, project_id, target_payload)
        return JSONResponse({"status": "success", "message": "✅ Trích xuất Master Schema thành công!", "audit_data": parsed_audit})
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Không thể giải mã: {str(e)}"}, status_code=500)


@app.post("/api/cineai/generate-asset-concept-prompt")
async def generate_asset_concept_prompt(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    prompt = f"Bạn là Art Director. Viết 1 visual prompt ngắn gọn (100% tiếng Anh) cho: {data.get('asset_name')}\nMô tả: {data.get('asset_description')}\nGhi chú: {data.get('user_tweak')}\nYêu cầu: Cinematic masterpiece 4K."
    raw_res, err_msg = call_gemini_direct(prompt)
    return JSONResponse({"status": "success", "concept_prompt": raw_res or err_msg})
@app.post("/api/cineai/upload-asset-explicit")
async def upload_asset_explicit(file: UploadFile = File(...), project_id: str = Form(""), session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    try:
        extracted_text = (await file.read()).decode("utf-8", errors="ignore")
        target_payload = get_project_latest_leaf(project_id)
        if target_payload:
            target_payload["ideation_core"]["project_raw_story"] = extracted_text
            target_payload["metadata"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            grow_new_leaf(username, project_id, target_payload)
            return JSONResponse({"status": "success", "message": f"✅ Đã nạp kịch bản từ tệp '{file.filename}'!", "extracted_content": extracted_text})
        return JSONResponse({"status": "error", "message": "Không tìm thấy dự án."}, status_code=404)
    except Exception as e: return JSONResponse({"status": "error", "message": f"Lỗi: {str(e)}"}, status_code=500)


@app.post("/api/cineai/upload-visual-token")
async def upload_visual_token(file: UploadFile = File(...), token_category: str = Form("character"), token_name: str = Form(""), project_id: str = Form(""), session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    token_id = f"TOKEN_{token_category.upper()}_{secrets.token_hex(3).upper()}"
    mock_url = f"https://cdn.cineai.studio/tokens/{username}/{project_id}/{file.filename}"
    target_payload = get_project_latest_leaf(project_id)
    if target_payload:
        target_payload["master_schema"]["token_registry"]["visual_tokens"].append({"token_id": token_id, "category": token_category, "name": token_name or file.filename, "file_url": mock_url, "file_name": file.filename})
        target_payload["metadata"]["highest_tier"] = max(target_payload["metadata"].get("highest_tier", 1), 2)
        grow_new_leaf(username, project_id, target_payload)
        return JSONResponse({"status": "success", "message": f"🖼️ Khóa ảnh thành công [{token_id}]!", "token_id": token_id})
    return JSONResponse({"status": "error", "message": "Lỗi định danh dự án"}, status_code=400)


@app.post("/api/cineai/upload-audio-token")
async def upload_audio_token(file: UploadFile = File(...), token_category: str = Form("bgm"), token_name: str = Form(""), project_id: str = Form(""), session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    token_id = f"TOKEN_AUD_{token_category.upper()}_{secrets.token_hex(3).upper()}"
    mock_url = f"https://cdn.cineai.studio/audio/{username}/{project_id}/{file.filename}"
    target_payload = get_project_latest_leaf(project_id)
    if target_payload:
        target_payload["master_schema"]["token_registry"]["audio_tokens"].append({"token_id": token_id, "category": token_category, "name": token_name or file.filename, "file_url": mock_url, "file_name": file.filename})
        target_payload["metadata"]["highest_tier"] = max(target_payload["metadata"].get("highest_tier", 1), 2)
        grow_new_leaf(username, project_id, target_payload)
        return JSONResponse({"status": "success", "message": f"🎵 Khóa âm thanh thành công [{token_id}]!", "token_id": token_id})
    return JSONResponse({"status": "error", "message": "Lỗi định danh dự án"}, status_code=400)


@app.post("/api/cineai/chat")
async def chat_with_director(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"reply": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    user_message, project_id, tier = data.get("message", ""), data.get("id", ""), int(data.get("tier", 1))
    if not user_message: return JSONResponse({"reply": "Vui lòng nhập nội dung!"})
    
    if tier == 1:
        target_payload = get_project_latest_leaf(project_id)
        current_slots = target_payload["ideation_core"].get("ideation_slots", {}) if target_payload else {}
        system_persona = (
            "Bạn là Đạo diễn ảo thấu cảm Cine AI 7.1.\n"
            "Nhiệm vụ: Trích xuất ATMOSPHERE, CORE_WOUND, TRIGGER_PROP, DILEMMA, CATHARSIS.\n"
            f"Slots hiện có: {json.dumps(current_slots, ensure_ascii=False)}\n"
            'Trả về JSON: {"message": "...", "extracted_slots": {"...": "..."}, "quick_chips": ["...", "...", "..."], "is_ready_for_script": true}'
        )
        raw_res, err_msg = call_gemini_direct(system_persona + f"\nUser: {user_message}")
        if raw_res:
            try:
                parsed = json.loads(re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE))
                if target_payload and parsed.get("extracted_slots"):
                    target_payload["ideation_core"]["ideation_slots"].update(parsed["extracted_slots"])
                    grow_new_leaf(username, project_id, target_payload)
                return JSONResponse({"reply": parsed.get("message", ""), "chips": parsed.get("quick_chips", []), "ready": True})
            except Exception: pass
        return JSONResponse({"reply": raw_res or err_msg, "chips": [], "ready": True})


    mode_instructions = {2: "Khóa mẫu Thực thể", 3: "Dựng cảnh 3 Hồi", 4: "Render toàn tập"}
    reply_text, err_msg = call_gemini_direct(f"Bạn là Đạo diễn ảo 7.1. Trạng thái: {mode_instructions.get(tier, '')}.\nUser: {user_message}")
    return JSONResponse({"reply": reply_text or err_msg, "chips": []})


@app.post("/api/cineai/generate-script-from-slots")
async def generate_script_from_slots(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    data = await request.json()
    project_id, aspect_ratio, target_duration = data.get("id", ""), data.get("aspect_ratio", "16:9"), data.get("target_duration", "45p")
    target_payload = get_project_latest_leaf(project_id)
    slots_text = json.dumps(target_payload["ideation_core"].get("ideation_slots", {}), ensure_ascii=False) if target_payload else "Tự do sáng tạo."
    
    prompt = (
        "Nhà biên kịch điện ảnh Cine AI 7.1. Dựa vào Soul Fingerprint:\n"
        f"{slots_text}\nĐịnh dạng: {aspect_ratio}, Thời lượng: {target_duration}.\n"
        'Trả về JSON: {"title": "...", "header": "...", "story": "Kịch bản 3 hồi..."}'
    )
    raw_res, err = call_gemini_direct(prompt)
    if not raw_res: return JSONResponse({"status": "error", "message": f"⚠️ {err}"}, status_code=500)
    try:
        res_data = json.loads(re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE))
        if target_payload:
            target_payload["metadata"]["title"] = res_data.get("title", "Dự án mới")
            target_payload["metadata"]["header"] = res_data.get("header", "")
            target_payload["ideation_core"]["project_raw_story"] = res_data.get("story", "")
            grow_new_leaf(username, project_id, target_payload)
        return JSONResponse({"status": "success", "data": res_data})
    except Exception as e: return JSONResponse({"status": "error", "message": "Lỗi phân giải kịch bản."}, status_code=500)


@app.post("/api/cineai/breakdown-scenes-enterprise")
async def breakdown_scenes_enterprise(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"message": "⚠️ Hết hạn!"}, status_code=401)
    data = await request.json()
    project_id = data.get("id", "")
    target_payload = get_project_latest_leaf(project_id)
    raw_story = target_payload["ideation_core"].get("project_raw_story", "") if target_payload else ""
    if not raw_story: return JSONResponse({"reply": "⚠️ Kịch bản trống!"}, status_code=400)
    
    raw_res, _ = call_gemini_direct(f"Phân tích kịch bản thành Scene 30s-150s, 3 Hồi. Trả về JSON chuẩn:\n{raw_story}")
    parsed_scenes = {"acts": [{"act_name": "Act I", "scenes": [{"scene_id": 1, "title": "Cảnh 1", "duration_sec": 60, "summary": "N/A"}]}]}
    if raw_res:
        try: parsed_scenes = json.loads(re.sub(r"^```json\s*|\s*```$", "", raw_res.strip(), flags=re.IGNORECASE))
        except Exception: pass


    total_dur, act_durs = 0, {}
    if "acts" in parsed_scenes:
        for act in parsed_scenes["acts"]:
            act_name = act.get("act_name", "Act I")
            for sc in act.get("scenes", []):
                dur = sc.get("duration_sec", 60)
                total_dur += dur
                act_durs[act_name] = act_durs.get(act_name, 0) + dur


    structured_data = {
        "schema_version": "7.1-Enterprise", "pacing_metrics": {"total_duration_sec": total_dur, "act_breakdown": act_durs},
        "scenes_data": parsed_scenes, "alternate_takes": {}, "active_takes": {}, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if target_payload:
        target_payload["master_schema"]["scene_breakdown_enterprise"] = structured_data
        target_payload["metadata"]["highest_tier"] = max(target_payload["metadata"].get("highest_tier", 1), 3)
        grow_new_leaf(username, project_id, target_payload)
    return JSONResponse({"status": "success", "message": "🌟 Đã dựng cảnh Enterprise!", "metrics": structured_data["pacing_metrics"], "data": parsed_scenes})


async def async_render_background_worker(username, project_id, scene_id):
    target_payload = get_project_latest_leaf(project_id)
    if target_payload:
        enterprise_data = target_payload["master_schema"].setdefault("scene_breakdown_enterprise", {})
        alternate_takes = enterprise_data.setdefault("alternate_takes", {})
        scene_key = f"scene_{scene_id}"
        current_takes = alternate_takes.setdefault(scene_key, [])
        new_take_id = len(current_takes) + 1
        
        current_takes.append({
            "take_id": new_take_id, "status": "rendered_success_async",
            "media_url": f"https://cdn.cineai.studio/renders/{project_id}_s{scene_id}_take{new_take_id}.mp4",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        target_payload["metadata"]["highest_tier"] = max(target_payload["metadata"].get("highest_tier", 1), 4)
        grow_new_leaf(username, project_id, target_payload)


@app.post("/api/cineai/render-scene-take")
async def render_scene_take(request: Request, background_tasks: BackgroundTasks, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    profile = get_user_profile_leaf(username)
    current_credits = profile.get("credits", 10)
    render_cost = 5
    if current_credits < render_cost:
        return JSONResponse({"status": "payment_required", "message": "⚠️ Số dư Credit không đủ!"}, status_code=402)
    
    data = await request.json()
    project_id, scene_id = data.get("id", ""), data.get("scene_id", 1)
    
    profile["credits"] = current_credits - render_cost
    save_user_profile_leaf(username, profile)
    
    background_tasks.add_task(async_render_background_worker, username, project_id, scene_id)
    return JSONResponse({"status": "success", "message": f"🎬 Đã đưa Phân cảnh {scene_id} vào Render Queue!", "remaining_credits": profile["credits"]})


@app.post("/api/cineai/set-active-take")
async def set_active_take(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"message": "⚠️ Hết hạn!"}, status_code=401)
    data = await request.json()
    project_id, scene_id, selected_take_id = data.get("id", ""), data.get("scene_id", 1), data.get("take_id", 1)
    target_payload = get_project_latest_leaf(project_id)
    if not target_payload: return JSONResponse({"reply": "⚠️ Lỗi dự án!"}, status_code=404)
        
    enterprise_data = target_payload["master_schema"].setdefault("scene_breakdown_enterprise", {})
    enterprise_data.setdefault("active_takes", {})[f"scene_{scene_id}"] = selected_take_id
    grow_new_leaf(username, project_id, target_payload)
    return JSONResponse({"status": "success", "message": "🎯 Đã chọn Take chính thức!"})


@app.get("/api/cineai/get-rough-cut")
async def get_rough_cut(id: str = "", session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"message": "⚠️ Hết hạn!"}, status_code=401)
    target_payload = get_project_latest_leaf(id)
    if not target_payload: return JSONResponse({"reply": "Lỗi dự án!"}, status_code=404)
        
    enterprise_data = target_payload["master_schema"].get("scene_breakdown_enterprise", {})
    scenes_json, active_takes, alternate_takes = enterprise_data.get("scenes_data", {}), enterprise_data.get("active_takes", {}), enterprise_data.get("alternate_takes", {})
    rough_cut_timeline, total_duration = [], 0
    
    if "acts" in scenes_json:
        for act in scenes_json["acts"]:
            act_name = act.get("act_name", "Act I")
            for sc in act.get("scenes", []):
                s_id, dur = sc.get("scene_id"), sc.get("duration_sec", 60)
                s_key, chosen_take_id = f"scene_{s_id}", active_takes.get(f"scene_{s_id}", 1)
                take_info = next((t for t in alternate_takes.get(s_key, []) if t.get("take_id") == chosen_take_id), None)
                rough_cut_timeline.append({
                    "act": act_name, "scene_id": s_id, "title": sc.get("title"),
                    "duration_sec": dur, "active_take_id": chosen_take_id, "media_url": take_info.get("media_url") if take_info else "Chưa render"
                })
                total_duration += dur
                
    target_payload["post_production"]["rough_cut_playlist"] = rough_cut_timeline
    grow_new_leaf(username, id, target_payload)
    return JSONResponse({"status": "success", "total_timeline_duration_sec": total_duration, "rough_cut_playlist": rough_cut_timeline})


@app.get("/api/cineai/export-srt")
async def export_srt_subtitles(id: str = "", session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return JSONResponse({"message": "⚠️ Hết hạn!"}, status_code=401)
    target_payload = get_project_latest_leaf(id)
    if not target_payload: return JSONResponse({"reply": "Lỗi dự án!"}, status_code=404)
        
    scenes_json = target_payload["master_schema"].get("scene_breakdown_enterprise", {}).get("scenes_data", {})
    srt_content, current_time, idx = "", 0.0, 1
    def format_time(sec): return f"{int(sec//3600):02d}:{int((sec%3600)//60):02d}:{int(sec%60):02d},{int((sec-int(sec))*1000):03d}"
    if "acts" in scenes_json:
        for act in scenes_json["acts"]:
            for sc in act.get("scenes", []):
                dur = float(sc.get("duration_sec", 60))
                srt_content += f"{idx}\n{format_time(current_time)} --> {format_time(current_time + dur)}\n[Lip-Sync] {sc.get('summary', '')}\n\n"
                current_time += dur
                idx += 1
    target_payload["post_production"]["subtitles_srt"] = srt_content
    grow_new_leaf(username, id, target_payload)
    return JSONResponse({"status": "success", "srt_format": srt_content})


@app.post("/api/payments/webhook")
async def sepay_payment_webhook(request: Request):
    try:
        data = await request.json()
        content, transfer_amount = data.get("content", ""), int(data.get("transferAmount", 0))
        match = re.search(r"NAPCREDIT\s+([a-zA-Z0-9_-]+)", content, re.IGNORECASE)
        if match:
            target_username = match.group(1)
            profile = get_user_profile_leaf(target_username)
            if profile:
                credits_to_add = int(transfer_amount / 1000)
                profile["credits"] = profile.get("credits", 0) + credits_to_add
                save_user_profile_leaf(target_username, profile)
                return JSONResponse({"success": True, "message": f"Cộng {credits_to_add} C cho {target_username}"})
        return JSONResponse({"success": False, "message": "Sai cú pháp"})
    except Exception as e: return JSONResponse({"success": False, "error": str(e)}, status_code=400)
def get_studio_html(target_project, user_credits, active_tier, highest_tier, username):
    p_id = target_project.get("id", "") if target_project else ""
    p_title = target_project["metadata"]["title"] if target_project else "Dự án mới"
    p_header = target_project["metadata"]["header"] if target_project else ""
    p_story = target_project["ideation_core"]["project_raw_story"] if target_project else ""


    def gtc(idx): return "bg-amber-500 text-slate-950 pointer-events-none" if idx == active_tier else ("bg-slate-800 text-slate-200 hover:bg-slate-700" if idx <= highest_tier else "bg-slate-950 text-slate-600 pointer-events-none opacity-40")
    t1_cls, t2_cls, t3_cls, t4_cls = gtc(1), gtc(2), gtc(3), gtc(4)
    t1_vis, t2_vis, t3_vis, t4_vis = ("block" if active_tier==1 else "hidden"), ("block" if active_tier==2 else "hidden"), ("block" if active_tier==3 else "hidden"), ("block" if active_tier==4 else "hidden")
    
    tokens_html = ""
    if target_project:
        for vt in target_project["master_schema"]["token_registry"].get("visual_tokens", []): tokens_html += f'<span class="bg-indigo-950 border border-indigo-800 text-indigo-300 text-[10px] px-2 py-0.5 rounded-full font-bold">🖼️ {vt.get("token_id")}</span> '
        for at in target_project["master_schema"]["token_registry"].get("audio_tokens", []): tokens_html += f'<span class="bg-emerald-950 border border-emerald-800 text-emerald-300 text-[10px] px-2 py-0.5 rounded-full font-bold">🎵 {at.get("token_id")}</span> '


    tmpl = f"""
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cine AI Studio Pro 7.1 Immortal Tree</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-3 sm:p-5 font-sans pb-24">
        <div class="max-w-4xl mx-auto space-y-3">
            <div class="flex justify-between items-center bg-slate-900/90 backdrop-blur-md p-3.5 rounded-2xl border border-slate-800 shadow-xl relative">
                <div class="flex items-center gap-2"><span class="text-xl">🎬</span><h1 class="text-sm sm:text-base font-black text-amber-400 uppercase">Cine AI Studio Pro 7.1</h1></div>
                <div class="relative"><button onclick="document.getElementById('profile-dropdown').classList.toggle('hidden')" class="w-9 h-9 rounded-full bg-slate-800 border-2 border-amber-400 flex items-center justify-center hover:bg-slate-700">👤</button>
                    <div id="profile-dropdown" class="hidden absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-800 rounded-2xl p-3 shadow-2xl z-50">
                        <p class="text-xs font-bold text-slate-200">{username}</p>
                        <p class="text-[11px] text-emerald-400 font-bold mb-2">💰 Số dư: {user_credits} Credit</p>
                        <button onclick="document.getElementById('topup-modal').classList.remove('hidden'); document.getElementById('profile-dropdown').classList.add('hidden');" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-2 rounded-xl text-xs mb-2">💳 Nạp Thêm Credit</button>
                        <a href="/logout" class="block w-full text-center bg-rose-950 hover:bg-rose-900 text-rose-200 py-1.5 rounded-xl text-xs font-bold">Đăng Xuất</a>
                    </div>
                </div>
            </div>


            <div class="bg-slate-900/90 border border-amber-500/30 p-3 rounded-2xl flex justify-between shadow-lg items-center">
                <div class="flex items-center gap-2"><span class="text-amber-400 text-xs">🎞️ Dự án hiện hành:</span><span id="global-project-title-display" class="text-amber-300 font-black text-xs truncate max-w-[150px]">{p_title}</span></div>
                <span class="text-[10px] bg-amber-500/10 text-amber-400 px-2.5 py-1 rounded-full font-bold border border-amber-500/20">Tầng {active_tier}</span>
            </div>


            <div class="grid grid-cols-3 gap-2 text-center text-xs font-bold">
                <a href="/?new_project=1" class="bg-amber-500 text-slate-950 py-2 rounded-xl flex items-center justify-center">➕ Dự Án Mới</a>
                <a href="/library" class="bg-slate-900 border border-slate-800 text-slate-200 py-2 rounded-xl flex items-center justify-center">📁 Thư Viện</a>
                <button onclick="openDrawer('chat')" class="bg-indigo-600 text-white py-2 rounded-xl flex items-center justify-center">🤖 Trợ Lý Ảo</button>
            </div>


            <div class="grid grid-cols-4 gap-1.5 bg-slate-900 p-1.5 rounded-2xl border border-slate-800 text-center text-[10px] font-bold mt-3">
                <a href="/?load_id={p_id}&tier=1" class="py-2 rounded-xl {t1_cls}">1. Kịch Bản</a>
                <a href="/?load_id={p_id}&tier=2" class="py-2 rounded-xl {t2_cls}">2. Casting & Đạo cụ</a>
                <a href="/?load_id={p_id}&tier=3" class="py-2 rounded-xl {t3_cls}">3. Dựng cảnh</a>
                <a href="/?load_id={p_id}&tier=4" class="py-2 rounded-xl {t4_cls}">4. Render</a>
            </div>
            <!-- MÀN HÌNH TẦNG 1 -->
            <div id="screen-tier-1" class="{t1_vis} space-y-3 mt-3">
                <div class="grid grid-cols-2 gap-2">
                    <button onclick="openDrawer('script')" class="bg-slate-900 border border-slate-700 p-3.5 rounded-2xl text-left shadow"><span class="text-xs font-black text-slate-100">📜 Câu chuyện của bạn</span><span class="text-[10px] text-slate-400 block">Mở chỉnh sửa kịch bản</span></button>
                    <button onclick="openDrawer('chat')" class="bg-indigo-950/40 border border-indigo-800/60 p-3.5 rounded-2xl text-left shadow"><span class="text-xs font-black text-indigo-200">✨ Ươm mầm ý tưởng</span><span class="text-[10px] text-indigo-400 block">Đạo diễn ảo AI</span></button>
                </div>
                <div class="bg-slate-900 p-4 rounded-3xl border border-slate-800 text-center"><h2 class="text-xs font-bold text-amber-400">📽️ Tầng 1: Không Gian Kịch Bản</h2><p class="text-[11px] text-slate-400 mt-2">Chạm vào các thẻ ở phía trên để thao tác.</p></div>
            </div>


            <!-- DRAWER SCRIPT -->
            <div id="drawer-script" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 hidden flex flex-col justify-end p-2 sm:p-4">
                <div class="bg-slate-900 border border-slate-700 rounded-3xl p-4 max-h-[85vh] overflow-y-auto space-y-3">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2"><h3 class="text-xs font-bold text-amber-400">📜 Kịch Bản</h3><button onclick="closeDrawer('script')" class="text-slate-300 font-bold">✕</button></div>
                    <label class="block text-[11px] font-semibold text-slate-400 mb-1">Tên Dự Án Phim:</label>
                    <input type="text" id="project-title" value="{p_title}" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-amber-300 font-bold">
                    <label class="block text-[11px] font-semibold text-slate-400 mb-1">Đề Mục / Logline:</label>
                    <input type="text" id="project-header" value="{p_header}" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200">
                    <div class="flex gap-2 items-center mt-2"><input type="file" id="file-story" accept=".txt,.md" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-1.5 text-xs"><button onclick="uploadStoryFile()" class="bg-blue-600 text-white px-3 py-2 rounded-xl text-xs font-bold">Nạp File</button></div>
                    <textarea id="project-story" rows="8" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200 mt-2">{p_story}</textarea>
                    <button onclick="saveAndCloseScriptDrawer()" class="w-full bg-amber-500 text-slate-950 font-black py-3 rounded-xl text-xs mt-2">💾 Lưu Lại & Thu Gọn</button>
                </div>
            </div>


            <!-- DRAWER CHAT -->
            <div id="drawer-chat" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 hidden flex flex-col justify-end p-2 sm:p-4">
                <div class="bg-slate-900 border border-slate-700 rounded-3xl p-4 max-h-[85vh] overflow-y-auto space-y-3">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span class="text-xs font-bold text-amber-400">✨ Ươm Mầm Ý Tưởng</span>
                        <div>
                            <button onclick="autoGenerateScriptFromSlots()" class="bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 font-black px-2 py-1 rounded-xl text-[10px] mr-2">🪄 Sinh Kịch Bản</button>
                            <button onclick="closeDrawer('chat')" class="text-slate-300 font-bold">✕</button>
                        </div>
                    </div>
                    <div id="chat-box" class="bg-slate-950 h-52 rounded-2xl p-3 overflow-y-auto text-xs text-slate-300 border border-slate-800 space-y-2"><p class="text-blue-200">Chào bạn! Đạo diễn ảo 7.1 đã sẵn sàng.</p></div>
                    <div class="flex gap-2 pt-1"><input type="text" id="chat-input" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl p-2 text-xs text-slate-100" placeholder="Trò chuyện..." onkeypress="if(event.key==='Enter') sendChat()"><button onclick="sendChat()" class="bg-indigo-600 text-white px-4 py-2 rounded-xl text-xs font-bold">Gửi</button></div>
                </div>
            </div>


            <!-- TẦNG 2 -->
            <div id="screen-tier-2" class="{t2_vis} bg-slate-900 p-4 rounded-3xl border border-slate-800 space-y-3 shadow-xl mt-3">
                <div class="flex justify-between items-center border-b border-slate-800 pb-2.5">
                    <div><h2 class="text-xs font-bold text-amber-400">🎨 Tầng 2: Casting & Đạo Cụ</h2><p class="text-[10px] text-slate-400">Khóa mẫu thực thể.</p></div>
                    <button onclick="runAuditAssets()" class="bg-indigo-600 text-white font-bold px-3 py-1.5 rounded-xl text-[11px] shadow">🔍 Quét Kịch Bản</button>
                </div>
                <div id="audit-checklist-tray" class="space-y-2 max-h-72 overflow-y-auto"><div class="text-center py-6 text-slate-500 text-xs">Bấm nút "🔍 Quét Kịch Bản" để AI trích xuất Casting và Đạo cụ!</div></div>
                <div class="p-2.5 bg-slate-950/80 rounded-2xl border border-slate-800"><span class="text-[10px] font-bold text-slate-400 block uppercase mb-1">Kho Token Đã Khóa:</span><div id="tokens-tray" class="flex flex-wrap gap-1.5">{tokens_html or "<p class='text-slate-500 text-[11px] italic'>Chưa có token nào.</p>"}</div></div>
            </div>


            <!-- TẦNG 3 -->
            <div id="screen-tier-3" class="{t3_vis} bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl mt-3">
                <h2 class="text-xs font-bold text-amber-400">🎬 Tầng 3: Dựng Cảnh & Chia Nhịp</h2>
                <button onclick="runBreakdown()" class="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold py-3 rounded-2xl text-xs shadow-lg">🚀 Kích Hoạt AI Dựng Cảnh</button>
                <div id="breakdown-result" class="bg-slate-950 p-3 rounded-2xl border border-slate-800 text-xs text-slate-300 max-h-40 overflow-y-auto">Chưa dựng cảnh. Bấm kích hoạt phía trên.</div>
            </div>


            <!-- TẦNG 4 -->
            <div id="screen-tier-4" class="{t4_vis} bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3 shadow-xl mt-3">
                <h2 class="text-xs font-bold text-amber-400">🎞️ Tầng 4: Phòng Dựng & Render</h2>
                <button onclick="renderScene(1)" class="w-full bg-emerald-600 text-slate-950 font-black py-3 rounded-2xl text-xs shadow">🎬 Gửi Render Scene (VEO 4K)</button>
                <button onclick="fetchTimeline()" class="w-full bg-slate-800 text-white font-bold py-2.5 rounded-2xl text-xs">🎞️ Xem Timeline Rough-Cut</button>
                <button onclick="exportSrtSubtitles()" class="w-full bg-indigo-600 text-white font-bold py-2.5 rounded-2xl text-xs">📜 Xuất Phụ Đề .SRT</button>
            </div>
        </div>


        <!-- MODAL NẠP CREDIT -->
        <div id="topup-modal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 hidden">
            <div class="bg-slate-900 border border-slate-800 p-5 rounded-3xl max-w-md w-full space-y-4 shadow-2xl text-slate-100">
                <div class="flex justify-between items-center border-b border-slate-800 pb-3"><h3 class="text-sm font-bold text-amber-400 uppercase">💳 Nạp Credit Vào Ví Sáng Tạo</h3><button onclick="document.getElementById('topup-modal').classList.add('hidden')" class="text-slate-400 font-bold">✕</button></div>
                <div class="space-y-2.5 text-xs text-slate-300">
                    <p class="font-semibold">Cổng Nội Địa (SePay & VietQR):</p>
                    <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800">Chuyển khoản tự động. Cú pháp: <code class="text-amber-400">NAPCREDIT {username}</code> (1.000đ = 1 Credit).</div>
                </div>
            </div>
        </div>


        <!-- FIXED FOOTER -->
        <div class="fixed bottom-0 left-0 right-0 bg-slate-900/95 p-3 z-40 border-t border-slate-800">
            <div class="max-w-4xl mx-auto flex gap-2">
                <button onclick="saveDraftCurrent({active_tier})" class="w-1/3 bg-slate-800 text-slate-200 font-bold py-3.5 rounded-2xl text-xs">💾 Lưu Thay Đổi</button>
                <button onclick="proceedToTier({active_tier} + 1)" class="w-2/3 bg-amber-500 text-slate-950 font-black py-3.5 rounded-2xl text-xs">TIẾP THEO ➔</button>
            </div>
        </div>
    """
    return tmpl
def get_studio_javascript(project_id, active_tier):
    return f"""
        <script>
            let currentActiveTier = {active_tier};
            let currentProjectId = "{project_id}";


            function openDrawer(type) {{ document.getElementById('drawer-' + type)?.classList.remove('hidden'); }}
            function closeDrawer(type) {{ document.getElementById('drawer-' + type)?.classList.add('hidden'); }}
            
            async function saveAndCloseScriptDrawer() {{ await saveDraftCurrent(currentActiveTier); closeDrawer('script'); }}


            async function saveDraftCurrent(tier) {{
                const payload = {{
                    id: currentProjectId || "",
                    title: document.getElementById('project-title')?.value.trim() || "Dự án mới",
                    header: document.getElementById('project-header')?.value || "",
                    story: document.getElementById('project-story')?.value || "",
                    aspect_ratio: "16:9",
                    target_duration: "45p",
                    tier: tier
                }};
                try {{
                    const res = await fetch('/api/cineai/save-draft', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload) }});
                    const data = await res.json();
                    if(data.status === 'success') {{
                        currentProjectId = data.saved_id;
                        document.getElementById('global-project-title-display').innerText = data.saved_title;
                        alert(data.message);
                    }} else alert(data.message);
                }} catch(e) {{ alert('⚠️ Lỗi kết nối khi lưu!'); }}
            }}


            async function proceedToTier(targetTier) {{
                if (targetTier > 4) targetTier = 4;
                await saveDraftCurrent(targetTier);
                window.location.href = '/?load_id=' + encodeURIComponent(currentProjectId) + '&tier=' + targetTier;
            }}


            async function uploadStoryFile() {{
                const fileInput = document.getElementById('file-story');
                if(!fileInput || fileInput.files.length === 0) return alert('⚠️ Vui lòng chọn tệp (.txt, .md)!');
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('project_id', currentProjectId);
                try {{
                    const res = await fetch('/api/cineai/upload-asset-explicit', {{method: 'POST', body: formData}});
                    const data = await res.json();
                    if(data.status === 'success') {{
                        document.getElementById('project-story').value = data.extracted_content;
                        alert(data.message);
                        saveDraftCurrent(1);
                    }} else alert(data.message);
                }} catch(e) {{ alert('Lỗi nạp tệp kịch bản!'); }}
            }}


            async function sendChat() {{
                const input = document.getElementById('chat-input');
                const box = document.getElementById('chat-box');
                const text = input.value.trim();
                if(!text) return;
                box.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-2.5 rounded-xl inline-block text-slate-100 max-w-[85%] text-left">' + text + '</span></div>';
                input.value = ''; box.scrollTop = box.scrollHeight;
                try {{
                    const res = await fetch('/api/cineai/chat', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{message: text, id: currentProjectId, tier: currentActiveTier}}) }});
                    const data = await res.json();
                    box.innerHTML += '<div class="bg-blue-950/60 p-3 rounded-xl text-blue-200 mt-2 max-w-[85%]" style="overflow-wrap:anywhere;">' + (data.reply || "Tiếp nhận.") + '</div>';
                    box.scrollTop = box.scrollHeight;
                }} catch(e) {{ box.innerHTML += '<div class="text-rose-400 mt-2">Lỗi AI!</div>'; }}
            }}


            async function autoGenerateScriptFromSlots() {{
                const box = document.getElementById('chat-box');
                box.innerHTML += '<div class="text-amber-300 font-bold mt-2">🪄 Đang phù phép kịch bản...</div>';
                try {{
                    const res = await fetch('/api/cineai/generate-script-from-slots', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{id: currentProjectId}}) }});
                    const data = await res.json();
                    if(data.status === 'success') {{
                        document.getElementById('project-title').value = data.data.title;
                        document.getElementById('project-header').value = data.data.header;
                        document.getElementById('project-story').value = data.data.story;
                        await saveDraftCurrent(currentActiveTier);
                        closeDrawer('chat'); openDrawer('script');
                        alert('🎉 Kịch bản đã được khởi tạo!');
                    }} else alert(data.message);
                }} catch(e) {{ alert('Lỗi tạo kịch bản!'); }}
            }}
            async function runAuditAssets() {{
                const tray = document.getElementById('audit-checklist-tray');
                tray.innerHTML = "<div class='text-center py-4 text-amber-400 text-xs animate-pulse'>⏳ Đang quét Master Schema...</div>";
                try {{
                    const res = await fetch('/api/cineai/audit-script-assets', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{id: currentProjectId}}) }});
                    const d = await res.json();
                    if(d.status === 'success') renderAuditChecklist(d.audit_data);
                    else tray.innerHTML = `<div class='text-rose-400 text-xs text-center'>${{d.message}}</div>`;
                }} catch(e) {{ tray.innerHTML = "<div class='text-rose-400 text-xs text-center'>⚠️ Lỗi kết nối kiểm kê!</div>"; }}
            }}


            function renderAuditChecklist(audit) {{
                let html = '';
                const renderCard = (item, catLabel, catType) => `
                    <div class="bg-slate-950 p-3 rounded-2xl border border-slate-800 space-y-2 mt-2">
                        <span class="text-[10px] font-bold bg-indigo-950 text-indigo-300 px-2 py-0.5 rounded-md">${{catLabel}}</span>
                        <h4 class="text-xs font-black text-slate-100">${{item.name}}</h4>
                        <p class="text-[11px] text-slate-400 leading-tight">${{item.description || item.audio_signature || ''}}</p>
                        <div class="flex gap-1.5 pt-1">
                            <label class="flex-1 bg-slate-800 text-slate-200 text-center py-1.5 rounded-xl text-[10px] font-bold cursor-pointer">📁 Tải Lên<input type="file" class="hidden" onchange="uploadDirectAsset(this, '${{catType}}', '${{item.name}}')"></label>
                            <button onclick="requestConcept('${{item.name}}')" class="flex-1 bg-amber-500/20 text-amber-400 py-1.5 rounded-xl text-[10px] font-bold border border-amber-500/30">✨ AI Concept</button>
                        </div>
                    </div>`;
                (audit.entities || []).forEach(e => html += renderCard(e, e.archetype || 'Thực thể', 'character'));
                (audit.locations || []).forEach(l => html += renderCard(l, 'Bối cảnh', 'landscape'));
                (audit.props || []).forEach(p => html += renderCard(p, 'Đạo cụ', 'costume'));
                (audit.audio_signatures || []).forEach(a => html += renderCard(a, 'Âm thanh 3D', 'bgm'));
                document.getElementById('audit-checklist-tray').innerHTML = html || "<div class='text-slate-500 text-xs text-center py-4'>Không phát hiện Token.</div>";
            }}


            async function uploadDirectAsset(inputElement, category, assetName) {{
                if(!inputElement.files || inputElement.files.length === 0) return;
                const file = inputElement.files[0];
                const endpoint = (category === 'bgm' || category === 'voice') ? '/api/cineai/upload-audio-token' : '/api/cineai/upload-visual-token';
                const formData = new FormData();
                formData.append('file', file); formData.append('token_category', category);
                formData.append('token_name', assetName); formData.append('project_id', currentProjectId);
                try {{
                    const res = await fetch(endpoint, {{method: 'POST', body: formData}});
                    const d = await res.json();
                    alert(d.message); if(d.status === 'success') location.reload();
                }} catch(e) {{ alert('Lỗi nạp tệp khóa token!'); }}
            }}


            async function requestConcept(name) {{
                const tweak = prompt("Ghi chú bổ sung (VD: 4K Cinematic):", "");
                if (tweak === null) return;
                try {{
                    const res = await fetch('/api/cineai/generate-asset-concept-prompt', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{asset_name: name, asset_description: "", user_tweak: tweak}}) }});
                    const d = await res.json();
                    alert("🎨 Visual Prompt:\\n\\n" + d.concept_prompt);
                }} catch(e) {{ alert('Lỗi tạo concept!'); }}
            }}


            async function runBreakdown() {{
                const box = document.getElementById('breakdown-result');
                box.innerHTML = "⏳ Đang gọi AI dựng cảnh 3 Hồi...";
                try {{
                    const res = await fetch('/api/cineai/breakdown-scenes-enterprise', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{id: currentProjectId}}) }});
                    const data = await res.json();
                    if(data.status === 'success') box.innerHTML = "✅ Dựng cảnh thành công! Tổng thời lượng: " + data.metrics.total_duration_sec + " giây.<br><pre class='text-[10px] text-slate-400 mt-2 whitespace-pre-wrap'>" + JSON.stringify(data.data, null, 2) + "</pre>";
                    else box.innerHTML = data.message || "Lỗi dựng cảnh.";
                }} catch(e) {{ box.innerHTML = "Lỗi kết nối AI Dựng cảnh!"; }}
            }}


            async function renderScene(id) {{
                try {{
                    const res = await fetch('/api/cineai/render-scene-take', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{id: currentProjectId, scene_id: id}}) }});
                    const data = await res.json(); alert(data.message);
                }} catch(e) {{ alert("Lỗi gửi lệnh Render!"); }}
            }}


            async function fetchTimeline() {{
                try {{
                    const res = await fetch('/api/cineai/get-rough-cut?id=' + encodeURIComponent(currentProjectId));
                    const data = await res.json(); alert('🎞️ Timeline: ' + (data.total_timeline_duration_sec || 0) + ' giây.');
                }} catch(e) {{ alert("Lỗi tải Timeline!"); }}
            }}


            async function exportSrtSubtitles() {{
                try {{
                    const res = await fetch('/api/cineai/export-srt?id=' + encodeURIComponent(currentProjectId));
                    const data = await res.json();
                    if(data.srt_format) {{
                        const a = document.createElement('a');
                        a.href = URL.createObjectURL(new Blob([data.srt_format], {{type: 'text/plain'}}));
                        a.download = 'subtitles.srt'; a.click();
                    }} else alert('Chưa có dữ liệu xuất phụ đề!');
                }} catch(e) {{ alert("Lỗi xuất SRT!"); }}
            }}
        </script>
    </body></html>
    """
@app.get("/", response_class=HTMLResponse)
async def home(session_id: str = Cookie(None), load_id: str = None, tier: int = None, new_project: str = None):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return RedirectResponse(url="/login", status_code=303)
    
    projects = get_user_projects(username)
    target_project = None
    
    if new_project == "1":
        new_id = secrets.token_hex(6)
        target_project = migrate_project_to_tree({"id": new_id, "title": f"Dự án mới #{len(projects) + 1}"})
        grow_new_leaf(username, new_id, target_project)
        projects.insert(0, target_project)
    elif load_id:
        target_project = get_project_latest_leaf(load_id)
    elif projects:
        target_project = projects[0]
        
    if not target_project:
        new_id = secrets.token_hex(6)
        target_project = migrate_project_to_tree({"id": new_id, "title": "Dự án phim mới"})
        grow_new_leaf(username, new_id, target_project)


    if tier:
        target_project["metadata"]["highest_tier"] = max(target_project["metadata"].get("highest_tier", 1), tier)
        active_tier = tier
        grow_new_leaf(username, target_project.get("id"), target_project)
    else:
        active_tier = target_project["metadata"].get("highest_tier", 1)
        
    highest_tier = target_project["metadata"].get("highest_tier", 1)
    profile = get_user_profile_leaf(username)


    html_content = get_studio_html(target_project, profile.get("credits", 10), active_tier, highest_tier, username)
    js_content = get_studio_javascript(target_project.get("id", ""), active_tier)
    
    return HTMLResponse(content=html_content + js_content)


@app.get("/library", response_class=HTMLResponse)
async def library_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username: return RedirectResponse(url="/login", status_code=303)
    
    projects_html = ""
    for p in get_user_projects(username):
        projects_html += f"""
        <div class='bg-slate-900 p-5 mt-3 rounded-2xl border border-slate-800 shadow-lg'>
            <h3 class='text-amber-400 font-bold text-lg'>{p.get('metadata', {}).get('title')}</h3>
            <p class='text-xs text-slate-400 mb-3'>{p.get('metadata', {}).get('header')}</p>
            <div class='flex gap-2'>
                <a href='/?load_id={p.get('id')}' class='bg-amber-500 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs'>Vào Sân Khấu ➔</a>
                <button onclick="if(confirm('Xóa dự án này?')) fetch('/api/cineai/delete-project', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{id: '{p.get('id')}'}})}}).then(()=>location.reload())" class='bg-rose-950 text-rose-200 px-4 py-2 rounded-xl text-xs font-bold'>Xóa</button>
            </div>
        </div>"""
        
    profile = get_user_profile_leaf(username)
    return HTMLResponse(content=f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-slate-950 text-white p-4 sm:p-6 font-sans'><div class='max-w-3xl mx-auto'><div class='flex justify-between items-center bg-slate-900 p-4 rounded-2xl border border-slate-800 mb-4'><h1 class='text-base font-bold text-amber-400 uppercase'>📁 Thư Viện Cây Bất Tử</h1><div class='flex gap-2'><a href='/?new_project=1' class='bg-emerald-500 text-slate-950 px-3 py-2 rounded-xl text-xs font-bold'>➕ Tạo Mới</a><a href='/' class='bg-slate-800 text-slate-200 px-3 py-2 rounded-xl text-xs font-bold'>🏠 Studio</a></div></div>{projects_html or '<p class=\"text-slate-500 text-sm text-center py-10\">Chưa có dự án nào.</p>'}</div></body></html>")


@app.get("/login", response_class=HTMLResponse)
@app.post("/login", response_class=HTMLResponse)
async def login_handler(request: Request, tab: str = "login", error: str = None, success: str = None):
    if request.method == "POST":
        form_data = await request.form()
        username, password = form_data.get("username", "").strip(), form_data.get("password", "").strip()
        profile = get_user_profile_leaf(username)
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if (username == "admin" and password == "admin123") or (profile and profile.get("password_hash") == pwd_hash):
            session_id = secrets.token_hex(16)
            ACTIVE_SESSIONS[session_id] = username
            resp = RedirectResponse(url="/", status_code=303)
            resp.set_cookie(key="session_id", value=session_id)
            return resp
        return RedirectResponse(url="/login?error=" + urllib.parse.quote("⚠️ Sai tên đăng nhập hoặc mật khẩu!"), status_code=303)


    is_reg = (tab == "register")
    is_forgot = (tab == "forgot")
    form_action = "/register" if is_reg else ("/forgot-password" if is_forgot else "/login")
    title_text = "Tạo Tài Khoản Mới" if is_reg else ("Khôi Phục Mật Khẩu" if is_forgot else "Đăng Nhập Hệ Thống")
    
    err_html = f'<div class="bg-rose-950/80 border border-rose-800 p-3.5 rounded-2xl text-rose-200 text-xs font-bold text-center mb-4">{error}</div>' if error else ''
    succ_html = f'<div class="bg-emerald-950/80 border border-emerald-800 p-3.5 rounded-2xl text-emerald-200 text-xs font-bold text-center mb-4">{success}</div>' if success else ''


    login_template = f"""
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title_text} - Cine AI 7.1</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4 sm:p-6 font-sans">
        <div class="bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-800 w-full max-w-sm sm:max-w-md space-y-6 shadow-2xl">
            <div class="text-center space-y-1">
                <h2 class="text-xl sm:text-2xl font-black text-amber-400">{title_text}</h2>
                <p class="text-xs text-slate-400">Cine AI Studio Pro 7.1 • Immortal Tree</p>
            </div>
            {err_html} {succ_html}
            <form method="POST" action="{form_action}" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-1.5">Tên tài khoản:</label>
                    <input type="text" name="username" required placeholder="Nhập tên đăng nhập..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-4 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition shadow-inner">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-1.5">Mật khẩu:</label>
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
    return HTMLResponse(content=login_template)


@app.post("/register")
async def register_post(username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    profile = get_user_profile_leaf(username)
    # Kiểm tra xem tài khoản đã tồn tại hay chưa (nếu có password_hash khác mặc định)
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    
    new_profile = {
        "password_hash": pwd_hash,
        "credits": 10
    }
    save_user_profile_leaf(username, new_profile)
    
    session_id = secrets.token_hex(16)
    ACTIVE_SESSIONS[session_id] = username
    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(key="session_id", value=session_id)
    return resp


@app.post("/forgot-password")
async def forgot_password_post(username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    profile = get_user_profile_leaf(username)
    if not profile:
        return RedirectResponse(url="/login?tab=forgot&error=" + urllib.parse.quote("⚠️ Tên tài khoản không tồn tại trên hệ thống!"), status_code=303)
    
    profile["password_hash"] = hashlib.sha256(password.encode()).hexdigest()
    save_user_profile_leaf(username, profile)
    return RedirectResponse(url="/login?success=" + urllib.parse.quote("🎉 Đổi mật khẩu thành công! Vui lòng đăng nhập."), status_code=303)




@app.get("/logout")
async def logout(session_id: str = Cookie(None)):
    if session_id in ACTIVE_SESSIONS: del ACTIVE_SESSIONS[session_id]
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="session_id")
    return resp


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)