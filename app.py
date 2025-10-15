import os
import telebot
from telebot import types
import gspread
from google.oauth2.service_account import Credentials
import datetime
import logging
from flask import Flask, request
import json

# ========== НАСТРОЙКА ЛОГГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== СОЗДАНИЕ FLASK ПРИЛОЖЕНИЯ ДЛЯ RENDER ==========
app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN')
MANAGER_CHAT_IDS = [int(x.strip()) for x in os.environ.get('MANAGER_CHAT_IDS', '508551392',  '475363648').split(',')]
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1AbgMLiQVYfLPcROOm1UMq0evFdYuRk760HhY0cI3LH8')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен в переменных окружения")
    raise ValueError("BOT_TOKEN не установлен")

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    bot_info = bot.get_me()
    logger.info(f"✅ Бот @{bot_info.username} инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации бота: {e}")
    raise

# ========== ИНИЦИАЛИЗАЦИЯ GOOGLE SHEETS ==========
def init_google_sheets():
    """Инициализация Google Sheets с использованием Service Account"""
    try:
        # Получаем credentials из переменной окружения
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        
        if not credentials_json:
            logger.warning("❌ GOOGLE_CREDENTIALS_JSON не установлен. Google Sheets отключен.")
            return None
        
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        
        # Создаем credentials из JSON строки
        credentials_info = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        gc = gspread.authorize(credentials)
        
        # Открываем таблицу по ID
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.sheet1
        
        # Проверяем структуру таблицы
        if sheet.row_count == 0:
            headers = [
                "Статус", "Дата создания", "ID пользователя", "Username", 
                "Имя", "Телефон", "Город назначения", 
                "Описание груза", "Ссылка на сайт", "Фото", "Вес (кг)", 
                "Объем (м³)", "Способ доставки", "Бюджет", "Комментарий"
            ]
            sheet.append_row(headers)
        
        logger.info("✅ Google Sheets подключен успешно")
        return sheet
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
        return None

sheet = init_google_sheets()

# ========== СЛОВАРЬ ДЛЯ ВРЕМЕННОГО ХРАНЕНИЯ ДАННЫХ ==========
user_data = {}

# ========== КЛАВИАТУРЫ ==========
def phone_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_phone = types.KeyboardButton(text="📞 Отправить номер", request_contact=True)
    button_back = types.KeyboardButton(text="⬅️ Назад")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    button_main = types.KeyboardButton(text="🏠 В начало")
    keyboard.add(button_phone)
    keyboard.add(button_back, button_manager, button_main)
    return keyboard

def delivery_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = ["✈️ Авиа", "🚢 Море", "🚛 Авто", "🔀 Комбинированное", "❓ Не знаю"]
    keyboard.add(*buttons)
    button_back = types.KeyboardButton(text="⬅️ Назад")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    button_main = types.KeyboardButton(text="🏠 В начало")
    keyboard.add(button_back, button_manager, button_main)
    return keyboard

def skip_photo_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add("📷 Пропустить фото")
    button_back = types.KeyboardButton(text="⬅️ Назад")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    button_main = types.KeyboardButton(text="🏠 В начало")
    keyboard.add(button_back, button_manager, button_main)
    return keyboard

def cancel_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_cancel = types.KeyboardButton(text="❌ Отменить")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    button_main = types.KeyboardButton(text="🏠 В начало")
    keyboard.add(button_cancel, button_manager, button_main)
    return keyboard

def main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_new = types.KeyboardButton(text="📦 Новая заявка")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    keyboard.add(button_new, button_manager)
    return keyboard

def confirm_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_yes = types.KeyboardButton(text="✅ Подтвердить")
    button_no = types.KeyboardButton(text="✏️ Исправить")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    button_main = types.KeyboardButton(text="🏠 В начало")
    keyboard.add(button_yes, button_no, button_manager, button_main)
    return keyboard

