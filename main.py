import base64
import requests
import io
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ضعي الـ OpenAI API Key هنا (من https://platform.openai.com/api-keys)
OPENAI_API_KEY = "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"  # غيّري ده بالكي الجديد بتاعك

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

def process_image(image_path, query):
    try:
        # قراءة وتشفير الصورة
        with open(image_path, "rb") as image_file:
            image_content = image_file.read()

        encoded_image = base64.b64encode(image_content).decode("utf-8")

        # التحقق من صلاحية الصورة
        try:
            img = Image.open(io.BytesIO(image_content))
            img.verify()
        except Exception as e:
            logger.error(f"Invalid image format: {str(e)}")
            return {"error": f"الصورة تالفة أو غير مدعومة: {str(e)}"}

        # إعداد الرسالة لـ GPT-4o-mini (يدعم الصور تمام)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]
            }
        ]

        # طلب واحد بس من GPT-4o-mini (سريع ودقيق)
        try:
            response = requests.post(
                OPENAI_API_URL,
                json={
                    "model": "gpt-4o-mini",  # أفضل موديل Vision رخيص وسريع
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7
                },
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    answer = data["choices"][0]["message"]["content"].strip()
                    logger.info("GPT-4o-mini answered successfully")
                    return {"gpt4o": answer}  # رد واحد بس عشان البساطة
                else:
                    return {"error": "الموديل رد بس مفيش إجابة واضحة"}
            else:
                error_msg = response.text[:200]
                return {"error": f"فشل الاتصال ({response.status_code}): {error_msg}"}

        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            return {"error": f"خطأ في الاتصال: {str(e)}"}

    except FileNotFoundError:
        return {"error": "الصورة مش موجودة! تأكدي من اسم الملف والمسار"}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return {"error": f"حصل خطأ غير متوقع: {str(e)}"}


# === تشغيل الاختبار ===
if __name__ == "__main__":
    image_path = "test1.png"   # غيّري لو اسم الصورة مختلف
    query = "اشرح لي بالعربي إيه اللي في الصورة دي بالتفصيل؟"  # غيّري السؤال زي ما تحبي

    print("جاري تحليل الصورة بـ GPT-4o-mini... انتظري شوية")
    result = process_image(image_path, query)
    
    print("\n" + "="*60)
    for model, answer in result.items():
        print(f"\n【 {model.upper()} 】\n{answer}")
    print("="*60)