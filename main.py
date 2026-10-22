import os
import json
import random
from datetime import datetime
import telebot
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# 1. إعداد التوكن وتخزين البيانات
BOT_TOKEN = "8946190104:AAE5uWoStI7VQLrCkrTn4xglekhS_wzcodA"
bot = telebot.TeleBot(BOT_TOKEN)

DATA_FILE = "league_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"players": [], "schedule": {}, "current_day": 0}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# معالجة النصوص العربية للصور
def format_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

# خوارزمية القرعة الكاملة (Round-Robin) لـ 26 لاعب أو أي عدد
def generate_round_robin(players):
    if len(players) % 2 != 0:
        players.append("باي (استراحة)") # إذا كان العدد فردياً
    
    list_players = list(players)
    random.shuffle(list_players)
    n = len(list_players)
    schedule = {}
    
    for day in range(n - 1):
        day_matches = []
        for i in range(n // 2):
            p1 = list_players[i]
            p2 = list_players[n - 1 - i]
            if p1 != "باي (استراحة)" and p2 != "باي (استراحة)":
                day_matches.append({"p1": p1, "p2": p2, "played": False, "result": ""})
        schedule[str(day + 1)] = day_matches
        # تدوير اللاعبين ما عدا الأول ثابت
        list_players = [list_players[0]] + [list_players[-1]] + list_players[1:-1]
        
    return schedule

# أمر بدء موسم جديد والقرعة
@bot.message_handler(commands=['new_season'])
def start_new_season(message):
    raw_text = message.text.replace('/new_season', '').strip()
    if not raw_text:
        bot.reply_to(message, "❌ يرجى إرسال أسماء اللاعبين بعد الأمر كل اسم في سطر.")
        return
    
    players = [p.strip() for p in raw_text.split('\n') if p.strip()]
    if len(players) < 2:
        bot.reply_to(message, "❌ يجب إدخل لاعبين اثنين على الأقل.")
        return
    
    schedule = generate_round_robin(players)
    data = {"players": players, "schedule": schedule, "current_day": 1}
    save_data(data)
    
    bot.reply_to(message, f"✅ تم بدء الموسم الجديد بنجاح! تم تسجيل {len(players)} لاعب وتوليد جدول الدوري بالكامل لـ {len(schedule)} مواجهة يومية.")

# أمر استعلام اللاعب عن مواجهته اليوم
@bot.message_handler(func=lambda m: m.text.strip() == "مواجهة" or m.text.strip() == "مواجهتي")
def get_my_match(message):
    data = load_data()
    current_day = str(data.get("current_day", 0))
    schedule = data.get("schedule", {})
    
    if current_day == "0" or current_day not in schedule:
        bot.reply_to(message, "⚠️ لا توجد بطولة قائمة حالياً أو انتهت المواجهات.")
        return
    
    user_name = message.from_user.first_name
    day_matches = schedule[current_day]
    my_match = None
    
    for match in day_matches:
        if user_name in match["p1"] or user_name in match["p2"]:
            my_match = match
            break
            
    if my_match:
        reply = f"📊 مواجهتك لليوم (اليوم {current_day}):\n\n⚔️ *{my_match['p1']}*  VS  *{my_match['p2']}*"
        bot.reply_to(message, reply, parse_mode="Markdown")
    else:
        bot.reply_to(message, f"🔍 لم أجد مواجهة مجدولة لليوم باسمك المسجل في تليجرام ({user_name}). تأكد من تطابق اسمك بالبطولة.")

# دالة إرسال مواجهات اليوم وتثبيتها
def send_daily_matches(chat_id):
    data = load_data()
    current_day = data.get("current_day", 0)
    schedule = data.get("schedule", {})
    
    if str(current_day) in schedule:
        matches = schedule[str(current_day)]
        text = f"📢 *مواجهات اليوم {current_day} من الدوري* 📢\n\n"
        
        for m in matches:
            text += f"⚽ {m['p1']}  ❌  {m['p2']}\n"
            
        text += "\n⚠️ بالتوفيق للجميع! يرجى تنسيق وقت المباراة والالتزام."
        
        msg = bot.send_message(chat_id, text, parse_mode="Markdown")
        try:
            bot.pin_chat_message(chat_id, msg.message_id)
        except Exception as e:
            print(f"لم نتمكن من التثبيت: {e}")
            
        data["current_day"] += 1
        save_data(data)

# أمر يدوي للمسؤول لإرسال مواجهة اليوم فوراً وتجربتها
@bot.message_handler(commands=['send_today'])
def force_today(message):
    send_daily_matches(message.chat.id)

# مؤقت مخصص بديل لـ APScheduler لتفادي مشاكل الحزم في البيئات المقيدة
def start_timer_at_midnight(chat_id):
    import time
    from threading import Thread
    
    def check_time():
        while True:
            now = datetime.now()
            # التحقق إذا كانت الساعة 00:00 (12 منتصف الليل) بتوقيت السيرفر
            if now.hour == 0 and now.minute == 0:
                send_daily_matches(chat_id)
                time.sleep(60) # تخطي الدقيقة الحالية لتفادي التكرار
            time.sleep(30)
            
    Thread(target=check_time, daemon=True).start()

print("البوت يعمل بكفاءة بدون قيود...")
bot.infinity_polling()