def correction_keyboard():
    """Клавиатура для выбора поля исправления"""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        "👤 Имя", "📞 Телефон", "🏙️ Город", "📦 Груз",
        "🔗 Ссылка", "🖼️ Фото", "⚖️ Вес", "📏 Объем",
        "🚚 Доставка", "💰 Бюджет", "💬 Комментарий"
    ]
    keyboard.add(*buttons)
    button_back = types.KeyboardButton(text="⬅️ Назад к подтверждению")
    keyboard.add(button_back)
    return keyboard

def standard_keyboard():
    """Стандартная клавиатура с кнопками Назад, Менеджер, В начало"""
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_back = types.KeyboardButton(text="⬅️ Назад")
    button_manager = types.KeyboardButton(text="👨‍💼 Связаться с менеджером")
    button_main = types.KeyboardButton(text="🏠 В начало")
    keyboard.add(button_back, button_manager, button_main)
    return keyboard

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'step': 'start'}
    
    text = """
🚚 Добро пожаловать в сервис доставки из Китая в Россию!

Данный бот соберет информацию для расчета стоимости продукции и стоимости логистики.

После получения заявки в ближайшее время с Вами свяжется наш менеджер для уточнения деталей.

                              ⬇️
    """
    bot.send_message(chat_id, text, reply_markup=main_menu_keyboard())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Команда для администраторов"""
    chat_id = message.chat.id
    admin_text = f"""
🛠️ Панель администратора

Ваш ID: {chat_id}
Текущие менеджеры: {MANAGER_CHAT_IDS}
"""
    bot.send_message(chat_id, admin_text)

@bot.message_handler(func=lambda message: message.text == "📦 Новая заявка")
def new_request(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'step': 'name'}
    
    text = "Введите ваше имя:"
    bot.send_message(chat_id, text, reply_markup=standard_keyboard())

@bot.message_handler(func=lambda message: message.text == "👨‍💼 Связаться с менеджером")
def contact_manager(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'step': 'manager_contact'}
    
    text = "Опишите вашу проблему или вопрос. Менеджер свяжется с вами в ближайшее время:"
    bot.send_message(chat_id, text, reply_markup=cancel_keyboard())

@bot.message_handler(func=lambda message: message.text == "❌ Отменить")
def cancel_command(message):
    chat_id = message.chat.id
    if chat_id in user_data:
        del user_data[chat_id]
    bot.send_message(chat_id, "Заявка отменена.", reply_markup=main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def back_command(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        start_command(message)
        return
    
    current_step = user_data[chat_id].get('step', 'start')
    
    # Логика возврата на предыдущий шаг
    steps_order = ['name', 'phone', 'destination', 'cargo', 'website', 'photo', 'weight', 'volume', 'delivery', 'budget', 'comment', 'confirm']
    
    if current_step in steps_order:
        current_index = steps_order.index(current_step)
        if current_index > 0:
            prev_step = steps_order[current_index - 1]
            user_data[chat_id]['step'] = prev_step
            
            # Возвращаем к соответствующему шагу
            if prev_step == 'name':
                bot.send_message(chat_id, "Введите ваше имя:", reply_markup=standard_keyboard())
            elif prev_step == 'phone':
                bot.send_message(chat_id, "📞 Ваш номер телефона:", reply_markup=phone_keyboard())
            elif prev_step == 'destination':
                bot.send_message(chat_id, "🏙️ Город назначения (Россия):", reply_markup=standard_keyboard())
            elif prev_step == 'cargo':
                bot.send_message(chat_id, "📦 Описание груза:", reply_markup=standard_keyboard())
            elif prev_step == 'website':
                bot.send_message(chat_id, "🔗 Ссылка на сайт (или 'Нет'):", reply_markup=standard_keyboard())
            elif prev_step == 'photo':
                bot.send_message(chat_id, "🖼️ Фото груза (или 'Пропустить фото'):", reply_markup=skip_photo_keyboard())
            elif prev_step == 'weight':
                bot.send_message(chat_id, "⚖️ Вес груза (кг):", reply_markup=standard_keyboard())
            elif prev_step == 'volume':
                bot.send_message(chat_id, "📏 Объем груза (м³):", reply_markup=standard_keyboard())
            elif prev_step == 'delivery':
                bot.send_message(chat_id, "🚚 Способ доставки:", reply_markup=delivery_keyboard())
            elif prev_step == 'budget':
                bot.send_message(chat_id, "💰 Бюджет:", reply_markup=standard_keyboard())
            elif prev_step == 'comment':
                bot.send_message(chat_id, "💬 Комментарии (или 'Нет'):", reply_markup=standard_keyboard())
        else:
            start_command(message)
    else:
        start_command(message)

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад к подтверждению")
def back_to_confirmation(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        start_command(message)
        return
    
    user_data[chat_id]['step'] = 'confirm'
    show_preview(chat_id)

@bot.message_handler(func=lambda message: message.text == "🏠 В начало")
def main_menu_command(message):
    start_command(message)

# ========== ЛОГИКА ДИАЛОГА ==========
@bot.message_handler(content_types=['text', 'contact'])
def handle_all_messages(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data:
        start_command(message)
        return
    
    current_step = user_data[chat_id].get('step', 'start')
    
    if current_step == 'start':
        if message.text == "📦 Новая заявка":
            new_request(message)
        elif message.text == "👨‍💼 Связаться с менеджером":
            contact_manager(message)
        else:
            start_command(message)
    
    elif current_step == 'manager_contact':
        process_manager_contact(message)
    
    elif current_step == 'name':
        process_name(message)
    
    elif current_step == 'phone':
        process_phone(message)
    
    elif current_step == 'destination':
        process_destination(message)
    
    elif current_step == 'cargo':
        process_cargo(message)
    
    elif current_step == 'website':
        process_website(message)
    
    elif current_step == 'photo':
        process_photo(message)
    
    elif current_step == 'weight':
        process_weight(message)
    
    elif current_step == 'volume':
        process_volume(message)
    
    elif current_step == 'delivery':
        process_delivery(message)
    
    elif current_step == 'budget':
        process_budget(message)
    
    elif current_step == 'comment':
        process_comment(message)
    
    elif current_step == 'confirm':
        process_confirmation(message)
    
    elif current_step == 'correction':
        process_correction(message)

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data:
        start_command(message)
        return
    
    current_step = user_data[chat_id].get('step', 'start')
    
    if current_step == 'photo':
        process_photo(message)

def process_manager_contact(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return
    
    # Сохраняем запрос помощи
    manager_request_text = f"""
