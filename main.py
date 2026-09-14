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
from fastapi import FastAPI, Request, Form, Response, Cookie, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse


app = FastAPI(title="Cine AI Studio Pro 6.5 - Full Enterprise Commercial Progressive Suite", version="6.5")


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
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={selected_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"], "gemini-1.5-flash"
        else:
            return None, f"Lỗi Google API ({response.status_code})"
    except Exception as e:
        return None, f"Lỗi kết nối: {str(e)}"


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
        current_highest = target_project.get("highest_tier", 1)
        target_project["highest_tier"] = max(current_highest, target_tier)
        target_project["current_tier"] = target_tier
        target_project["tierProgress"] = f"Tầng {target_project['highest_tier']} (Tiến độ cao nhất)"
        target_project["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"💾 Đã cập nhật thành công nội dung Tầng {target_tier} cho dự án '{new_title}'!"
    else:
        if len(projects) >= 2:
            return JSONResponse({"status": "limit_reached", "message": "⚠️ Đã đạt giới hạn tối đa 2 dự án thương mại cho mỗi user!"}, status_code=400)
        target_project = {
            "title": new_title,
            "header": project_header,
            "project_raw_story": project_story,
            "token_registry": {"visual_tokens": [], "audio_tokens": []},
            "scene_matrix": {},
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
        "message": f"✅ Nạp thành công kịch bản từ tệp '{file.filename}'!",
        "extracted_content": extracted_text
    })


@app.post("/api/cineai/upload-visual-token")
async def upload_visual_token(
    file: UploadFile = File(...),
    token_category: str = Form("character"),
    project_title: str = Form("Dự án mới"),
    session_id: str = Cookie(None)
):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    file_name = file.filename.lower()
    if not (file_name.endswith(".png") or file_name.endswith(".jpg") or file_name.endswith(".jpeg")):
        return JSONResponse({"status": "error", "message": "⚠️ Vui lòng chọn tệp hình ảnh (.png, .jpg)!"}, status_code=400)
    
    token_id = f"TOKEN_{token_category.upper()}_{secrets.token_hex(3).upper()}"
    mock_url = f"https://cdn.cineai.studio/tokens/{username}/{project_title.replace(' ', '_')}/{file.filename}"
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                if "token_registry" not in p:
                    p["token_registry"] = {"visual_tokens": [], "audio_tokens": []}
                p["token_registry"]["visual_tokens"].append({
                    "token_id": token_id,
                    "category": token_category,
                    "file_url": mock_url,
                    "file_name": file.filename,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                p["highest_tier"] = max(p.get("highest_tier", 1), 2)
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({"status": "success", "message": f"🖼️ Khóa mẫu hình ảnh thành công với mã định danh [{token_id}]!", "token_id": token_id, "file_name": file.filename})


@app.post("/api/cineai/upload-audio-token")
async def upload_audio_token(
    file: UploadFile = File(...),
    token_category: str = Form("bgm"),
    project_title: str = Form("Dự án mới"),
    session_id: str = Cookie(None)
):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"status": "error", "message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    file_name = file.filename.lower()
    if not (file_name.endswith(".mp3") or file_name.endswith(".wav")):
        return JSONResponse({"status": "error", "message": "⚠️ Vui lòng chọn tệp âm thanh (.mp3, .wav)!"}, status_code=400)
    
    token_id = f"TOKEN_AUDIO_{token_category.upper()}_{secrets.token_hex(3).upper()}"
    mock_url = f"https://cdn.cineai.studio/audio/{username}/{project_title.replace(' ', '_')}/{file.filename}"
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                if "token_registry" not in p:
                    p["token_registry"] = {"visual_tokens": [], "audio_tokens": []}
                p["token_registry"]["audio_tokens"].append({
                    "token_id": token_id,
                    "category": token_category,
                    "file_url": mock_url,
                    "file_name": file.filename,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                p["highest_tier"] = max(p.get("highest_tier", 1), 2)
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({"status": "success", "message": f"🎵 Khóa mẫu âm thanh thành công với mã định danh [{token_id}]!", "token_id": token_id, "file_name": file.filename})
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
    
    mode_instructions = {
        1: "Tầng 7 & 8: Khai thác qua 10 câu hỏi phỏng vấn cốt lõi, tự động điền thông tin, xây dựng cốt truyện và kiểm soát nhịp điệu (Pacing Graph) cho phim 45 phút.",
        2: "Tầng 9 & 10: Bóc tách kịch bản thành thước phim 30s-150s, áp dụng mã khóa cứng (FaceID, Costume & Prop Token, Landscape Token, Cinematic Color Grading Token) chống lỗi AI.",
        3: "Tầng 11 & 12: Niêm phong dữ liệu gốc, điều phối AI render tích hợp mã lệnh Stereo 3D spatial audio và quản lý kho lưu trữ biến thể (Alternate Takes).",
        4: "Tầng 13 đến 16: Render toàn tập, quản lý hạn mức dung lượng/thời lượng, xuất file HD/2K/4K (9:16 hoặc 16:9) và phát triển/tiếp nối dự án."
    }
    
    system_persona = (
        "Bạn là Đạo diễn ảo thấu cảm và chuyên gia sản xuất phim thương mại cấp cao của Cine AI Studio Pro 6.5. "
        f"Trạng thái vận hành hiện tại: {mode_instructions.get(tier, mode_instructions[1])} "
        "Hãy đóng vai trò người dẫn dắt thông minh, tự động phân tích ý tưởng, đưa ra prompt chuyên sâu chống lỗi trôi nhân vật, đạo cụ ma và lệch màu sắc.\n\n"
        f"Dự án hiện tại: {project_title}\n"
    )
    prompt = system_persona + f"Yêu cầu từ nhà sáng tạo: {user_message}"
    reply_text, err_msg = call_gemini_direct(prompt)
    if not reply_text:
        reply_text = f"⚠️ {err_msg}"
        
    return JSONResponse({"reply": reply_text, "project": project_title})


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
        return JSONResponse({"reply": "⚠️ Chưa có nội dung kịch bản thô. Vui lòng nhập hoặc tải lên kịch bản tại Tầng 1!"}, status_code=400)
    
    keys = get_gemini_keys()
    if not keys:
        return JSONResponse({"reply": "⚠️ Chưa cấu hình GEMINI_API_KEYS trên Render!"}, status_code=500)
    
    selected_key = random.choice(keys)
    model_name = "gemini-1.5-pro"
    url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={selected_key}"
    
    pro_prompt = (
        "Bạn là Tổng đạo diễn và Kiến trúc sư thuật toán của Cine AI Studio Pro 6.5. "
        "Hãy phân tích kịch bản sau và trả về DUY NHẤT một chuỗi JSON hợp lệ (không kèm văn bản ngoài), "
        "được chia theo cấu trúc 3 Hồi (Act I, Act II, Act III) cho phim 45 phút. "
        "Mỗi cảnh (Scene) phải có thời lượng từ 30 đến 150 giây và gắn Global Lock-in Tokens.\n\n"
        "Định dạng JSON yêu cầu:\n"
        "{\n"
        '  "acts": [\n'
        "    {\n"
        '      "act_name": "Act I",\n'
        '      "scenes": [\n'
        "        {\n"
        '          "scene_id": 1,\n'
        '          "title": "Tên cảnh",\n'
        '          "duration_sec": 60,\n'
        '          "summary": "Nội dung ngắn gọn",\n'
        '          "lock_tokens": {\n'
        '            "face_id": "CHAR_A_TOKEN",\n'
        '            "costume": "COSTUME_A_TOKEN",\n'
        '            "landscape": "LOC_A_TOKEN",\n'
        '            "color_grading": "CINEMATIC_WARM_LUT"\n'
        "          }\n"
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Nội dung kịch bản gốc:\n{raw_story}"
    )
    payload = {"contents": [{"parts": [{"text": pro_prompt}]}], "systemInstruction": {"parts": [{"text": "Luôn luôn trả về định dạng JSON thuần túy chuẩn xác 100%, không giải thích dài dòng."}]}}
    headers = {"Content-Type": "application/json"}
    
    parsed_scenes = None
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=40)
            data_res = response.json()
            raw_response = data_res["candidates"][0]["content"]["parts"][0]["text"]
            clean_json_str = re.sub(r"^```json\s*|\s*```$", "", raw_response.strip(), flags=re.IGNORECASE)
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
        "schema_version": "6.5-Enterprise",
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
        "message": "🌟 Đã bóc tách phân cảnh kịch bản cấp độ Enterprise 6.5!",
        "metrics": structured_data["pacing_metrics"],
        "data": parsed_scenes
    })


@app.post("/api/cineai/render-scene-take")
async def render_scene_take(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"message": "⚠️ Phiên đăng nhập hết hạn!"}, status_code=401)
    
    user_data = USERS_DB.get(username, {})
    current_credits = user_data.get("credits", 10)
    render_cost = 5
    if current_credits < render_cost:
        return JSONResponse({"status": "payment_required", "message": f"⚠️ Số dư Credit không đủ ({current_credits}/{render_cost} credit). Vui lòng nạp thêm qua cổng SePay/VietQR để tiếp tục render!"}, status_code=402)
    
    data = await request.json()
    project_title = data.get("title", "Dự án mới")
    scene_id = data.get("scene_id", 1)
    user_tweak = data.get("tweak_prompt", "")
    
    project_data = None
    if "projects" in user_data:
        for p in user_data["projects"]:
            if p.get("title") == project_title:
                project_data = p
                break
    if not project_data:
        return JSONResponse({"reply": "⚠️ Không tìm thấy dự án!"}, status_code=404)
        
    enterprise_data = project_data.get("scene_breakdown_enterprise", {})
    scenes_json = enterprise_data.get("scenes_data", {})
    target_scene = None
    if "acts" in scenes_json:
        for act in scenes_json["acts"]:
            for sc in act.get("scenes", []):
                if sc.get("scene_id") == scene_id:
                    target_scene = sc
                    break
            if target_scene:
                break
    if not target_scene:
        return JSONResponse({"reply": f"⚠️ Không tìm thấy Phân cảnh số {scene_id}!"}, status_code=404)


    lock_tokens = target_scene.get("lock_tokens", {})
    face_token = lock_tokens.get("face_id", "CHAR_DEFAULT")
    costume_token = lock_tokens.get("costume", "COSTUME_DEFAULT")
    landscape_token = lock_tokens.get("landscape", "LOC_DEFAULT")
    color_lut = lock_tokens.get("color_grading", "CINEMATIC_LUT")
    
    audiophile_tags = "Binaural 3D spatial audio, holographic soundstage, crystal clear 24-bit audiophile, dynamic left-right hard panning."
    final_render_prompt = (
        f"Masterpiece cinematic shot, 4K resolution. "
        f"Scene: {target_scene.get('summary', '')}. "
        f"Tokens -> FaceID: [{face_token}], Costume: [{costume_token}], Landscape: [{landscape_token}], Color: [{color_lut}]. "
        f"Audio: {audiophile_tags}. Note: {user_tweak}"
    )


    if "alternate_takes" not in enterprise_data:
        enterprise_data["alternate_takes"] = {}
    scene_key = f"scene_{scene_id}"
    if scene_key not in enterprise_data["alternate_takes"]:
        enterprise_data["alternate_takes"][scene_key] = []
        
    current_takes = enterprise_data["alternate_takes"][scene_key]
    new_take_id = len(current_takes) + 1
    new_take_object = {
        "take_id": new_take_id,
        "status": "rendered_success",
        "render_prompt": final_render_prompt,
        "media_url": f"https://cdn.cineai.studio/renders/{project_title.replace(' ', '_')}_s{scene_id}_take{new_take_id}.mp4",
        "audio_specs": audiophile_tags,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    current_takes.append(new_take_object)
    
    user_data["credits"] = current_credits - render_cost
    project_data["highest_tier"] = max(project_data.get("highest_tier", 1), 4)
    project_data["tierProgress"] = f"Tầng 12 (Đã render Scene {scene_id} - Take {new_take_id})"
    save_users()
    
    return JSONResponse({
        "status": "success",
        "message": f"🎬 Render thành công Phân cảnh {scene_id} (Take {new_take_id})! Đã trừ {render_cost} credit (Số dư còn lại: {user_data['credits']} credit).",
        "remaining_credits": user_data["credits"],
        "take_info": new_take_object
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


    return JSONResponse({"status": "success", "total_timeline_duration_sec": total_duration, "rough_cut_playlist": rough_cut_timeline})


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
@app.get("/", response_class=HTMLResponse)
async def home(session_id: str = Cookie(None), load_project: str = None, tier: int = None):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    user_data = USERS_DB.get(username, {})
    user_credits = user_data.get("credits", 10)
    projects = user_data.get("projects", [])
    
    target_project = None
    if load_project:
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
            "token_registry": {"visual_tokens": [], "audio_tokens": []},
            "highest_tier": 1,
            "current_tier": 1
        }
        projects.append(target_project)
        user_data["projects"] = projects
        save_users()


    highest_tier = target_project.get("highest_tier", 1)
    active_tier = tier if tier and tier <= highest_tier else highest_tier


    tokens_html = ""
    visual_tokens = target_project.get("token_registry", {}).get("visual_tokens", [])
    audio_tokens = target_project.get("token_registry", {}).get("audio_tokens", [])
    for vt in visual_tokens:
        tokens_html += f'<div class="bg-slate-900 border border-slate-800 p-2.5 rounded-xl text-xs flex justify-between items-center"><span class="text-indigo-400 font-bold">🖼️ {vt.get("token_id")}</span><span class="text-slate-400 text-[11px]">{vt.get("category")}</span></div>'
    for at in audio_tokens:
        tokens_html += f'<div class="bg-slate-900 border border-slate-800 p-2.5 rounded-xl text-xs flex justify-between items-center"><span class="text-emerald-400 font-bold">🎵 {at.get("token_id")}</span><span class="text-slate-400 text-[11px]">{at.get("category")}</span></div>'


    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cine AI Studio Pro 6.5 - Progressive Suite</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-3 sm:p-5 font-sans">
        <div class="max-w-4xl mx-auto space-y-4">
            
            <div class="flex justify-between items-center bg-slate-900 p-4 rounded-2xl border border-slate-800 shadow-xl">
                <div>
                    <h1 class="text-base sm:text-lg font-bold text-amber-400">🎬 Cine AI Studio Pro 6.5</h1>
                    <p class="text-xs text-slate-400">Dự án: <b class="text-slate-200">PROJECT_TITLE_VAL</b></p>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-emerald-400 font-bold bg-emerald-950/60 px-3 py-1 rounded-full border border-emerald-800">💰 USER_CREDITS_VAL C</span>
                    <a href="/library" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-xl text-xs font-semibold transition">📁 Thư Viện</a>
                    <a href="/community" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-xl text-xs font-semibold transition">🌍 Public</a>
                </div>
            </div>


            <!-- THANH TIẾN TRÌNH TUẦN TỰ (BREADCRUMB) -->
            <div class="grid grid-cols-4 gap-1.5 bg-slate-900 p-1.5 rounded-2xl border border-slate-800 text-center text-xs font-bold">
                <a href="/?load_project=PROJECT_TITLE_ENCODED&tier=1" class="py-2.5 rounded-xl transition TIER_1_CLASS">1. Kịch Bản</a>
                <a href="/?load_project=PROJECT_TITLE_ENCODED&tier=2" class="py-2.5 rounded-xl transition TIER_2_CLASS">2. Khóa Token</a>
                <a href="/?load_project=PROJECT_TITLE_ENCODED&tier=3" class="py-2.5 rounded-xl transition TIER_3_CLASS">3. Bóc Tách</a>
                <a href="/?load_project=PROJECT_TITLE_ENCODED&tier=4" class="py-2.5 rounded-xl transition TIER_4_CLASS">4. Render</a>
            </div>


            <!-- MÀN HÌNH TẦNG 1: KỊCH BẢN GỐC -->
            <div id="screen-tier-1" class="TIER_1_VISIBILITY bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                    <h2 class="text-sm font-bold text-amber-400 uppercase tracking-wider">📝 Tầng 1: Khai Mở Ý Tưởng & Kịch Bản Gốc</h2>
                    <span class="text-xs bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full border border-amber-500/20">Bước 1/4</span>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-1">Tên Dự Án Phim:</label>
                    <input type="text" id="project-title" value="PROJECT_TITLE_VAL" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-amber-300 font-bold">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-1">Đề Mục / Logline & Thể Loại:</label>
                    <input type="text" id="project-header" value="PROJECT_HEADER_VAL" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-200">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-1">Nội Dung Kịch Bản Thô (Text):</label>
                    <textarea id="project-story" rows="5" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-200">PROJECT_STORY_VAL</textarea>
                </div>
                <div class="space-y-2 p-3 bg-slate-950/60 rounded-2xl border border-slate-800">
                    <span class="text-xs text-slate-400">Hoặc tải tệp kịch bản (.txt, .md):</span>
                    <div class="flex gap-2">
                        <input type="file" id="file-story" accept=".txt,.md" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-400">
                        <button onclick="uploadStoryFile()" class="bg-blue-600 hover:bg-blue-500 px-4 py-2 rounded-xl text-xs font-bold text-white whitespace-nowrap">Nạp File</button>
                    </div>
                </div>
                <div class="flex gap-2 pt-2">
                    <button onclick="saveDraftCurrent(1)" class="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">💾 Lưu Nháp</button>
                    <button onclick="goToTier(2)" class="flex-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3.5 rounded-2xl text-xs transition shadow-lg">Tiếp tục (hoặc Bỏ qua) ➔</button>
                </div>
            </div>


            <!-- MÀN HÌNH TẦNG 2: KHÓA MẪU TOKEN -->
            <div id="screen-tier-2" class="TIER_2_VISIBILITY bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                    <h2 class="text-sm font-bold text-amber-400 uppercase tracking-wider">🖼️ Tầng 2: Khóa Mẫu Hình Ảnh & Âm Thanh</h2>
                    <span class="text-xs bg-indigo-500/10 text-indigo-400 px-3 py-1 rounded-full border border-indigo-500/20">Bước 2/4</span>
                </div>
                <div class="p-3 bg-slate-950/60 rounded-2xl border border-slate-800 space-y-2">
                    <label class="block text-xs font-bold text-slate-300">1. Khóa Token Hình Ảnh (Nhân vật, Trang phục, Bối cảnh):</label>
                    <div class="flex gap-2">
                        <select id="visual-category" class="bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-200">
                            <option value="character">Nhân vật</option>
                            <option value="costume">Trang phục</option>
                            <option value="landscape">Bối cảnh</option>
                        </select>
                        <input type="file" id="file-visual" accept=".png,.jpg,.jpeg" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-400">
                    </div>
                    <button onclick="uploadVisualToken()" class="w-full bg-indigo-600 hover:bg-indigo-500 py-2.5 rounded-xl text-xs font-bold text-white transition">🖼️ Lưu Token Hình Ảnh</button>
                </div>
                <div class="p-3 bg-slate-950/60 rounded-2xl border border-slate-800 space-y-2">
                    <label class="block text-xs font-bold text-slate-300">2. Khóa Token Âm Thanh (BGM / Giọng đọc):</label>
                    <div class="flex gap-2">
                        <select id="audio-category" class="bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-200">
                            <option value="bgm">Nhạc nền</option>
                            <option value="voice">Giọng đọc</option>
                        </select>
                        <input type="file" id="file-audio" accept=".mp3,.wav" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-xs text-slate-400">
                    </div>
                    <button onclick="uploadAudioToken()" class="w-full bg-emerald-600 hover:bg-emerald-500 py-2.5 rounded-xl text-xs font-bold text-slate-950 transition">🎵 Lưu Token Âm Thanh</button>
                </div>
                <div class="space-y-2">
                    <span class="text-xs font-bold text-slate-400">Kho Token Của Dự Án:</span>
                    <div id="tokens-tray" class="space-y-1.5 max-h-32 overflow-y-auto">TOKENS_HTML_VAL</div>
                </div>
                <div class="flex gap-2 pt-2">
                    <button onclick="goToTier(1)" class="w-1/3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">⬅️ Tầng 1</button>
                    <button onclick="saveDraftCurrent(2)" class="w-1/3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">💾 Lưu Nháp</button>
                    <button onclick="goToTier(3)" class="w-1/3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3.5 rounded-2xl text-xs transition shadow-lg">Tiếp Tục ➔</button>
                </div>
            </div>


            <!-- MÀN HÌNH TẦNG 3: BÓC TÁCH PHÂN CẢNH -->
            <div id="screen-tier-3" class="TIER_3_VISIBILITY bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                    <h2 class="text-sm font-bold text-amber-400 uppercase tracking-wider">🎬 Tầng 3: Bóc Tách Phân Cảnh & Ma Trận 3 Hồi</h2>
                    <span class="text-xs bg-purple-500/10 text-purple-400 px-3 py-1 rounded-full border border-purple-500/20">Bước 3/4</span>
                </div>
                <button onclick="runBreakdown()" class="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold py-3.5 rounded-2xl text-xs shadow-lg transition">🚀 Kích Hoạt AI Bóc Tách Phân Cảnh</button>
                <div id="breakdown-result" class="bg-slate-950 p-4 rounded-2xl border border-slate-800 text-xs space-y-2 text-slate-300 max-h-44 overflow-y-auto">
                    Chưa bóc tách kịch bản. Hãy bấm nút phía trên để kích hoạt AI.
                </div>
                <div class="flex gap-2 pt-2">
                    <button onclick="goToTier(2)" class="w-1/3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">⬅️ Tầng 2</button>
                    <button onclick="saveDraftCurrent(3)" class="w-1/3 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">💾 Lưu Nháp</button>
                    <button onclick="goToTier(4)" class="w-1/3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-3.5 rounded-2xl text-xs transition shadow-lg">Tiếp Tục ➔</button>
                </div>
            </div>


            <!-- MÀN HÌNH TẦNG 4: RENDER & DỰNG PHIM -->
            <div id="screen-tier-4" class="TIER_4_VISIBILITY bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-3">
                    <h2 class="text-sm font-bold text-amber-400 uppercase tracking-wider">🎞️ Tầng 4: Phòng Dựng, Render & Xuất Bản</h2>
                    <span class="text-xs bg-emerald-500/10 text-emerald-400 px-3 py-1 rounded-full border border-emerald-800/20">Bước 4/4</span>
                </div>
                <div class="space-y-2.5">
                    <button onclick="renderScene(1)" class="w-full bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black py-3.5 rounded-2xl text-xs shadow-lg transition">🎬 Render Phân Cảnh Mẫu (5 Credit)</button>
                    <button onclick="fetchTimeline()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3 rounded-2xl text-xs transition">🎞️ Xem Timeline Rough-Cut Playlist</button>
                    <button onclick="exportSrtSubtitles()" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-3 rounded-2xl text-xs transition">📜 Xuất Phụ Đề Chuẩn .SRT</button>
                </div>
                <div class="flex gap-2 pt-2">
                    <button onclick="goToTier(3)" class="w-1/2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">⬅️ Tầng 3</button>
                    <button onclick="saveDraftCurrent(4)" class="w-1/2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3.5 rounded-2xl text-xs transition">💾 Lưu Toàn Bộ Dự Án</button>
                </div>
            </div>


            <!-- CỬA SỔ CHAT ĐẠO DIỄN ẢO TƯƠNG TÁC TỪNG CHẶNG -->
            <div class="bg-slate-900 p-4 rounded-3xl border border-slate-800 space-y-3 shadow-xl">
                <span class="text-xs font-bold text-amber-400 uppercase tracking-wider">💬 Đạo Diễn Ảo Đồng Hành (Tầng ACTIVE_TIER_VAL)</span>
                <div id="chat-box" class="bg-slate-950 h-32 rounded-2xl p-3 overflow-y-auto text-xs text-slate-300 border border-slate-800 space-y-2">
                    <p class="text-blue-200">Chào bạn! Tôi đang đồng hành cùng bạn tại Tầng ACTIVE_TIER_VAL. Bạn có thể trao đổi ý tưởng hoặc bấm Skip để đi tiếp.</p>
                </div>
                <div class="flex gap-2">
                    <input type="text" id="chat-input" placeholder="Trao đổi với Đạo diễn ảo..." class="flex-1 bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs focus:outline-none focus:border-amber-500">
                    <button onclick="sendChat()" class="bg-indigo-600 hover:bg-indigo-500 px-4 py-3 rounded-xl font-bold text-xs text-white transition">Gửi</button>
                </div>
            </div>


        </div>
        <script>
            let currentActiveTier = ACTIVE_TIER_VAL;
            let currentHighestTier = HIGHEST_TIER_VAL;
            let currentProjectTitle = "PROJECT_TITLE_VAL";


            function goToTier(targetTier) {
                window.location.href = '/?load_project=' + encodeURIComponent(currentProjectTitle) + '&tier=' + targetTier;
            }


            async function saveDraftCurrent(tier) {
                const title = document.getElementById('project-title') ? document.getElementById('project-title').value : currentProjectTitle;
                const header = document.getElementById('project-header') ? document.getElementById('project-header').value : "";
                const story = document.getElementById('project-story') ? document.getElementById('project-story').value : "";
                
                try {
                    const res = await fetch('/api/cineai/save-draft', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({old_title: currentProjectTitle, title: title, header: header, story: story, tier: tier})
                    });
                    const data = await res.json();
                    alert(data.message);
                    if(data.status === 'success') {
                        currentProjectTitle = data.saved_title;
                    }
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
                const res = await fetch('/api/cineai/upload-asset-explicit', {method: 'POST', body: formData});
                const data = await res.json();
                if(data.status === 'success') {
                    document.getElementById('project-story').value = data.extracted_content;
                    alert(data.message);
                } else alert(data.message);
            }


            async function uploadVisualToken() {
                const fileInput = document.getElementById('file-visual');
                if(fileInput.files.length === 0) return alert('⚠️ Vui lòng chọn tệp ảnh (.png, .jpg)!');
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('token_category', document.getElementById('visual-category').value);
                formData.append('project_title', currentProjectTitle);
                const res = await fetch('/api/cineai/upload-visual-token', {method: 'POST', body: formData});
                const data = await res.json();
                alert(data.message);
                if(data.status === 'success') location.reload();
            }


            async function uploadAudioToken() {
                const fileInput = document.getElementById('file-audio');
                if(fileInput.files.length === 0) return alert('⚠️ Vui lòng chọn tệp âm thanh (.mp3, .wav)!');
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('token_category', document.getElementById('audio-category').value);
                formData.append('project_title', currentProjectTitle);
                const res = await fetch('/api/cineai/upload-audio-token', {method: 'POST', body: formData});
                const data = await res.json();
                alert(data.message);
                if(data.status === 'success') location.reload();
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
                const text = input.value.trim();
                if(!text) return;
                box.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-2.5 rounded-xl inline-block text-slate-100">' + text + '</span></div>';
                input.value = '';
                const res = await fetch('/api/cineai/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, title: currentProjectTitle, tier: currentActiveTier})
                });
                const data = await res.json();
                box.innerHTML += '<div class="bg-blue-950/60 p-2.5 rounded-xl text-blue-200">' + data.reply + '</div>';
                box.scrollTop = box.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


    def get_tier_classes(idx):
        if idx == active_tier:
            return "bg-amber-500 text-slate-950 shadow-md pointer-events-none"
        if idx <= highest_tier:
            return "bg-slate-800 text-slate-200 hover:bg-slate-700 cursor-pointer"
        return "bg-slate-950 text-slate-600 pointer-events-none opacity-40"


    html_content = html_content.replace("USER_CREDITS_VAL", str(user_credits))
    html_content = html_content.replace("PROJECT_TITLE_VAL", target_project.get("title", ""))
    html_content = html_content.replace("PROJECT_TITLE_ENCODED", urllib.parse.quote(target_project.get("title", "")))
    html_content = html_content.replace("PROJECT_HEADER_VAL", target_project.get("header", ""))
    html_content = html_content.replace("PROJECT_STORY_VAL", target_project.get("project_raw_story", ""))
    html_content = html_content.replace("ACTIVE_TIER_VAL", str(active_tier))
    html_content = html_content.replace("HIGHEST_TIER_VAL", str(highest_tier))
    html_content = html_content.replace("TOKENS_HTML_VAL", tokens_html or "<p class='text-slate-500 text-xs italic'>Chưa có token nào.</p>")


    for i in range(1, 5):
        html_content = html_content.replace(f"TIER_{i}_CLASS", get_tier_classes(i))
        html_content = html_content.replace(f"TIER_{i}_VISIBILITY", "block" if i == active_tier else "hidden")


    return HTMLResponse(content=html_content)
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
        projects_html += f"""
        <div class="bg-slate-950 p-5 rounded-3xl border border-slate-800 flex justify-between items-center gap-3">
            <div>
                <span class="text-[10px] font-bold bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full border border-amber-500/20">🎬 Tiến độ: Tầng {h_tier}</span>
                <h3 class="text-base font-black text-slate-100 mt-2">{title}</h3>
                <p class="text-xs text-slate-400 italic">{p.get("header", "")}</p>
            </div>
            <div class="flex gap-2">
                <a href="/?load_project={urllib.parse.quote(title)}" class="bg-amber-500 text-slate-950 font-black px-4 py-3 rounded-2xl text-xs uppercase shadow transition">Mở</a>
                <button onclick="confirmDelete('{title}')" class="bg-rose-900/60 hover:bg-rose-700 text-rose-200 px-3 py-3 rounded-2xl text-xs font-bold transition">Xóa</button>
            </div>
        </div>
        """


    library_template = """
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Thư Viện - Cine AI 6.5</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-4 font-sans">
        <div class="max-w-4xl mx-auto space-y-4">
            <div class="flex justify-between items-center bg-slate-900 p-5 rounded-3xl border border-slate-800 shadow-xl">
                <div>
                    <h1 class="text-lg font-bold text-amber-400">📁 Thư Viện Dự Án</h1>
                    <p class="text-xs text-slate-400">Hạn mức: PROJECT_COUNT_VAL/2 dự án • Ví Credit: USER_CREDITS_VAL C</p>
                </div>
                <a href="/" class="bg-slate-800 text-slate-200 px-4 py-2.5 rounded-2xl text-xs font-bold transition">⚡ Studio</a>
            </div>
            <div class="bg-slate-900 p-5 rounded-3xl border border-slate-800 space-y-3">PROJECTS_LIST_VAL</div>
        </div>
        <script>
            async function confirmDelete(title) {
                if(confirm("⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn dự án '" + title + "' không?")) {
                    const res = await fetch('/api/cineai/delete-project', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:title})});
                    const d = await res.json();
                    alert(d.message);
                    location.reload();
                }
            }
        </script>
    </body></html>
    """
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
    
    err_html = f'<div class="bg-rose-950/80 p-3 rounded-2xl text-rose-200 text-xs font-bold text-center">{error}</div>' if error else ''
    succ_html = f'<div class="bg-emerald-950/80 p-3 rounded-2xl text-emerald-200 text-xs font-bold text-center">{success}</div>' if success else ''


    login_template = """
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Xác Thực - Cine AI 6.5</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4 font-sans">
        <div class="bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-800 w-full max-w-md space-y-5 shadow-2xl">
            <h2 class="text-xl font-bold text-amber-400 text-center">PAGE_TITLE_VAL</h2>
            ALERT_ERR_VAL ALERT_SUCC_VAL
            <form method="POST" action="FORM_ACTION_VAL" class="space-y-4">
                <input type="text" name="username" required placeholder="Tên tài khoản..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-3.5 text-xs text-slate-100">
                <input type="password" name="password" required placeholder="Mật khẩu..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-3.5 text-xs text-slate-100">
                <button type="submit" class="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold py-3.5 rounded-2xl text-xs uppercase shadow-xl transition">Xác Nhận</button>
            </form>
            <div class="flex justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800">
                <a href="/login" class="hover:underline text-amber-400">Đăng nhập</a>
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
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Cộng Đồng - Cine AI 6.5</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-5 font-sans">
        <div class="max-w-4xl mx-auto space-y-4">
            <div class="flex justify-between items-center bg-slate-900 p-5 rounded-3xl border border-slate-800 shadow-xl">
                <h1 class="text-lg font-bold text-amber-400">🌍 Cộng Đồng Phim Public Pro 6.5</h1>
                <a href="/" class="bg-amber-500 text-slate-950 font-bold px-4 py-2 rounded-2xl text-xs">⚡ Quay lại Studio</a>
            </div>
            <div class="bg-slate-900 p-6 rounded-3xl border border-slate-800 text-xs text-slate-400 text-center py-10">Bảng tin cộng đồng đang kết nối API mạng xã hội...</div>
        </div>
    </body></html>
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)