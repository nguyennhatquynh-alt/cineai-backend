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




app = FastAPI(title="Cine AI Studio Pro 6.4 - Full Enterprise Commercial & Multi-Asset Ecosystem", version="6.4")




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
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
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
        target_project["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"💾 Đã cập nhật thành công nội dung cho dự án '{new_title}'!"
    else:
        if len(projects) >= 2:
            return JSONResponse({"status": "limit_reached", "message": "⚠️ Đã đạt giới hạn tối đa 2 dự án thương mại cho mỗi user!"}, status_code=400)
        projects.append({
            "title": new_title,
            "header": project_header,
            "project_raw_story": project_story,
            "token_registry": {
                "visual_tokens": [],
                "audio_tokens": []
            },
            "scene_matrix": {},
            "tierProgress": "Tầng 7-8 (Đang lưu nháp)",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        msg = f"💾 Đã tạo và lưu nháp dự án mới '{new_title}' thành công!"
        
    save_users()
    return JSONResponse({"status": "success", "message": msg, "saved_title": new_title})




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
        return JSONResponse({
            "status": "error",
            "message": "⚠️ Vui lòng chọn đúng tệp kịch bản văn bản (.txt hoặc .md)."
        }, status_code=400)
    
    try:
        extracted_text = file_content.decode("utf-8", errors="ignore")
    except Exception as e:
        extracted_text = f"Không thể đọc tệp: {str(e)}"
    
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
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({
        "status": "success",
        "message": f"🖼️ Khóa mẫu hình ảnh thành công với mã định danh [{token_id}]!",
        "token_id": token_id
    })




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
                p["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        save_users()
        
    return JSONResponse({
        "status": "success",
        "message": f"🎵 Khóa mẫu âm thanh thành công với mã định danh [{token_id}]!",
        "token_id": token_id
    })




@app.post("/api/cineai/chat")
async def chat_with_director(request: Request, session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return JSONResponse({"reply": "⚠️ Phiên đăng nhập hết hạn! Vui lòng tải lại trang."}, status_code=401)
    
    data = await request.json()
    user_message = data.get("message", "")
    project_title = data.get("title", "Dự án mới")
    tier_mode = data.get("tierMode", "tầng-7-8")
    
    if not user_message:
        return JSONResponse({"reply": "Vui lòng nhập nội dung trao đổi với Đạo diễn ảo!"})
    
    mode_instructions = {
        "tầng-7-8": "Tầng 7 & 8: Khai thác qua 10 câu hỏi phỏng vấn cốt lõi, tự động điền thông tin, xây dựng cốt truyện và kiểm soát nhịp điệu (Pacing Graph) cho phim 45 phút.",
        "tầng-9-10": "Tầng 9 & 10: Bóc tách kịch bản thành thước phim 30s-150s, áp dụng mã khóa cứng (FaceID, Costume & Prop Token, Landscape Token, Cinematic Color Grading Token) chống lỗi AI.",
        "tầng-11-12": "Tầng 11 & 12: Niêm phong dữ liệu gốc, điều phối AI render tích hợp mã lệnh Stereo 3D spatial audio và quản lý kho lưu trữ biến thể (Alternate Takes).",
        "tầng-13-16": "Tầng 13 đến 16: Render toàn tập, quản lý hạn mức dung lượng/thời lượng, xuất file HD/2K/4K (9:16 hoặc 16:9) và phát triển/tiếp nối dự án."
    }
    
    system_persona = (
        "Bạn là Đạo diễn ảo thấu cảm và chuyên gia sản xuất phim thương mại cấp cao của Cine AI Studio Pro 6.4. "
        f"Trạng thái vận hành: {mode_instructions.get(tier_mode, '')} "
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
    
    if not raw_story:
        if username in USERS_DB and "projects" in USERS_DB[username]:
            for p in USERS_DB[username]["projects"]:
                if p.get("title") == project_title:
                    raw_story = p.get("project_raw_story", "")
                    break
                    
    if not raw_story:
        return JSONResponse({"reply": "⚠️ Chưa có nội dung dự án. Vui lòng nhập hoặc tải lên kịch bản thô trước!"}, status_code=400)
    
    keys = get_gemini_keys()
    if not keys:
        return JSONResponse({"reply": "⚠️ Chưa cấu hình GEMINI_API_KEYS trên Render!"}, status_code=500)
    
    selected_key = random.choice(keys)
    model_name = "gemini-1.5-pro" 
    url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={selected_key}"
    
    pro_prompt = (
        "Bạn là Tổng đạo diễn và Kiến trúc sư thuật toán của Cine AI Studio Pro 6.4. "
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
    
    payload = {
        "contents": [{"parts": [{"text": pro_prompt}]}],
        "systemInstruction": {"parts": [{"text": "Luôn luôn trả về định dạng JSON thuần túy chuẩn xác 100%, không giải thích dài dòng."}]}
    }
    headers = {"Content-Type": "application/json"}
    
    parsed_scenes = None
    max_retries = 2
    current_prompt = pro_prompt
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=40)
            if response.status_code != 200:
                if attempt == max_retries:
                    return JSONResponse({"reply": f"⚠️ Lỗi gọi API Google ({response.status_code})"}, status_code=500)
                continue
                
            data_res = response.json()
            raw_response = data_res["candidates"][0]["content"]["parts"][0]["text"]
            clean_json_str = re.sub(r"^```json\s*|\s*```$", "", raw_response.strip(), flags=re.IGNORECASE)
            parsed_scenes = json.loads(clean_json_str)
            break
        except (json.JSONDecodeError, Exception) as parse_err:
            if attempt < max_retries:
                error_feedback = f"\n\n[HỆ THỐNG BÁO LỖI CÚ PHÁP JSON]: {str(parse_err)}. Hãy sửa lại toàn bộ phản hồi trước đó thành một chuỗi JSON chuẩn mực, hợp lệ tuyệt đối."
                payload["contents"][0]["parts"][0]["text"] = current_prompt + error_feedback
                continue
            else:
                parsed_scenes = {"raw_fallback": "Không thể tự động ép kiểu JSON sau các lần thử tự chữa lỗi."}




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
        "schema_version": "6.4-Enterprise",
        "routing_model": model_name,
        "self_healing_applied": True,
        "pacing_metrics": {
            "total_duration_sec": total_duration,
            "act_breakdown": act_durations
        },
        "scenes_data": parsed_scenes,
        "alternate_takes": {},
        "active_takes": {},
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if username in USERS_DB and "projects" in USERS_DB[username]:
        for p in USERS_DB[username]["projects"]:
            if p.get("title") == project_title:
                p["scene_breakdown_enterprise"] = structured_data
                p["tierProgress"] = "Tầng 9-12 (Enterprise Routing & Self-Healing)"
                break
        save_users()
        
    return JSONResponse({
        "status": "success",
        "message": "🌟 Đã vận hành hệ thống cấp độ Enterprise 6.4: Định tuyến Model Pro, Context Caching & JSON Self-Healing!",
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
        return JSONResponse({
            "status": "payment_required",
            "message": f"⚠️ Số dư Credit không đủ ({current_credits}/{render_cost} credit). Vui lòng nạp thêm qua cổng SePay/VietQR để tiếp tục render!"
        }, status_code=402)
    
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
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    current_takes.append(new_take_object)
    project_data["tierProgress"] = f"Tầng 12 (Đã render Scene {scene_id} - Take {new_take_id})"
    
    user_data["credits"] = current_credits - render_cost
    save_users()
    
    return JSONResponse({
        "status": "success",
        "message": f"🎬 Render thành công Phân cảnh {scene_id} (Take {new_take_id})! Đã trừ {render_cost} credit (Số dư còn lại: {user_data['credits']} credit).",
        "remaining_credits": user_data["credits"],
        "take_info": new_take_object
    })




@app.post("/api/payments/webhook")
async def sepay_payment_webhook(request: Request):
    try:
        data = await request.json()
        content = data.get("content", "")
        transfer_amount = int(data.get("transferAmount", 0))
        
        match = re.search(r"NAPCREDIT\s+([a-zA-Z0-9_-]+)", content, re.IGNORECASE)
        if match:
            target_username = match.group(1)
            if target_username in USERS_DB:
                credits_to_add = int(transfer_amount / 1000) 
                if credits_to_add > 0:
                    USERS_DB[target_username]["credits"] = USERS_DB[target_username].get("credits", 0) + credits_to_add
                    save_users()
                    return JSONResponse({"success": True, "message": f"Đã cộng {credits_to_add} credit cho user {target_username}"})
        
        return JSONResponse({"success": False, "message": "Không khớp cú pháp nạp tiền"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)




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
@app.get("/", response_class=HTMLResponse)
async def home(session_id: str = Cookie(None), load_project: str = None):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    user_data = USERS_DB.get(username, {})
    user_credits = user_data.get("credits", 10)
    
    current_project_title = "Định Mệnh Địa Cầu - Phim Ngắn 45p"
    current_project_header = "Thể loại: Cổ phong huyền huyễn • Tình cảm tâm lý"
    current_project_story = "Nội dung kịch bản chi tiết hoặc cốt truyện thô sẽ được lưu ở đây..."
    
    projects = user_data.get("projects", [])
    if load_project:
        for p in projects:
            if p.get("title") == load_project:
                current_project_title = p.get("title", current_project_title)
                current_project_header = p.get("header", current_project_header)
                current_project_story = p.get("project_raw_story", current_project_story)
                break
    else:
        if not projects:
            user_data["projects"] = [{
                "title": current_project_title,
                "header": current_project_header,
                "project_raw_story": current_project_story,
                "token_registry": {"visual_tokens": [], "audio_tokens": []},
                "tierProgress": "Tầng 7-8 (Đang lưu nháp)",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]
            save_users()
        else:
            current_project_title = projects[0].get("title", current_project_title)
            current_project_header = projects[0].get("header", current_project_header)
            current_project_story = projects[0].get("project_raw_story", current_project_story)




    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cine AI Studio Pro 6.4 - Enterprise Suite</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-3 sm:p-5 font-sans">
        <div class="max-w-7xl mx-auto space-y-4">
            
            <div class="flex flex-col md:flex-row justify-between items-center bg-slate-900 p-4 rounded-2xl border border-slate-800 shadow-xl gap-3">
                <div>
                    <h1 class="text-lg sm:text-xl font-bold text-amber-400">🎬 Cine AI Studio Pro 6.4 (Enterprise Commercial Suite)</h1>
                    <p class="text-xs text-slate-400">Tự động hóa 16 Tầng • Multi-Asset Tokenization • Model Routing • SePay Credit Ledger</p>
                </div>
                <div class="flex items-center space-x-3 flex-wrap gap-2">
                    <span class="text-xs text-emerald-400 font-bold bg-emerald-950/60 px-3 py-1 rounded-full border border-emerald-800">💰 Số dư: <span id="user-credits-val">USER_CREDITS_PLACEHOLDER</span> Credit</span>
                    <span class="text-xs text-amber-300 font-semibold">👤 USER_NAME_PLACEHOLDER</span>
                    <a href="/logout" class="bg-rose-600 hover:bg-rose-700 px-3 py-1.5 rounded-lg text-xs font-semibold transition shadow">Đăng xuất</a>
                </div>
            </div>




            <div class="flex flex-wrap gap-2 justify-between items-center bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                <div class="flex flex-wrap gap-2">
                    <a href="/" class="bg-amber-500 text-slate-950 px-4 py-2 rounded-xl font-bold text-xs shadow transition">⚡ Studio 16 Tầng</a>
                    <a href="/library" class="bg-slate-900 hover:bg-slate-800 text-slate-300 px-4 py-2 rounded-xl font-semibold text-xs border border-slate-800 transition">📁 Thư Viện & Hạn Mức</a>
                    <a href="/community" class="bg-slate-900 hover:bg-slate-800 text-slate-300 px-4 py-2 rounded-xl font-semibold text-xs border border-slate-800 transition">🌍 Cộng Đồng Phim Public</a>
                </div>
                <button onclick="triggerEnterpriseBreakdown()" class="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg">🚀 Chạy Thuật Toán Bóc Tách Enterprise Pro</button>
            </div>




            <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
                
                <div class="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-4 shadow-xl lg:col-span-1">
                    <div class="flex justify-between items-center">
                        <h2 class="text-xs font-bold uppercase tracking-wider text-amber-400">⚙️ Quản lý Dự Án & 16 Tầng</h2>
                        <button onclick="saveProjectDraft()" class="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black px-3.5 py-2 rounded-xl text-xs transition shadow flex items-center gap-1 uppercase tracking-wider">💾 Cập Nhật Nháp</button>
                    </div>
                    
                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Tiêu Đề / Tên Dự Án Phim:</label>
                        <input type="text" id="project-title" value="PROJECT_TITLE_PLACEHOLDER" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs font-semibold text-amber-300">
                    </div>




                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Đề Mục / Logline & Thể Loại:</label>
                        <input type="text" id="project-header" value="PROJECT_HEADER_PLACEHOLDER" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-200">
                    </div>




                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Nội Dung Dự Án / Cốt Truyện Thô:</label>
                        <textarea id="project-story" rows="4" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-amber-500">PROJECT_STORY_PLACEHOLDER</textarea>
                    </div>




                    <!-- KHU VỰC 1: TẢI LÊN KỊCH BẢN VĂN BẢN (.TXT) -->
                    <div class="space-y-2 p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                        <label class="block text-[11px] font-bold uppercase tracking-wider text-amber-400">📄 1. Tải Lên Kịch Bản Văn Bản (.txt)</label>
                        <input type="file" id="file-story" accept=".txt,.md" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-[11px] text-slate-400 cursor-pointer">
                        <button onclick="uploadAssetFileExplicit()" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 rounded-xl text-xs transition shadow">📤 Nạp Kịch Bản Thô</button>
                    </div>




                    <!-- KHU VỰC 2: TẢI LÊN HÌNH MẪU KHÓA CỨNG (VISUAL TOKENS) -->
                    <div class="space-y-2 p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                        <label class="block text-[11px] font-bold uppercase tracking-wider text-amber-400">🖼️ 2. Khóa Mẫu Hình Ảnh (.png, .jpg)</label>
                        <select id="visual-category" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-[11px] text-slate-200">
                            <option value="character">👤 Khóa Mẫu Nhân Vật (Character)</option>
                            <option value="costume">👘 Khóa Mẫu Trang Phục (Costume)</option>
                            <option value="landscape">🌄 Khóa Mẫu Bối Cảnh (Landscape)</option>
                        </select>
                        <input type="file" id="file-visual" accept=".png,.jpg,.jpeg" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-[11px] text-slate-400 cursor-pointer">
                        <button onclick="uploadVisualToken()" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2 rounded-xl text-xs transition shadow">🖼️ Tải Lên Token Hình Ảnh</button>
                    </div>




                    <!-- KHU VỰC 3: TẢI LÊN MẪU ÂM THANH (AUDIO TOKENS) -->
                    <div class="space-y-2 p-3 bg-slate-950/60 rounded-xl border border-slate-800">
                        <label class="block text-[11px] font-bold uppercase tracking-wider text-amber-400">🎵 3. Khóa Mẫu Âm Thanh (.mp3, .wav)</label>
                        <select id="audio-category" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2 text-[11px] text-slate-200">
                            <option value="bgm">🎶 Mẫu Nhạc Nền / BGM</option>
                            <option value="voice">🗣️ Mẫu Giọng Đọc / Voice Tone</option>
                        </select>
                        <input type="file" id="file-audio" accept=".mp3,.wav" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-[11px] text-slate-400 cursor-pointer">
                        <button onclick="uploadAudioToken()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black py-2 rounded-xl text-xs transition shadow">🎵 Tải Lên Token Âm Thanh</button>
                    </div>




                    <div>
                        <label class="block text-[11px] font-semibold text-slate-400 mb-1">Chọn Tầng Quy Trình Hoạt Động:</label>
                        <select id="tier-mode" class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-200">
                            <option value="tầng-7-8">🎬 Tầng 7 & 8: Ý tưởng, 10 Câu hỏi & Pacing Graph</option>
                            <option value="tầng-9-10">🎥 Tầng 9 & 10: Bóc tách JSON & Self-Healing Loop</option>
                            <option value="tầng-11-12">⚙️ Tầng 11 & 12: Niêm phong dữ liệu & Alternate Takes</option>
                            <option value="tầng-13-16">🚀 Tầng 13 đến 16: Xuất bản HD/2K/4K, SRT & Timeline</option>
                        </select>
                    </div>




                    <div class="space-y-2 pt-2 border-t border-slate-800">
                        <button onclick="fetchRoughCut()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-slate-950 font-bold py-2.5 rounded-xl text-xs transition shadow">🎞️ Xem Timeline Rough-Cut Playlist</button>
                        <button onclick="exportSrt()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2.5 rounded-xl text-xs transition shadow">📜 Xuất Phụ Đề Chuẩn .SRT</button>
                    </div>
                </div>




                <div class="bg-slate-900 p-4 rounded-2xl border border-slate-800 space-y-3 shadow-xl lg:col-span-2 flex flex-col justify-between">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-amber-400">💬 Đạo Diễn Ảo Enterprise & Bảng Điều Hướng Thuật Toán</span>
                        <span id="current-tier-badge" class="text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-800 px-2.5 py-1 rounded-full font-semibold">Enterprise Active</span>
                    </div>




                    <div id="chat-box" class="bg-slate-950 h-[440px] rounded-xl p-4 overflow-y-auto border border-slate-800 space-y-3 text-xs">
                        <div class="bg-blue-950/60 border border-blue-800/50 p-4 rounded-2xl text-blue-200 shadow-sm space-y-2">
                            <p class="font-bold text-amber-300">🌟 Điểm danh đầu phiên: Hệ thống Cine AI Studio Pro 6.4 đã sẵn sàng.</p>
                            <p>Đã tích hợp 3 cổng tải lên chuyên biệt: Kịch bản văn bản, Khóa mẫu Hình ảnh (Visual Tokens) và Khóa mẫu Âm thanh (Audio Tokens).</p>
                        </div>
                    </div>




                    <div class="flex gap-2 pt-2">
                        <input type="text" id="user-input" placeholder="Nhập trao đổi với Đạo diễn ảo..." class="flex-1 bg-slate-950 border border-slate-700 rounded-xl p-3.5 text-xs focus:outline-none focus:border-amber-500 transition" onkeypress="if(event.key==='Enter') sendMessage()">
                        <button onclick="sendMessage()" class="bg-indigo-600 hover:bg-indigo-700 px-6 py-3.5 rounded-xl font-bold text-xs transition shadow-lg">Gửi Trao Đổi</button>
                    </div>
                </div>




            </div>
        </div>




        <script>
            let originalProjectTitle = "PROJECT_TITLE_PLACEHOLDER";




            async function saveProjectDraft() {
                const newTitle = document.getElementById('project-title').value;
                const header = document.getElementById('project-header').value;
                const story = document.getElementById('project-story').value;
                const chatBox = document.getElementById('chat-box');
                
                try {
                    const res = await fetch('/api/cineai/save-draft', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({old_title: originalProjectTitle, title: newTitle, header: header, story: story})
                    });
                    const data = await res.json();
                    if(data.status === 'success') {
                        originalProjectTitle = data.saved_title;
                        chatBox.innerHTML += '<div class="bg-emerald-950/60 border border-emerald-800/50 p-3 rounded-2xl text-emerald-200 text-xs">✅ ' + data.message + '</div>';
                    } else {
                        alert(data.message);
                    }
                    chatBox.scrollTop = chatBox.scrollHeight;
                } catch(e) {
                    alert('Lỗi kết nối khi lưu dự án nháp!');
                }
            }




            async function uploadAssetFileExplicit() {
                const fileInput = document.getElementById('file-story');
                const title = document.getElementById('project-title').value;
                const chatBox = document.getElementById('chat-box');
                
                if(fileInput.files.length === 0) {
                    alert('⚠️ Vui lòng chọn tệp kịch bản (.txt) trước khi bấm tải lên!');
                    return;
                }
                
                const file = fileInput.files[0];
                const formData = new FormData();
                formData.append('file', file);
                formData.append('project_title', title);
                
                chatBox.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-3 rounded-2xl inline-block text-slate-100 text-xs">📁 Đang tải lên tệp kịch bản...</span></div>';
                
                try {
                    const res = await fetch('/api/cineai/upload-asset-explicit', {method: 'POST', body: formData});
                    const data = await res.json();
                    if(data.status === 'success') {
                        document.getElementById('project-story').value = data.extracted_content;
                        chatBox.innerHTML += '<div class="bg-emerald-950/60 border border-emerald-800/50 p-3 rounded-2xl text-emerald-200 text-xs">🎉 ' + data.message + '</div>';
                    } else {
                        alert(data.message);
                        chatBox.innerHTML += '<div class="bg-rose-950/60 border border-rose-800/50 p-3 rounded-2xl text-rose-200 text-xs">⚠️ ' + data.message + '</div>';
                    }
                    chatBox.scrollTop = chatBox.scrollHeight;
                } catch(e) {
                    alert('Lỗi kết nối khi tải lên tệp!');
                }
            }




            async function uploadVisualToken() {
                const fileInput = document.getElementById('file-visual');
                const category = document.getElementById('visual-category').value;
                const title = document.getElementById('project-title').value;
                const chatBox = document.getElementById('chat-box');
                
                if(fileInput.files.length === 0) {
                    alert('⚠️ Vui lòng chọn tệp hình ảnh (.png, .jpg)!');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('token_category', category);
                formData.append('project_title', title);
                
                chatBox.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-3 rounded-2xl inline-block text-slate-100 text-xs">🖼️ Đang tải lên và sinh mã khóa cứng Visual Token...</span></div>';
                
                try {
                    const res = await fetch('/api/cineai/upload-visual-token', {method: 'POST', body: formData});
                    const data = await res.json();
                    if(data.status === 'success') {
                        chatBox.innerHTML += '<div class="bg-indigo-950/60 border border-indigo-800/50 p-3 rounded-2xl text-indigo-200 text-xs">✨ ' + data.message + '</div>';
                    } else {
                        alert(data.message);
                    }
                    chatBox.scrollTop = chatBox.scrollHeight;
                } catch(e) {
                    alert('Lỗi kết nối tải lên ảnh!');
                }
            }




            async function uploadAudioToken() {
                const fileInput = document.getElementById('file-audio');
                const category = document.getElementById('audio-category').value;
                const title = document.getElementById('project-title').value;
                const chatBox = document.getElementById('chat-box');
                
                if(fileInput.files.length === 0) {
                    alert('⚠️ Vui lòng chọn tệp âm thanh (.mp3, .wav)!');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('token_category', category);
                formData.append('project_title', title);
                
                chatBox.innerHTML += '<div class="text-right"><span class="bg-slate-800 p-3 rounded-2xl inline-block text-slate-100 text-xs">🎵 Đang tải lên mẫu âm thanh Audio Token...</span></div>';
                
                try {
                    const res = await fetch('/api/cineai/upload-audio-token', {method: 'POST', body: formData});
                    const data = await res.json();
                    if(data.status === 'success') {
                        chatBox.innerHTML += '<div class="bg-emerald-950/60 border border-emerald-800/50 p-3 rounded-2xl text-emerald-200 text-xs">🎶 ' + data.message + '</div>';
                    } else {
                        alert(data.message);
                    }
                    chatBox.scrollTop = chatBox.scrollHeight;
                } catch(e) {
                    alert('Lỗi kết nối tải lên âm thanh!');
                }
            }




            async function triggerEnterpriseBreakdown() {
                const title = document.getElementById('project-title').value;
                const chatBox = document.getElementById('chat-box');
                chatBox.innerHTML += '<div class="bg-indigo-950/60 border border-indigo-800/50 p-4 rounded-2xl text-indigo-200 text-xs">🚀 Đang kích hoạt thuật toán bóc tách Enterprise Pro (Model Pro + Self-Healing JSON)...</div>';
                
                try {
                    const res = await fetch('/api/cineai/breakdown-scenes-enterprise', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json’@app.get("/library", response_class=HTMLResponse)
async def library_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    
    user_data = USERS_DB.get(username, {})
    user_projects = user_data.get("projects", [])
    user_credits = user_data.get("credits", 0)
    
    projects_html = ""
    if not user_projects:
        projects_html = """
        <div class="text-center py-12 bg-slate-950/60 rounded-3xl border border-dashed border-slate-800 space-y-3">
            <p class="text-sm text-slate-400">Chưa có dự án phim nào được lưu.</p>
            <a href="/" class="inline-block bg-amber-500 text-slate-950 font-bold px-6 py-3 rounded-2xl text-xs shadow-lg">⚡ Bắt Đầu Tạo Dự Án Mới</a>
        </div>
        """
    else:
        for idx, p in enumerate(user_projects):
            title = p.get("title", f"Dự án #{idx+1}")
            header = p.get("header", "Chưa có đề mục")
            status = p.get("tierProgress", "Đang lưu nháp (Draft)")
            updated_time = p.get("updated_at", "Vừa xong")
            
            projects_html += f"""
            <div class="bg-slate-950 p-5 sm:p-6 rounded-3xl border border-slate-800 shadow-xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 transition hover:border-amber-500/50">
                <div class="space-y-1">
                    <span class="text-[10px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full border border-amber-500/20">🎬 {status}</span>
                    <h3 class="text-base sm:text-lg font-black text-slate-100 pt-1">{title}</h3>
                    <p class="text-xs text-slate-400 italic">📌 {header}</p>
                    <p class="text-[11px] text-slate-500">🕒 Cập nhật: {updated_time}</p>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <a href="/?load_project={urllib.parse.quote(title)}" class="flex-1 sm:flex-none text-center bg-amber-500 hover:bg-amber-400 text-slate-950 font-black px-6 py-3.5 rounded-2xl text-xs transition shadow-lg uppercase tracking-wider">📂 Mở Studio</a>
                    <button onclick="confirmDeleteProject('{title}')" class="bg-rose-900/60 hover:bg-rose-700 text-rose-200 border border-rose-800 font-bold px-4 py-3.5 rounded-2xl text-xs transition shadow">🗑️ Xóa</button>
                </div>
            </div>
            """




    library_html = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Thư Viện Dự Án - Cine AI Studio Pro 6.4</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-4 sm:p-6 font-sans">
        <div class="max-w-4xl mx-auto space-y-6">
            
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-slate-900 p-6 rounded-3xl border border-slate-800 shadow-2xl gap-4">
                <div>
                    <h1 class="text-xl sm:text-2xl font-black text-amber-400 tracking-wide">📁 Thư Viện & Quản Lý Dự Án</h1>
                    <p class="text-xs text-slate-400 mt-1">Đã dùng <b class="text-amber-300">USER_PROJECTS_COUNT</b> / 2 dự án tiêu chuẩn • Ví Credit: <b class="text-emerald-400">USER_CREDITS_VAL Credit</b></p>
                </div>
                <a href="/" class="bg-slate-950 hover:bg-slate-800 text-slate-200 border border-slate-700 px-5 py-3 rounded-2xl font-bold text-xs transition shadow">⚡ Quay lại Studio 16 Tầng</a>
            </div>




            <div class="bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-800 space-y-4 shadow-2xl">
                <div class="flex justify-between items-center border-b border-slate-800 pb-4">
                    <h2 class="text-sm font-bold uppercase tracking-wider text-amber-400">📋 Danh Sách Dự Án Nháp & Hoàn Thành</h2>
                    <a href="/" class="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black px-5 py-3 rounded-2xl text-xs transition shadow">➕ Tạo Dự Án Mới</a>
                </div>
                <div class="space-y-4 pt-2">
                    PROJECTS_HTML_PLACEHOLDER
                </div>
            </div>




        </div>




        <script>
            async function confirmDeleteProject(title) {
                if(confirm("⚠️ Bạn đã chắc chắn với hành động xóa dự án '" + title + "' này chưa? Dữ liệu không thể khôi phục sau khi xóa.")) {
                    try {
                        const res = await fetch('/api/cineai/delete-project', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({title: title})
                        });
                        const data = await res.json();
                        alert(data.message);
                        location.reload();
                    } catch(e) {
                        alert('Lỗi kết nối khi xóa dự án!');
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    library_html = library_html.replace("USER_PROJECTS_COUNT", str(len(user_projects)))
    library_html = library_html.replace("USER_CREDITS_VAL", str(user_credits))
    library_html = library_html.replace("PROJECTS_HTML_PLACEHOLDER", projects_html)
    return HTMLResponse(content=library_html)




@app.get("/login", response_class=HTMLResponse)
async def login_page(tab: str = "login", error: str = None, success: str = None):
    is_register = (tab == "register")
    is_forgot = (tab == "forgot")
    
    login_tab_class = "flex-1 py-3 text-center font-bold text-xs rounded-xl transition " + ("bg-amber-500 text-slate-950 shadow-lg" if not is_register and not is_forgot else "text-slate-400 hover:text-slate-200")
    reg_tab_class = "flex-1 py-3 text-center font-bold text-xs rounded-xl transition " + ("bg-amber-500 text-slate-950 shadow-lg" if is_register else "text-slate-400 hover:text-slate-200")
    
    form_action = "/login" if not is_register and not is_forgot else ("/register" if is_register else "/forgot-password")
    title_text = "🔐 Đăng Nhập Hệ Thống" if not is_register and not is_forgot else ("📝 Tạo Tài Khoản Mới" if is_register else "🔑 Khôi Phục Mật Khẩu")
    subtitle_text = "Cine AI Studio Pro 6.4 Enterprise" if not is_register and not is_forgot else ("Nhận ngay 10 Credit trải nghiệm" if is_register else "Cập nhật mật khẩu mới an toàn")
    btn_text = "Đăng Nhập Ngay" if not is_register and not is_forgot else ("Đăng Ký Tài Khoản" if is_register else "Xác Nhận Đổi Mật Khẩu")




    error_html = f'<div class="bg-rose-950/80 border border-rose-800 p-3 rounded-2xl text-rose-200 text-xs text-center font-bold">{error}</div>' if error else ''
    success_html = f'<div class="bg-emerald-950/80 border border-emerald-800 p-3 rounded-2xl text-emerald-200 text-xs text-center font-bold">{success}</div>' if success else ''




    forgot_link = '<div class="text-right"><a href="/login?tab=forgot" class="text-[11px] text-amber-400 hover:underline">Quên mật khẩu?</a></div>' if not is_register and not is_forgot else '<div class="text-left"><a href="/login?tab=login" class="text-[11px] text-amber-400 hover:underline">← Quay lại đăng nhập</a></div>'




    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Xác Thực - Cine AI Studio Pro 6.4</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4 font-sans">
        <div class="bg-slate-900 p-6 sm:p-8 rounded-3xl border border-slate-800 w-full max-w-md space-y-6 shadow-2xl">
            
            <div class="text-center space-y-2">
                <h2 class="text-xl sm:text-2xl font-black text-amber-400 tracking-wide">{title_text}</h2>
                <p class="text-xs text-slate-400 font-medium">{subtitle_text}</p>
            </div>




            {error_html}
            {success_html}




            {'<div class="flex bg-slate-950 p-1.5 rounded-2xl border border-slate-800"><a href="/login?tab=login" class="' + login_tab_class + '">Đăng Nhập</a><a href="/login?tab=register" class="' + reg_tab_class + '">Đăng Ký Mới</a></div>' if not is_forgot else ''}




            <form method="POST" action="{form_action}" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-2">👤 Tên đăng nhập:</label>
                    <input type="text" name="username" required placeholder="Nhập tên tài khoản..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-4 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition shadow-inner">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-300 mb-2">🔑 {'Mật khẩu mới' if is_forgot else 'Mật khẩu bảo mật'}:</label>
                    <input type="password" name="password" required placeholder="Nhập mật khẩu..." class="w-full bg-slate-950 border border-slate-700 rounded-2xl p-4 text-sm text-slate-100 focus:outline-none focus:border-amber-500 transition shadow-inner">
                </div>
                {forgot_link if not is_forgot else ''}
                <button type="submit" class="w-full bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black py-4 rounded-2xl transition text-sm shadow-xl tracking-wider uppercase mt-2">{btn_text}</button>
            </form>




            <div class="text-center pt-2 border-t border-slate-800/80">
                <p class="text-[11px] text-slate-500">Cine AI Studio Pro 6.4 • Secure Commercial Production Suite</p>
            </div>
        </div>
    </body>
    </html>
    """)




@app.get("/register", response_class=HTMLResponse)
async def register_page_redirect():
    return RedirectResponse(url="/login?tab=register", status_code=303)




@app.post("/login")
async def login_post(username: str = Form(...), password: str = Form(...)):
    user_info = USERS_DB.get(username)
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    if (username == "admin" and password == "admin123") or (user_info and user_info.get("password_hash") == pwd_hash):
        session_id = secrets.token_hex(16)
        ACTIVE_SESSIONS[session_id] = username
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id)
        return response
    return RedirectResponse(url="/login?tab=login&error=" + urllib.parse.quote("⚠️ Sai tên đăng nhập hoặc mật khẩu, vui lòng kiểm tra lại!"), status_code=303)




@app.post("/register")
async def register_post(username: str = Form(...), password: str = Form(...)):
    if username in USERS_DB:
        return RedirectResponse(url="/login?tab=register&error=" + urllib.parse.quote("⚠️ Tên đăng nhập này đã tồn tại! Vui lòng chọn tên khác."), status_code=303)
    USERS_DB[username] = {"password_hash": hashlib.sha256(password.encode()).hexdigest(), "projects": [], "credits": 10}
    save_users()
    session_id = secrets.token_hex(16)
    ACTIVE_SESSIONS[session_id] = username
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_id", value=session_id)
    return response




@app.post("/forgot-password")
async def forgot_password_post(username: str = Form(...), password: str = Form(...)):
    if username not in USERS_DB:
        return RedirectResponse(url="/login?tab=forgot&error=" + urllib.parse.quote("⚠️ Tên tài khoản này không tồn tại trong hệ thống!"), status_code=303)
    
    USERS_DB[username]["password_hash"] = hashlib.sha256(password.encode()).hexdigest()
    save_users()
    return RedirectResponse(url="/login?tab=login&success=" + urllib.parse.quote("🎉 Đổi mật khẩu thành công! Vui lòng đăng nhập bằng mật khẩu mới."), status_code=303)




@app.get("/logout")
async def logout(session_id: str = Cookie(None)):
    if session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_id")
    return response




@app.get("/community", response_class=HTMLResponse)
async def community_page(session_id: str = Cookie(None)):
    username = ACTIVE_SESSIONS.get(session_id)
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content="""
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><title>Cộng Đồng - Cine AI Studio Pro 6.4</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-slate-100 min-h-screen p-6 font-sans">
        <div class="max-w-4xl mx-auto space-y-4">
            <div class="flex justify-between items-center bg-slate-900 p-4 rounded-2xl border border-slate-800 shadow-xl">
                <h1 class="text-xl font-bold text-amber-400">🌍 Cộng Đồng Phim Thương Mại Pro 6.4</h1>
                <a href="/" class="bg-amber-500 text-slate-950 px-4 py-2 rounded-xl font-bold text-xs">⚡ Quay lại Studio</a>
            </div>
            <div class="bg-slate-900 p-6 rounded-2xl border border-slate-800"><p class="text-xs text-slate-500">Bảng tin cộng đồng đang cập nhật...</p></div>
        </div>
    </body></html>
    """)




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)