🆘 ПОМОЩЬ ОТ ПОЛЬЗОВАТЕЛЯ

👤 Пользователь: {message.from_user.first_name} {f'(@{message.from_user.username})' if message.from_user.username else ''}
🆔 ID: {chat_id}
📝 Сообщение: {message.text}

📞 Свяжитесь с пользователем как можно скорее!
"""
    
    # Отправляем менеджерам
    send_to_manager_chats(manager_request_text, None, "Запрос помощи")
    
    # Сохраняем в Google Sheets
    if sheet:
        try:
            row = [
                "Запрос помощи",
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(chat_id),
                f"@{message.from_user.username}" if message.from_user.username else "Не указан",
                f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip(),
                "Не указан",
                "Не указан",
                message.text,
                "Не указана",
                "Не загружено",
                "Не указан",
                "Не указан",
                "Не указан",
                "Не указан",
                "Не указан"
            ]
            sheet.append_row(row)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения запроса помощи: {e}")
    
    bot.send_message(chat_id, "✅ Ваше сообщение отправлено менеджерам! Они свяжутся с вами в ближайшее время.", 
                    reply_markup=main_menu_keyboard())

def process_name(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return
    
    user_data[chat_id]['name'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'phone'
    user_data[chat_id]['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data[chat_id]['user_id'] = chat_id
    user_data[chat_id]['username'] = f"@{message.from_user.username}" if message.from_user.username else "Не указан"
    
    bot.send_message(chat_id, "📞 Ваш номер телефона:", reply_markup=phone_keyboard())

def process_phone(message):
    chat_id = message.chat.id
    
    # Обработка контакта
    if message.contact:
        phone = message.contact.phone_number
        user_data[chat_id]['phone'] = phone
        
        # Если это режим исправления, возвращаем к подтверждению
        if user_data[chat_id].get('correcting_mode'):
            user_data[chat_id]['step'] = 'confirm'
            show_preview(chat_id)
            return
        
        # Иначе продолжаем обычный поток
        user_data[chat_id]['step'] = 'destination'
        bot.send_message(chat_id, "🏙️ Город назначения (Россия):", reply_markup=standard_keyboard())
        return
    
    # Обработка текста (если пользователь ввел номер вручную)
    if message.text and message.text not in ["⬅️ Назад", "👨‍💼 Связаться с менеджером", "🏠 В начало"]:
        phone = message.text
        user_data[chat_id]['phone'] = phone
        
        # Если это режим исправления, возвращаем к подтверждению
        if user_data[chat_id].get('correcting_mode'):
            user_data[chat_id]['step'] = 'confirm'
            show_preview(chat_id)
            return
        
        # Иначе продолжаем обычный поток
        user_data[chat_id]['step'] = 'destination'
        bot.send_message(chat_id, "🏙️ Город назначения (Россия):", reply_markup=standard_keyboard())
        return
    
    # Если это команда навигации
    if message.text == "⬅️ Назад":
        back_command(message)
    elif message.text == "👨‍💼 Связаться с менеджером":
        contact_manager(message)
    elif message.text == "🏠 В начало":
        main_menu_command(message)

def process_destination(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['destination'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'cargo'
    bot.send_message(chat_id, "📦 Описание груза:", reply_markup=standard_keyboard())

def process_cargo(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['cargo'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'website'
    bot.send_message(chat_id, "🔗 Ссылка на сайт (или 'Нет'):", reply_markup=standard_keyboard())

def process_website(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['website'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'photo'
    bot.send_message(chat_id, "🖼️ Фото груза (или 'Пропустить фото'):", 
                    reply_markup=skip_photo_keyboard())

def process_photo(message):
    chat_id = message.chat.id
    
    # Обработка текстовых команд
    if hasattr(message, 'text') and message.text:
        if message.text == "❌ Отменить":
            cancel_command(message)
            return
        elif message.text == "📷 Пропустить фото":
            user_data[chat_id]['photo'] = "Не загружено"
            
            # Если это режим исправления, возвращаем к подтверждению
            if user_data[chat_id].get('correcting_mode'):
                user_data[chat_id]['step'] = 'confirm'
                show_preview(chat_id)
                return
            
            # Иначе продолжаем обычный поток
            user_data[chat_id]['step'] = 'weight'
            bot.send_message(chat_id, "⚖️ Вес груза (кг):", reply_markup=standard_keyboard())
            return
        elif message.text in ["⬅️ Назад", "👨‍💼 Связаться с менеджером", "🏠 В начало"]:
            # Обработка навигационных команд
            if message.text == "⬅️ Назад":
                back_command(message)
            elif message.text == "👨‍💼 Связаться с менеджером":
                contact_manager(message)
            elif message.text == "🏠 В начало":
                main_menu_command(message)
            return
    
    # Обработка фото
    if message.photo:
        # Сохраняем информацию о фото
        user_data[chat_id]['photo'] = "Фото загружено"
        # Сохраняем file_id для возможного дальнейшего использования
        user_data[chat_id]['photo_file_id'] = message.photo[-1].file_id
        
        # Получаем URL фото
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохраняем фото локально (на Render.com файловая система временная)
        photo_filename = f"photo_{chat_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        with open(photo_filename, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        user_data[chat_id]['photo_filename'] = photo_filename
        
        # Если это режим исправления, возвращаем к подтверждению
        if user_data[chat_id].get('correcting_mode'):
            user_data[chat_id]['step'] = 'confirm'
            show_preview(chat_id)
            return
        
        # Иначе продолжаем обычный поток
        user_data[chat_id]['step'] = 'weight'
        bot.send_message(chat_id, "✅ Фото сохранено!\n\n⚖️ Вес груза (кг):", reply_markup=standard_keyboard())
    else:
        user_data[chat_id]['photo'] = "Не загружено"
        
        # Если это режим исправления, возвращаем к подтверждению
        if user_data[chat_id].get('correcting_mode'):
            user_data[chat_id]['step'] = 'confirm'
            show_preview(chat_id)
            return
        
        # Иначе продолжаем обычный поток
        user_data[chat_id]['step'] = 'weight'
        bot.send_message(chat_id, "⚖️ Вес груза (кг):", reply_markup=standard_keyboard())

def process_weight(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['weight'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'volume'
    bot.send_message(chat_id, "📏 Объем груза (м³):", reply_markup=standard_keyboard())

def process_volume(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['volume'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'delivery'
    bot.send_message(chat_id, "🚚 Способ доставки:", reply_markup=delivery_keyboard())

def process_delivery(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['delivery'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'budget'
    bot.send_message(chat_id, "💰 Бюджет:", reply_markup=standard_keyboard())

def process_budget(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['budget'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'comment'
    bot.send_message(chat_id, "💬 Комментарии (или 'Нет'):", reply_markup=standard_keyboard())

def process_comment(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return

    user_data[chat_id]['comment'] = message.text
    
    # Если это режим исправления, возвращаем к подтверждению
    if user_data[chat_id].get('correcting_mode'):
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Иначе продолжаем обычный поток
    user_data[chat_id]['step'] = 'confirm'
    
    # Показываем заявку для подтверждения
    show_preview(chat_id)

def show_preview(chat_id):
    """Показывает предварительный просмотр заявки"""
    preview_text = f"""
