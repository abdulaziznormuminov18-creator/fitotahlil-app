import os
import time
import base64
import telebot
from groq import Groq
from dotenv import load_dotenv

load_dotenv()  # Lokalda .env fayldan o'qiydi; Railway'da bu qatorning ta'siri yo'q (u o'zining env-varlaridan oladi)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN or not GROQ_API_KEY:
    raise RuntimeError("BOT_TOKEN yoki GROQ_API_KEY topilmadi. .env faylni yoki Railway Variables'ni tekshiring.")

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()

    web_app = telebot.types.WebAppInfo(
        url="https://abdulaziznormuminov18-creator.github.io/fitotahlil-app/"
    )

    app_button = telebot.types.InlineKeyboardButton(
        text="🌿 FitoTahlil AI ilovasini ochish",
        web_app=web_app
    )

    markup.add(app_button)

    welcome_text = (
        "🌿 FitoTahlil AI botiga xush kelibsiz!\n\n"
        "O‘simlik rasmini sun’iy intellekt yordamida tahlil qilish "
        "uchun quyidagi tugmani bosing:"
    )

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=markup
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    status_msg = bot.reply_to(message, "⏳ **FitoTahlil AI rasmni tahlil qilmoqda...**\n*Iltimos, bir oz kuting...*", parse_mode="Markdown")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        prompt = (
            "Siz professional agronom va fitopatologsiz. Berilgan o'simlik/gul rasmini tahlil qiling. "
            "Javobni aniq va tushunarli O'ZBEK TILIDA quyidagi struktura bo'yicha bering:\n\n"
            "📌 **O'simlik nomi:** (O'zbekcha va Lotincha nomi)\n"
            "📊 **Holati:** (Sog'lom / Zararlangan / Xavf ostida)\n"
            "🔍 **Tashxis va Muammo:** (Sababini tushuntiring)\n"
            "💡 **Parvarish va Davolash Tavsiyalari:**\n"
            " - 💧 **Suv:** (Sug'orish rejimiga tavsiya)\n"
            " - ☀️ **Yorug'lik va Harorat:** (Qanday muhit kerak)\n"
            " - 🧪 **O'g'it va Davolash:** (Kerakli preparat yoki o'g'itlar)"
        )

        completion = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            temperature=0.2,
            max_completion_tokens=1024,
            reasoning_effort="none",
            reasoning_format="hidden",
        )

        ai_reply = completion.choices[0].message.content
        bot.edit_message_text(f"📋 **FITOTAHLIL NATIJASI**\n\n{ai_reply}", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

    except Exception as e:
        print("Xatolik:", e)
        bot.edit_message_text(f"⚠️ Rasmni tahlil qilishda xatolik yuz berdi:\n\n`{e}`", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")


if __name__ == '__main__':
    print("FitoTahlil Bot ishga tushdi...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            print("Polling xatoligi, 5 soniyadan keyin qayta urinamiz:", e)
            time.sleep(5)
