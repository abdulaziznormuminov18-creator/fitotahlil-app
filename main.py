import os
import time
import base64
import threading

import telebot
from telebot import types
from groq import Groq
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_cors import CORS


# =========================
# SOZLAMALAR
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Render Variables yoki .env faylni tekshiring."
    )

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY topilmadi. Render Variables yoki .env faylni tekshiring."
    )


# =========================
# OBYEKTLAR
# =========================

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)
CORS(app)


WEB_APP_URL = (
    "https://abdulaziznormuminov18-creator.github.io/"
    "fitotahlil-app/"
)


# =========================
# UMUMIY AI TAHLIL FUNKSIYASI
# =========================

def analyze_image(image_bytes):
    """
    Rasmni Groq AI orqali tahlil qiladi
    va matn ko'rinishida natija qaytaradi.
    """

    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Siz professional agronom va fitopatologsiz.
Berilgan o'simlik rasmini tahlil qiling.

Javobni o'zbek tilida, sodda va amaliy tarzda yozing.
Quyidagi tartibdan foydalaning:

1. O'simlik nomi:
   O'zbekcha va lotincha nomi.

2. Umumiy holati:
   Sog'lom, zararlangan yoki xavf ostida.

3. Tashxis:
   Ko'rinayotgan muammo va ehtimoliy sabab.

4. Ishonchlilik:
   Taxminiy foizda ko'rsating.
   Agar rasm sifati past bo'lsa, buni ayting.

5. Suv tavsiyasi:
   Qachon va qancha sug'orish kerak.

6. Yorug'lik va harorat:
   O'simlikka mos sharoit.

7. Davolash:
   Zarur bo'lsa, qanday parvarish yoki vosita kerakligi.

8. Qayta tekshirish:
   Necha kundan keyin yana rasmga olish kerakligi.

Javobning oxirida:
"Bu dastlabki AI tahlilidir. Jiddiy holatlarda agronom bilan maslahatlashish tavsiya etiladi."
deb yozing.
"""

    completion = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                f"{base64_image}"
                            )
                        }
                    }
                ]
            }
        ],
        temperature=0.2,
        max_completion_tokens=1024,
        reasoning_effort="none",
        reasoning_format="hidden"
    )

    result = completion.choices[0].message.content

    if not result:
        raise RuntimeError("AI bo'sh javob qaytardi.")

    return result


# =========================
# MINI APP API
# =========================

@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "FitoTahlil AI API ishlayapti"
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy"
    })


@app.post("/api/analyze")
def analyze_from_mini_app():
    """
    Mini App rasmni multipart/form-data orqali yuboradi.
    Field nomi: image
    """

    try:
        if "image" not in request.files:
            return jsonify({
                "success": False,
                "error": "Rasm topilmadi."
            }), 400

        image = request.files["image"]

        if not image.filename:
            return jsonify({
                "success": False,
                "error": "Rasm fayli tanlanmagan."
            }), 400

        image_bytes = image.read()

        if not image_bytes:
            return jsonify({
                "success": False,
                "error": "Rasm bo'sh."
            }), 400

        # 10 MB dan katta fayllarni qabul qilmaymiz
        if len(image_bytes) > 10 * 1024 * 1024:
            return jsonify({
                "success": False,
                "error": "Rasm hajmi 10 MB dan oshmasligi kerak."
            }), 413

        ai_result = analyze_image(image_bytes)

        return jsonify({
            "success": True,
            "result": ai_result
        })

    except Exception as error:
        print("Mini App API xatoligi:", repr(error))

        return jsonify({
            "success": False,
            "error": (
                "Tahlil vaqtida xatolik yuz berdi. "
                "Iltimos, rasmni qayta yuboring."
            )
        }), 500


# =========================
# TELEGRAM BOT
# =========================

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()

    app_button = types.InlineKeyboardButton(
        text="🌿 FitoTahlil AI ilovasini ochish",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )

    markup.add(app_button)

    welcome_text = (
        "🌿 FitoTahlil AI botiga xush kelibsiz!\n\n"
        "O'simlik rasmini Mini App ichida tahlil qilish "
        "uchun quyidagi tugmani bosing:"
    )

    bot.send_message(
        chat_id=message.chat.id,
        text=welcome_text,
        reply_markup=markup
    )


@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_data(message):
    bot.send_message(
        message.chat.id,
        "✅ Ilova muvaffaqiyatli ulandi. "
        "Tahlilni Mini App ichida davom ettiring."
    )


@bot.message_handler(content_types=["photo"])
def handle_telegram_photo(message):
    status_message = bot.reply_to(
        message,
        "⏳ Rasm tahlil qilinmoqda...\n"
        "Iltimos, biroz kuting."
    )

    try:
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        image_bytes = bot.download_file(file_info.file_path)

        ai_result = analyze_image(image_bytes)

        result_text = (
            "📋 FITOTAHLIL NATIJASI\n\n"
            f"{ai_result}"
        )

        # Markdown ishlatilmayapti, parse xatosi chiqmaydi
        bot.edit_message_text(
            text=result_text,
            chat_id=message.chat.id,
            message_id=status_message.message_id
        )

    except Exception as error:
        print("Telegram rasm tahlili xatoligi:", repr(error))

        bot.edit_message_text(
            text=(
                "⚠️ Rasmni tahlil qilishda xatolik yuz berdi.\n"
                "Iltimos, rasmni qayta yuboring."
            ),
            chat_id=message.chat.id,
            message_id=status_message.message_id
        )


def run_telegram_bot():
    """
    Telegram polling alohida thread'da ishlaydi.
    """

    try:
        print("Eski Telegram webhook o'chirilmoqda...")
        bot.delete_webhook(drop_pending_updates=True)

        print("Telegram bot ishga tushdi...")

        bot.infinity_polling(
            timeout=30,
            long_polling_timeout=30
        )

    except Exception as error:
        print("Telegram bot xatoligi:", repr(error))


# =========================
# ISHGA TUSHIRISH
# =========================

if __name__ == "__main__":
    bot_thread = threading.Thread(
        target=run_telegram_bot,
        daemon=True
    )

    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))

    print(f"FitoTahlil API {port}-portda ishga tushdi...")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
