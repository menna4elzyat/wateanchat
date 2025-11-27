import json
import os
import base64
import requests
import io
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from PIL import Image
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI()

# تحميل بيانات الأطباء من JSON
DOCTORS_DATA = {"doctors": []}
try:
    with open("doctors.json", "r", encoding="utf-8") as f:
        DOCTORS_DATA = json.load(f)
    logger.info("تم تحميل بيانات الأطباء من doctors.json")
except FileNotFoundError:
    logger.warning("ملف doctors.json مش موجود، هيشتغل بدون مواعيد الأطباء")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# دالة البحث عن الدكتور في الـ JSON
def find_doctor_in_db(query: str):
    q = query.lower().strip().replace("ة", "ه")  # عشان "جلدية" = "جلديه"

    # قاموس الكلمات المفتاحية لكل تخصص (مضبوط على 10 دكاترة اللي عملناهم)
    keywords = {
        "أسنان": ["أسنان", "اسنان", "دكتور اسنان", "دكتور أسنان", "تنظيف", "حشو", "تقويم", "زراعة", "تركيبات", "زرع", "ضرس", "ابتسامة", "تبييض"],
        "جلدية وتجميل": ["جلدية", "جلديه", "تجميل", "ليزر", "بوتوكس", "فيلر", "دكتورة جلدية", "دكتور جلدية", "دكتوره جلديه", "هيدرافيشيال", "بلازما"],
        "عظام": ["عظام", "عظم", "مفاصل", "كسور", "دكتور عظام", "خشونة", "غضاريف", "ركبة", "كتف", "ظهر"],
        "نساء وتوليد": ["نسا", "نساء", "توليد", "حمل", "متابعة حمل", "دكتورة نسا", "دكتوره نسا", "سونار", "حوامل"],
        "أطفال": ["أطفال", "اطفال", "باطنة اطفال", "دكتور اطفال", "برد اطفال", "لقاحات", "تطعيمات"],
        "أنف وأذن وحنجرة": ["أنف وأذن", "انف واذن", "اذن", "حنجرة", "سماعات", "دكتور انف واذن", "زكام", "لوز"],
        "مخ وأعصاب": ["مخ واعصاب", "اعصاب", "صداع", "دوخه", "دوار", "نوبات", "صرع", "دكتور مخ واعصاب"],
        "باطنة وسكر": ["باطنه", "سكر", "ضغط", "غدد", "دكتورة باطنة", "سكري", "هرمونات"],
        "جراحة عامة وليزر دوالي": ["دوالي", "جراحة", "ليزر دوالي", "جراح", "فتاق", "مرارة"],
        "تغذية علاجية ونحافة": ["دايت", "نحافة", "زيادة وزن", "تغذية", "رجيم", "دكتورة دايت", "دكتوره تغذيه"]
    }

    for doc in DOCTORS_DATA.get("doctors", []):
        doc_spec = doc.get("specialty", "")

        # 1. لو ذكر اسم الدكتور بالظبط
        if any(part in q for part in doc.get("name", "").lower().split() + doc.get("full_name", "").lower().split()):
            return doc

        # 2. لو سأل بالتخصص (الأهم)
        for spec_key, words in keywords.items():
            if doc_spec == spec_key and any(word in q for word in words):
                return doc

    return None
    for doc in DOCTORS_DATA.get("doctors", []):
        doc_name = doc.get("name", "").lower()
        doc_full = doc.get("full_name", "").lower()
        doc_spec = doc.get("specialty", "").lower()

        # لو ذكر اسم الدكتور صراحة
        if any(word in q for word in [doc_name, doc_full]):
            return doc

        # لو سأل بالتخصص فقط (أهم حاجة)
        for spec_ar, words in keywords.items():
            if doc_spec == spec_ar and any(word in q for word in words):
                return doc

    return None  # لو مفيش تطابق خالص

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>الدكتور الذكي - عيادة وتين</title>
        <style>
            body { font-family: 'Cairo', sans-serif; background: linear-gradient(135deg, #e3f2fd, #bbdefb); margin:0; padding:20px; }
            .container { max-width:650px; margin:auto; background:white; padding:30px; border-radius:20px; box-shadow:0 15px 40px rgba(0,0,0,0.15); }
            h1 { text-align:center; color:#1976d2; }
            input, button { padding:15px; margin:10px 0; width:100%; border-radius:12px; border:2px solid #ddd; font-size:17px; }
            button { background:#1976d2; color:white; border:none; cursor:pointer; font-weight:bold; }
            button:hover { background:#1565c0; }
            .response { margin-top:25px; padding:20px; border-radius:12px; display:none; font-size:18px; line-height:1.8; }
            .from-db { background:#e8f5e8; border:2px solid #4caf50; }
            .from-ai { background:#fff3e0; border:2px solid #ff9800; }
            .error { background:#ffebee; border:2px solid #f44336; }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="container">
            <h1>الدكتور الذكي - عيادة وتين</h1>
            <p style="text-align:center;">اسأل عن مواعيد الدكاترة أو ارفع أشعة أو وصف أعراضك</p>
            
            <form id="chatForm" enctype="multipart/form-data">
                <input type="file" name="image" accept="image/*"><br>
                <input type="text" name="query" placeholder="مثلاً: مواعيد دكتور أحمد محمد؟ أو أشعة صدر" required><br>
                <button type="submit">إرسال</button>
            </form>
            
            <div id="response" class="response"></div>
        </div>

        <script>
            document.getElementById('chatForm').onsubmit = async (e) => {
                e.preventDefault();
                const fd = new FormData(e.target);
                const div = document.getElementById('response');
                div.style.display = 'block';
                div.className = 'response';
                div.innerHTML = 'جاري البحث والتحليل...';

                try {
                    const res = await fetch('/upload_and_query', {method:'POST', body:fd});
                    const data = await res.json();
                    if (data.error) {
                        div.className += ' error';
                        div.innerHTML = `<p>خطأ: ${data.error}</p>`;
                    } else if (data.from_db) {
                        div.className += ' from-db';
                        div.innerHTML = data.response;
                    } else {
                        div.className += ' from-ai';
                        div.innerHTML = `<strong>الذكاء الاصطناعي قال (${data.model}):</strong><br>${data.response.replace(/\\n/g, '<br>')}`;
                    }
                } catch (err) {
                    div.className += ' error';
                    div.innerHTML = `<p>مشكلة في الاتصال: ${err.message}</p>`;
                }
            };
        </script>
    </body>
    </html>
    """

@app.post("/upload_and_query")
async def upload_and_query(image: UploadFile = File(None), query: str = Form(...)):
    user_query = query.strip()
    q = user_query.lower().replace("ة", "ه").replace("ى", "ي")

    # القائمة القاتلة – أي كلمة من دول = رد من الـ JSON فورًا
    triggers = ["مواعيد","موعد","حجز","كشف","دكتور","دكتوره","دكتورة",
                "نسا","نساء","توليد","حمل","اسنان","أسنان","جلديه","جلدية",
                "تجميل","ليزر","عظام","اطفال","أطفال","دايت","سكر","دوالي",
                "انف واذن","مخ واعصاب","تغذيه","نحافه","رجيم"]

    if any(t in q for t in triggers):
        doctor = get_doctor(user_query)  # الدالة اللي فوق في الكود الجديد
        if doctor:
            days = "، ".join(doctor["days"])
            html = f"""
            <div style="background:#e8f5e8;padding:25px;border-radius:18px;border:3px solid #4caf50;text-align:center;font-size:19px;line-height:2;">
                <h2 style="color:#1976d2;margin:0 0 15px 0;">{doctor['full_name']}</h2>
                <p><strong>التخصص:</strong> {doctor['specialty']}</p>
                <p><strong>أيام الكشف:</strong> {days}</p>
                <p><strong>المواعيد:</strong> {doctor['from']} → {doctor['to']}</p>
                <p><strong>الفرع:</strong> {doctor['location']}</p>
                <p style="margin:15px 0;font-size:24px;color:#25d366"><strong>{doctor['phone']}</strong></p>
                <a href="https://wa.me/2{doctor['phone']}" 
                   style="background:#25d366;color:white;padding:16px 50px;border-radius:15px;text-decoration:none;font-weight:bold;font-size:20px;">
                   حجز واتساب فوري
                </a>
            </div>
            """
            return {"response": html, "from_db": True}

        # لو الدكتور مش عندنا
        return {"response": "<p style='color:#d32f2f;font-size:20px;text-align:center;'>عذرًا، الدكتور/ة ده مش موجودين حاليًا في عيادة وتين 🏥<br>جرب تخصص تاني أو ارفع أشعة وأنا أساعدك</p>", "from_db": True}

    # لو مفيش ولا كلمة حجز خالص → يروح للـ AI (أشعة أو أسئلة عامة)
    # هنا حط كود الـ Vision و Groq اللي عندك أصلًا (مش محتاج تغيره)
    # مثال سريع:
    try:
        if image and image.filename:
            # كود الـ Vision بتاعك القديم
            return {"response": "تحليل الصورة...", "model": "GPT-4o-mini"}
        else:
            # كود Groq بتاعك القديم
            return {"response": "سؤالك وصل للذكاء الاصطناعي", "model": "Llama-3.3-70B"}
    except:
        return {"response": "في مشكلة مؤقتة، جرب تاني بعد شوية"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



