import telebot
from telebot import types
import sqlite3
import random
import time
import re
import requests
import json
from datetime import datetime, timedelta
import threading
import schedule
import pytz
import os

# إعدادات البوت - سيتم الحصول على التوكن من متغير البيئة
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)

# بيانات المطور
DEVELOPER_ID = 7722416548
DEVELOPER_USERNAME = '@Solo_sn'

# قناة الاشتراك الإجباري (يمكن تعيينها عبر متغير البيئة)
FORCE_SUB_CHANNEL = os.getenv('FORCE_SUB_CHANNEL', None)

# قاعدة البيانات
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 1000,
    bank_balance INTEGER DEFAULT 0,
    rank TEXT DEFAULT 'عضو',
    joined_date DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price INTEGER,
    category TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_items (
    user_id INTEGER,
    item_id INTEGER,
    purchase_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (item_id) REFERENCES items (item_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS ai_responses (
    keyword TEXT PRIMARY KEY,
    responses TEXT
)
''')

# إضافة بعض العناصر إلى المتجر
default_items = [
    ('سيارة', 5000, 'مركبات'),
    ('طائرة', 15000, 'مركبات'),
    ('ملعب', 30000, 'عقارات'),
    ('لعبة', 1000, 'ترفيه'),
    ('منزل', 45000, 'عقارات'),
    ('يخت', 25000, 'مركبات'),
    ('دبابة', 30000, 'مركبات'),
    ('دراجة نارية', 3000, 'مركبات'),
    ('قصر', 100000, 'عقارات'),
    ('جزيرة', 500000, 'عقارات')
]

cursor.executemany('INSERT OR IGNORE INTO items (name, price, category) VALUES (?, ?, ?)', default_items)

# إضافة ردود الذكاء الاصطناعي الأساسية
default_responses = [
    ('مرحبا', 'أهلاً وسهلاً! 😊|مرحباً بك! 🤗|أهلاً بك! كيف يمكنني مساعدتك؟ 🎉'),
    ('اهلا', 'أهلاً وسهلاً! 😊|مرحباً بك! 🤗|أهلاً بك! 🎉'),
    # ... (كل الردود الأخرى التي لديك)
]

for keyword, responses in default_responses:
    cursor.execute('INSERT OR IGNORE INTO ai_responses (keyword, responses) VALUES (?, ?)', (keyword, responses))

conn.commit()

# رتب البوت
RANKS = {
    'عضو': 0,
    'مميز': 1,
    'ادمن': 2,
    'مدير': 3,
    'مالك': 4,
    'مالك اساسي': 5
}

# دالة للتحقق من صلاحية الرتبة
def check_rank(user_id, required_rank):
    cursor.execute('SELECT rank FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        user_rank = result[0]
        return RANKS.get(user_rank, 0) >= RANKS.get(required_rank, 0)
    return False

# دالة للتحقق من حالة الاشتراك في القناة
def check_subscription(user_id):
    if not FORCE_SUB_CHANNEL:
        return True
    
    try:
        member = bot.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# دالة للحصول على رد ذكي
def get_ai_response(text):
    text = text.lower()
    
    # البحث عن كلمة مفتاحية في النص
    cursor.execute('SELECT keyword, responses FROM ai_responses')
    all_responses = cursor.fetchall()
    
    for keyword, responses in all_responses:
        if keyword in text:
            response_list = responses.split('|')
            return random.choice(response_list)
    
    # إذا لم يتم العثور على رد مناسب
    default_responses = [
        "هذا مثير للاهتمام، أخبرني المزيد 📚",
        "أنا أتعلم كل يوم، يمكنك تعليمي أشياء جديدة 🌟",
        "رائع! هل لديك المزيد لتقوله؟ 🎉",
        "لم أفهم ما تقصد، هل يمكنك التوضيح أكثر؟ 🤔",
        "مممم، لا أعرف كيف أرد على هذا 🧐"
    ]
    return random.choice(default_responses)

# دالة لمنح مكافأة يومية
def daily_bonus():
    cursor.execute('UPDATE users SET balance = balance + 500 WHERE balance < 100000')
    conn.commit()

# جدولة المكافأة اليومية
schedule.every().day.at("00:00").do(daily_bonus)

# تشغيل الجدولة في الخلفية
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.daemon = True
scheduler_thread.start()

# الأوامر الأساسية
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # التحقق من الاشتراك في القناة
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("اشترك في القناة", url=f"https://t.me/{FORCE_SUB_CHANNEL[1:]}"))
        markup.add(types.InlineKeyboardButton("تأكيد الاشتراك", callback_data="check_subscription"))
        bot.send_message(message.chat.id, f"عذراً {user_name}، يجب الاشتراك في القناة أولاً:", reply_markup=markup)
        return
    
    # إضافة المستخدم إلى قاعدة البيانات إذا لم يكن موجوداً
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, user_name))
    conn.commit()
    
    # إرسال رسالة ترحيب مع أزرار
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add('💰 رصيدي', '🏦 بنك')
    markup.add('🛒 متجر', '🎯 ألعاب')
    markup.add('ℹ️ معلومات', '💬 محادثة')
    
    welcome_text = f"""
    أهلاً وسهلاً بك {user_name}!
    في بوت الذكاء الاصطناعي العربي 🤖

    ✅ يمكنك التحدث معي بشكل طبيعي وسأرد عليك.
    💰 لديك رصيد ابتدائي 1000 عملة.
    🎯 استمتع بالألعاب والميزات الأخرى.

    اختر من الأزرار أدناه أو اكتب رسالة لتبدأ المحادثة.
    """
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text
    
    # التحقق من الاشتراك في القناة
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("اشترك في القناة", url=f"https://t.me/{FORCE_SUB_CHANNEL[1:]}"))
        markup.add(types.InlineKeyboardButton("تأكيد الاشتراك", callback_data="check_subscription"))
        bot.send_message(message.chat.id, "عذراً، يجب الاشتراك في القناة أولاً:", reply_markup=markup)
        return
    
    # معالجة الأوامر النصية
    if text == '💰 رصيدي':
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = cursor.fetchone()
        if balance:
            bot.reply_to(message, f"رصيدك الحالي: {balance[0]} عملة 💰")
        else:
            bot.reply_to(message, "لم يتم العثور على حسابك.")
    
    elif text == '🏦 بنك':
        cursor.execute('SELECT bank_balance FROM users WHERE user_id = ?', (user_id,))
        bank_balance = cursor.fetchone()
        if bank_balance:
            bot.reply_to(message, f"رصيدك في البنك: {bank_balance[0]} عملة 🏦")
        else:
            bot.reply_to(message, "لم يتم العثور على حسابك.")
    
    elif text == '🛒 متجر':
        # عرض عناصر المتجر
        cursor.execute('SELECT name, price, category FROM items')
        items = cursor.fetchall()
        items_text = "🛒 متجر العناصر:\n\n"
        for item in items:
            items_text += f"{item[0]} - {item[2]} - {item[1]} عملة\n"
        items_text += "\nلشراء عنصر، اكتب 'اشتري [اسم العنصر]'"
        bot.reply_to(message, items_text)
    
    elif text == '🎯 ألعاب':
        # عرض قائمة الألعاب
        games_text = """
        🎯 قائمة الألعاب:
        
        - lucky: اختر رقمًا واحصل على جائزة 🎲
        - كرة القدم: تحدى البوت في كرة القدم ⚽
        - سباق: سباق سيارات 🏎️
        
        اكتب اسم اللعبة لبدء اللعب.
        """
        bot.reply_to(message, games_text)
    
    elif text == 'ℹ️ معلومات':
        # عرض معلومات المستخدم
        cursor.execute('SELECT username, balance, bank_balance, rank, joined_date FROM users WHERE user_id = ?', (user_id,))
        user_info = cursor.fetchone()
        if user_info:
            info_text = f"""
            ℹ️ معلومات المستخدم:
            
            الاسم: {user_info[0]}
            الرصيد: {user_info[1]} عملة
            البنك: {user_info[2]} عملة
            الرتبة: {user_info[3]}
            تاريخ الانضمام: {user_info[4]}
            """
            bot.reply_to(message, info_text)
        else:
            bot.reply_to(message, "لم يتم العثور على حسابك.")
    
    elif text == '💬 محادثة':
        bot.reply_to(message, "مرحبًا! يمكنك التحدث معي بشكل طبيعي. جرب أن تسألني أو تخبرني شيءًا 😊")
    
    elif text.startswith('اشتري '):
        item_name = text[6:]
        cursor.execute('SELECT item_id, price FROM items WHERE name = ?', (item_name,))
        item = cursor.fetchone()
        if item:
            item_id, price = item
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            balance = cursor.fetchone()
            if balance and balance[0] >= price:
                # خصم المبلغ وإضافة العنصر للمستخدم
                cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (price, user_id))
                cursor.execute('INSERT INTO user_items (user_id, item_id) VALUES (?, ?)', (user_id, item_id))
                conn.commit()
                bot.reply_to(message, f"تم شراء {item_name} بنجاح! 🛍️")
            else:
                bot.reply_to(message, "رصيدك غير كافي لشراء هذا العنصر. 💸")
        else:
            bot.reply_to(message, "العنصر غير موجود في المتجر. ❌")
    
    elif text == 'lucky':
        # لعبة الحظ
        lucky_number = random.randint(1, 10)
        prize = lucky_number * 100
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (prize, user_id))
        conn.commit()
        bot.reply_to(message, f"🎲 الرقم الذي ظهر هو: {lucky_number}\nمبارك! لقد ربحت {prize} عملة! 🎉")
    
    else:
        # محادثة عادية مع البوت
        response = get_ai_response(text)
        bot.reply_to(message, response)

# معالجة callback للاشتراك
@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    user_id = call.from_user.id
    if check_subscription(user_id):
        bot.edit_message_text("تم الاشتراك بنجاح! 😊", call.message.chat.id, call.message.message_id)
        # إرسال رسالة ترحيب بعد الاشتراك
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "لم يتم الاشتراك بعد. يرجى الاشتراك في القناة أولاً.", show_alert=True)

# تشغيل البوت
if __name__ == '__main__':
    print("Bot is running...")
    bot.polling(none_stop=True)