📋 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР ЗАЯВКИ

✅ Проверьте правильность данных:

👤 Имя: {user_data[chat_id]['name']}
📞 Телефон: {user_data[chat_id]['phone']}
🏙️ Город назначения: {user_data[chat_id]['destination']}
📦 Груз: {user_data[chat_id]['cargo']}
🔗 Ссылка: {user_data[chat_id]['website']}
🖼️ Фото: {user_data[chat_id]['photo']}
⚖️ Вес: {user_data[chat_id]['weight']} кг
📏 Объем: {user_data[chat_id]['volume']} м³
🚚 Способ доставки: {user_data[chat_id]['delivery']}
💰 Бюджет: {user_data[chat_id]['budget']}
💬 Комментарии: {user_data[chat_id]['comment']}

Всё верно?
"""
    
    bot.send_message(chat_id, preview_text, reply_markup=confirm_keyboard())

def process_confirmation(message):
    chat_id = message.chat.id
    if message.text == "❌ Отменить":
        cancel_command(message)
        return
    
    if message.text == "✅ Подтвердить":
        # Сохраняем данные
        save_data(user_data[chat_id])
        
        # Отправляем менеджерам
        send_to_managers(user_data[chat_id])
        
        # Финальное сообщение
        final_text = f"""
✅ Заявка принята!

