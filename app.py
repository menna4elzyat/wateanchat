import json
import base64
import requests
import io
import logging
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI()

# تحميل الأطباء مرة واحدة بس
try:
    with open("doctors.json", "r", encoding="utf-8") as f:
        DOCTORS = json.load(f)["doctors"]
    logger.info(f"تم تحميل {len(DOCTORS)} دكتور من doctors.json")
except Exception as e:
    logger.error("مشكلة في doctors.json → " + str(e))
    DOCTORS = []

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# البحث السريع جدًا في الأطباء
def get_doctor(query: str):
    q = query.lower().replace("ة", "ه").replace("ى", "ي")
    triggers = ["مواعيد","موعد","حجز","كشف","دكتور","دكتوره","دكتورة","نسا","اسنان","جلديه","عظام","اطفال","دايت","سكر","دوالي","ليزر","تجميل","انف واذن","مخ واعصاب","تغذيه","نحافه","رجيم","حمل","توليد"]
    if not any(t in q for t in triggers):
        return None
    for doc in DOCTORS:
        if (doc["name"].lower() in q or 
            doc["full_name"].lower() in q or 
            doc["specialty"].lower() in q or 
            q in doc["specialty"].lower()):
            return doc
    return None

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>عيادة وتين - الحجز الذكي</title>
        <style>
            body {font-family:'Cairo',sans-serif;background:linear-gradient(135deg,#e3f2fd,#bbdefb);margin:0;padding:20px}
            .c {max-width:700px;margin:auto;background:white;padding:35px;border-radius:25px;box-shadow:0 15px 50px rgba(0,0,0,.15)}
            h1 {text-align:center;color:#1976d2;margin-bottom:10px}
            input,button {padding:16px;border-radius:14px;border:2px solid #ddd;width:100%;margin:12px 0;font-size:18px;box-sizing:border-box}
            button {background:#1976d2;color:white;font-weight:bold;cursor:pointer}
            button:hover {background:#1565c0}
            .r {padding:25px;border-radius:18px;margin-top:20px;font-size:19px;line-height:2;display:none}
            .db {background:#e8f5e8;border:3px solid #4caf50}
            .ai {background:#fff3e0;border:3px solid #ff9800}
            .err {background:#ffebee;border:3px solid #f44336;color:#c62828}
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="c">
            <h1>عيادة وتين الطبية</h1>
            <p style="text-align:center;color:#555">اكتب اسم الدكتور أو التخصص أو ارفع أشعة</p>
            <form id="chatForm" enctype="multipart/form-data">
                <input type="file" name="image" accept="image/*"><br>
                <input type="text" name="query" placeholder="مثلاً: دكتوره نسا • اسنان • جلدية التجمع • مواعيد كريم" required><br>
                <button type="submit">إرسال</button>
            </form>
            <div id="response" class="r"></div>
        </div>

        <script>
        document.getElementById('chatForm').onsubmit = async e => {
            e.preventDefault();
            const fd = new FormData(e.target);
            const div = document.getElementById('response');
            div.style.display = 'block';
            div.className = 'r';
            div.innerHTML = 'جاري التحميل...';

            try {
                const res = await fetch('/upload_and_query', {method:'POST', body:fd});
                if (!res.ok) {
                    const txt = await res.text();
                    throw new Error(`خطأ ${res.status}: ${txt.slice(0,150)}`);
                }
                const data = await res.json();
                if (data.from_db) {
                    div.className = 'r db';
                    div.innerHTML = data.response;
                } else {
                    div.className = 'r ai';
                    div.innerHTML = `<strong>الذكاء الاصطناعي قال (${data.model||'Llama'}):</strong><br>${data.response.replace(/\\n/g,'<br>')}`;
                }
            } catch (err) {
                console.error(err);
                div.className = 'r err';
                div.innerHTML = `<p>حدث خطأ: ${err.message}</p>`;
            }
        };
        </script>
    </body>
    </html>
    """

@app.post("/upload_and_query")
async def upload_and_query(image: UploadFile = File(None), query: str = Form(...)):
    user_query = query.strip()

    # أول حاجة: لو السؤال عن حجز أو دكتور → JSON فورًا
    doctor = get_doctor(user_query)
    if doctor:
        days = "، ".join(doctor["days"])
        html = f"""
        <div style="background:#e8f5e8;padding:30px;border-radius:20px;border:4px solid #4caf50;text-align:center;font-size:20px;line-height:2.2;">
            <h2 style="color:#1976d2;margin:0 0 20px 0;">{doctor['full_name']}</h2>
            <p><strong>التخصص:</strong> {doctor['specialty']}</p>
            <p><strong>أيام الكشف:</strong> {days}</p>
            <p><strong>المواعيد:</strong> {doctor['from']} → {doctor['to']}</p>
            <p><strong>الفرع:</strong> {doctor['location']}</p>
            <p style="font-size:28px;color:#25d366;margin:20px 0"><strong>{doctor['phone']}</strong></p>
            <a href="https://wa.me/2{doctor['phone']}" 
               style="background:#25d366;color:white;padding:18px 60px;border-radius:16px;text-decoration:none;font-weight:bold;font-size:22px;">
               حجز واتساب فوري
            </a>
        </div>
        """
        return {"response": html, "from_db": True}

    # لو مفيش دكتور → يروح للـ AI
    try:
        if image and image.filename:
            # GPT-4o Vision
            content = await image.read()
            b64 = base64.b64encode(content).decode()
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"بالعربي المصري: {user_query}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }],
                "max_tokens": 1000
            }
            r = requests.post("https://api.openai.com/v1/chat/completions",
                              json=payload,
                              headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                              timeout=90)
            r.raise_for_status()
            ans = r.json()["choices"][0]["message"]["content"]
            return {"response": ans, "model": "GPT-4o-mini"}

        else:
            # Groq Llama 3.3
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": f"جاوب بالعربي المصري: {user_query}"}],
                "temperature": 0.7,
                "max_tokens": 1024
            }
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              json=payload,
                              headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                              timeout=40)
            r.raise_for_status()
            ans = r.json()["choices"][0]["message"]["content"]
            return {"response": ans, "model": "Llama-3.3-70B"}

    except Exception as e:
        logger.error(str(e))
        return {"response": f"عذرًا حصل مشكلة مؤقتة: {str(e)[:100]}", "model": "خطأ"}

# معالجة أي خطأ في السيرفر → رد JSON دايمًا
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "خطأ داخلي", "detail": str(exc)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)