📞 Менеджер свяжется с вами в ближайшее время для уточнения деталей.

Спасибо, что выбрали наш сервис! 🚚
"""
        
        bot.send_message(chat_id, final_text, reply_markup=main_menu_keyboard())
        
        # Очищаем данные
        if chat_id in user_data:
            del user_data[chat_id]
    
    elif message.text == "✏️ Исправить":
        user_data[chat_id]['step'] = 'correction'
        show_correction_options(chat_id)

def show_correction_options(chat_id):
    """Показывает варианты для исправления"""
    correction_text = """
✏️ Выберите, что хотите исправить:

Нажмите на поле, которое нужно изменить:
"""
    bot.send_message(chat_id, correction_text, reply_markup=correction_keyboard())

def process_correction(message):
    chat_id = message.chat.id
    
    if message.text == "⬅️ Назад к подтверждению":
        user_data[chat_id]['step'] = 'confirm'
        show_preview(chat_id)
        return
    
    # Устанавливаем режим исправления
    user_data[chat_id]['correcting_mode'] = True
    
    # Определяем какое поле нужно исправить
    if message.text == "👤 Имя":
        user_data[chat_id]['step'] = 'name'
        bot.send_message(chat_id, "Введите ваше имя:", reply_markup=standard_keyboard())
    
    elif message.text == "📞 Телефон":
        user_data[chat_id]['step'] = 'phone'
        bot.send_message(chat_id, "📞 Ваш номер телефона:", reply_markup=phone_keyboard())
    
    elif message.text == "🏙️ Город":
        user_data[chat_id]['step'] = 'destination'
        bot.send_message(chat_id, "🏙️ Город назначения (Россия):", reply_markup=standard_keyboard())
    
    elif message.text == "📦 Груз":
        user_data[chat_id]['step'] = 'cargo'
        bot.send_message(chat_id, "📦 Описание груза:", reply_markup=standard_keyboard())
    
    elif message.text == "🔗 Ссылка":
        user_data[chat_id]['step'] = 'website'
        bot.send_message(chat_id, "🔗 Ссылка на сайт (или 'Нет'):", reply_markup=standard_keyboard())
    
    elif message.text == "🖼️ Фото":
        user_data[chat_id]['step'] = 'photo'
        bot.send_message(chat_id, "🖼️ Фото груза (или 'Пропустить фото'):", reply_markup=skip_photo_keyboard())
    
    elif message.text == "⚖️ Вес":
        user_data[chat_id]['step'] = 'weight'
        bot.send_message(chat_id, "⚖️ Вес груза (кг):", reply_markup=standard_keyboard())
    
    elif message.text == "📏 Объем":
        user_data[chat_id]['step'] = 'volume'
        bot.send_message(chat_id, "📏 Объем груза (м³):", reply_markup=standard_keyboard())
    
    elif message.text == "🚚 Доставка":
        user_data[chat_id]['step'] = 'delivery'
        bot.send_message(chat_id, "🚚 Способ доставки:", reply_markup=delivery_keyboard())
    
    elif message.text == "💰 Бюджет":
        user_data[chat_id]['step'] = 'budget'
        bot.send_message(chat_id, "💰 Бюджет:", reply_markup=standard_keyboard())
    
    elif message.text == "💬 Комментарий":
        user_data[chat_id]['step'] = 'comment'
        bot.send_message(chat_id, "💬 Комментарии (или 'Нет'):", reply_markup=standard_keyboard())

def send_to_managers(data):
    """Отправляем заявку менеджерам"""
    manager_text = f"""
🆕 НОВАЯ ЗАЯВКА НА ДОСТАВКУ

📅 Дата: {data['timestamp']}
👤 Пользователь: {data.get('username', 'Не указан')}
🆔 ID: {data['user_id']}

📋 ДАННЫЕ ЗАЯВКИ:
├ Имя: {data.get('name', '')}
├ Телефон: {data.get('phone', '')}
├ Город назначения: {data.get('destination', '')}
├ Груз: {data.get('cargo', '')}
├ Ссылка: {data.get('website', '')}
├ Фото: {data.get('photo', '')}
├ Вес: {data.get('weight', '')} кг
├ Объем: {data.get('volume', '')} м³
├ Способ доставки: {data.get('delivery', '')}
├ Бюджет: {data.get('budget', '')}
└ Комментарии: {data.get('comment', '')}

⚡ Срочно свяжитесь с клиентом!
"""
    
    # Отправляем фото менеджерам, если оно есть
    photo_path = data.get('photo_filename')
    
    # Отправляем в указанные чаты менеджеров
    send_to_manager_chats(manager_text, photo_path, "Новая заявка")
    
    # Альтернативный способ - сохраняем в лог файл
    save_manager_notification(manager_text, data.get('name', 'N/A'))

def send_to_manager_chats(text, photo_path=None, notification_type="Уведомление"):
    """Отправляет сообщения в чаты менеджеров"""
    if not MANAGER_CHAT_IDS:
        logger.warning(f"⚠️ Список ID менеджеров пуст. {notification_type} не отправлена.")
        # Сохраняем в лог файл как запасной вариант
        save_manager_notification(text, "Менеджер")
        return
    
    success_count = 0
    for manager_id in MANAGER_CHAT_IDS:
        try:
            if photo_path and os.path.exists(photo_path):
                # Отправляем фото с текстом
                with open(photo_path, 'rb') as photo:
                    bot.send_photo(chat_id=manager_id, photo=photo, caption=text)
                logger.info(f"✅ {notification_type} с фото отправлена менеджеру {manager_id}")
            else:
                # Отправляем только текст
                bot.send_message(chat_id=manager_id, text=text)
                logger.info(f"✅ {notification_type} отправлена менеджеру {manager_id}")
            success_count += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки менеджеру {manager_id}: {e}")
    
    if success_count == 0:
        logger.warning(f"⚠️ Ни одному менеджеру не удалось отправить {notification_type}")
        save_manager_notification(text, "Менеджер")

def save_manager_notification(text, user_name):
    """Сохраняет уведомление в файл (запасной вариант)"""
    try:
        filename = f"manager_notifications.txt"
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Дата: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Пользователь: {user_name}\n")
            f.write(f"Текст:\n{text}\n")
            f.write(f"{'='*60}\n")
        logger.info(f"📝 Уведомление сохранено в файл: {filename}")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения уведомления в файл: {e}")

def save_data(data):
    """Сохраняем данные в Google Sheets или файл"""
    # Пробуем сохранить в Google Sheets
    if sheet:
        try:
            # Формируем строку для таблицы
            photo_info = data.get('photo', 'Не загружено')
            if data.get('photo_filename'):
                photo_info = f"Фото сохранено: {data.get('photo_filename')}"
            
            row = [
                "Новая заявка",
                data.get('timestamp', ''),
                str(data.get('user_id', '')),
                data.get('username', ''),
                data.get('name', ''),
                data.get('phone', ''),
                data.get('destination', ''),
                data.get('cargo', ''),
                data.get('website', ''),
                photo_info,
                data.get('weight', ''),
                data.get('volume', ''),
                data.get('delivery', ''),
                data.get('budget', ''),
                data.get('comment', '')
            ]
            sheet.append_row(row)
            logger.info(f"✅ Данные сохранены в Google Таблицу (пользователь: {data.get('name', 'N/A')})")
            return
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в Google Sheets: {e}")
    
    # Если Google Sheets не доступен, сохраняем в файл
    save_to_file(data)

def save_to_file(data):
    """Сохраняем данные в текстовый файл"""
    try:
        filename = f"заявки_{datetime.datetime.now().strftime('%Y%m')}.txt"
        with open(filename, 'a', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write(f"Дата: {data['timestamp']}\n")
            f.write(f"ID: {data.get('user_id', '')}\n")
            f.write(f"Username: {data.get('username', '')}\n")
            f.write(f"Имя: {data.get('name', '')}\n")
            f.write(f"Телефон: {data.get('phone', '')}\n")
            f.write(f"Город назначения: {data.get('destination', '')}\n")
            f.write(f"Груз: {data.get('cargo', '')}\n")
            f.write(f"Ссылка: {data.get('website', '')}\n")
            f.write(f"Фото: {data.get('photo', '')}\n")
            if data.get('photo_filename'):
                f.write(f"Файл фото: {data.get('photo_filename')}\n")
            f.write(f"Вес: {data.get('weight', '')} кг\n")
            f.write(f"Объем: {data.get('volume', '')} м³\n")
            f.write(f"Способ доставки: {data.get('delivery', '')}\n")
            f.write(f"Бюджет: {data.get('budget', '')}\n")
            f.write(f"Комментарии: {data.get('comment', '')}\n")
            f.write("=" * 50 + "\n\n")
        
        logger.info(f"✅ Данные сохранены в файл: {filename}")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения в файл: {e}")

# ========== WEBHOOK МАРШРУТЫ ДЛЯ RENDER ==========
@app.route('/')
def home():
    return "🚚 Telegram Bot для доставки из Китая в РФ активен!"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 403

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    # На Render используем порт из переменной окружения
    port = int(os.environ.get('PORT', 5000))
    
    # Настройка webhook для Render
    webhook_url = os.environ.get('WEBHOOK_URL')
    if webhook_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{webhook_url}/webhook")
        logger.info(f"✅ Webhook установлен: {webhook_url}/webhook")
    else:
        logger.info("🔧 Режим: Webhook не настроен, используется polling")
    
    logger.info(f"🚀 Запуск приложения на порту {port}")

    app.run(host='0.0.0.0', port=port)
