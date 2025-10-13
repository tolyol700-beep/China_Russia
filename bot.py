import telebot
from telebot import types
import gspread
from google.oauth2.service_account import Credentials
import datetime
import os

# ========== КОНФИГУРАЦИЯ ==========

# Токен бота от BotFather
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'

# Настройки доступа к Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'  # Путь к вашему JSON-файлу
SPREADSHEET_NAME = 'Заявки на доставку из Китая'  # Название вашей таблицы

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация Google Sheets
credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open(SPREADSHEET_NAME).sheet1  # Работаем с первым листом

# Словарь для временного хранения данных пользователей
user_data = {}

# ========== ОПРЕДЕЛЕНИЕ СОСТОЯНИЙ ==========
class UserState:
    NAME = 1
    PHONE = 2
    ORIGIN_CITY = 3
    DESTINATION_CITY = 4
    CARGO_DESCRIPTION = 5
    WEBSITE_LINK = 6
    PHOTO = 7
    WEIGHT = 8
    VOLUME = 9
    DELIVERY_METHOD = 10
    BUDGET = 11
    COMMENT = 12

# ========== КЛАВИАТУРЫ ==========
def phone_keyboard():
    """Клавиатура для запроса номера телефона"""
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_phone = types.KeyboardButton(text="Отправить номер телефона", request_contact=True)
    keyboard.add(button_phone)
    return keyboard

def delivery_method_keyboard():
    """Клавиатура для выбора способа доставки"""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        "Авиа",
        "Море (контейнер)",
        "Авто", 
        "Комбинированное",
        "Не знаю"
    ]
    keyboard.add(*buttons)
    return keyboard

def photo_keyboard():
    """Клавиатура для загрузки фото"""
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add("Пропустить загрузку фото")
    return keyboard

def cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add("Отменить заявку")
    return keyboard

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_data[chat_id] = {}  # Создаем запись для пользователя

    welcome_text = """
    🚚 Добро пожаловать в сервис доставки грузов из Китая в РФ!

    Я помогу вам собрать информацию для расчета стоимости и сроков доставки. Заполнение займет не более 3 минут.

    Для начала введите ваше *Имя*:
    """
    bot.send_message(chat_id, welcome_text, parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_name_step)

@bot.message_handler(func=lambda message: message.text == "Отменить заявку")
def cancel_request(message):
    chat_id = message.chat.id
    if chat_id in user_data:
        del user_data[chat_id]
    bot.send_message(chat_id, "Заявка отменена. Чтобы начать заново, отправьте /start.", reply_markup=types.ReplyKeyboardRemove())

# ========== ЛОГИКА ДИАЛОГА ==========
def process_name_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['name'] = message.text
    bot.send_message(chat_id, "📞 Теперь поделитесь вашим номером телефона для связи:", reply_markup=phone_keyboard())
    bot.register_next_step_handler(message, process_phone_step)

def process_phone_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    if message.contact is not None:
        phone = message.contact.phone_number
    else:
        phone = message.text  # На случай, если пользователь введет номер вручную

    user_data[chat_id]['phone'] = phone

    bot.send_message(chat_id, "🏙️ Из какого *города в Китае* нужно забрать груз?", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_origin_city_step)

def process_origin_city_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['origin_city'] = message.text
    bot.send_message(chat_id, "🏙️ В какой *город в России* нужно доставить груз?", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_destination_city_step)

def process_destination_city_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['destination_city'] = message.text
    bot.send_message(chat_id, "📦 Опишите груз (например: *Электронные компоненты, одежда, запчасти*):", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_cargo_description_step)

def process_cargo_description_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['cargo_description'] = message.text
    bot.send_message(chat_id, "🔗 Есть ли *ссылка на сайт* с товаром? (Если нет, напишите 'Нет'):", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_website_link_step)

def process_website_link_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['website_link'] = message.text
    bot.send_message(chat_id, "🖼️ Пришлите *фото груза* (если есть). Или нажмите 'Пропустить загрузку фото':", parse_mode='Markdown', reply_markup=photo_keyboard())
    bot.register_next_step_handler(message, process_photo_step)

def process_photo_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    if message.text == "Пропустить загрузку фото":
        user_data[chat_id]['photo'] = "Не загружено"
        bot.send_message(chat_id, "⚖️ Укажите *приблизительный вес груза (в кг)*:", parse_mode='Markdown', reply_markup=cancel_keyboard())
        bot.register_next_step_handler(message, process_weight_step)
    elif message.photo:
        # Сохраняем информацию о фото (file_id)
        photo_id = message.photo[-1].file_id
        user_data[chat_id]['photo'] = f"Фото загружено (ID: {photo_id})"
        bot.send_message(chat_id, "✅ Фото принято! Теперь укажите *приблизительный вес груза (в кг)*:", parse_mode='Markdown', reply_markup=cancel_keyboard())
        bot.register_next_step_handler(message, process_weight_step)
    else:
        user_data[chat_id]['photo'] = "Не загружено"
        bot.send_message(chat_id, "⚖️ Укажите *приблизительный вес груза (в кг)*:", parse_mode='Markdown', reply_markup=cancel_keyboard())
        bot.register_next_step_handler(message, process_weight_step)

def process_weight_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['weight'] = message.text
    bot.send_message(chat_id, "📏 Укажите *приблизительный объем груза (в м³)*:", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_volume_step)

def process_volume_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['volume'] = message.text
    bot.send_message(chat_id, "🚚 Выберите *способ доставки*:", parse_mode='Markdown', reply_markup=delivery_method_keyboard())
    bot.register_next_step_handler(message, process_delivery_method_step)

def process_delivery_method_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['delivery_method'] = message.text
    bot.send_message(chat_id, "💰 Укажите ваш *примерный бюджет* на доставку:", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_budget_step)

def process_budget_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['budget'] = message.text
    bot.send_message(chat_id, "💬 *Последний шаг!* Есть ли дополнительные *комментарии*?\n(Если нет, напишите 'Нет'):", parse_mode='Markdown', reply_markup=cancel_keyboard())
    bot.register_next_step_handler(message, process_comment_step)

def process_comment_step(message):
    chat_id = message.chat.id
    if message.text == "Отменить заявку":
        cancel_request(message)
        return

    user_data[chat_id]['comment'] = message.text

    # ========== СОХРАНЕНИЕ ДАННЫХ ==========
    save_data_to_sheet(chat_id, message.from_user.username, user_data[chat_id])

    # ========== ФИНАЛЬНОЕ СООБЩЕНИЕ ==========
    final_message = f"""
✅ *Спасибо! Ваша заявка принята!*

*Данные заявки:*
*Название блоков:* Новая заявка на доставку
*Имя:* {user_data[chat_id]['name']}
*Телефон:* {user_data[chat_id]['phone']}
*Город отправитель (КНР):* {user_data[chat_id]['origin_city']}
*Город получатель (РФ):* {user_data[chat_id]['destination_city']}
*Описание груза:* {user_data[chat_id]['cargo_description']}
*Ссылка на сайт:* {user_data[chat_id]['website_link']}
*Фото:* {user_data[chat_id]['photo']}
*Вес:* {user_data[chat_id]['weight']} кг
*Объем:* {user_data[chat_id]['volume']} м³
*Способ доставки:* {user_data[chat_id]['delivery_method']}
*Бюджет:* {user_data[chat_id]['budget']}
*Комментарии:* {user_data[chat_id]['comment']}

Наш менеджер свяжется с вами в ближайшее время для уточнения деталей и расчета точной стоимости.

Для создания новой заявки отправьте /start
"""
    
    bot.send_message(chat_id, final_message, parse_mode='Markdown', reply_markup=types.ReplyKeyboardRemove())

    # Очищаем временные данные
    del user_data[chat_id]

def save_data_to_sheet(chat_id, username, data):
    """Функция для сохранения данных в Google Таблицу"""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            "Новая заявка на доставку",  # Название блоков
            timestamp,                   # Дата заявки / Timestamp
            chat_id,                     # User ID
            f"@{username}" if username else "Не указан",  # Username
            data.get('name', ''),        # Имя
            data.get('phone', ''),       # Телефон
            data.get('origin_city', ''), # Город отправитель (КНР)
            data.get('destination_city', ''), # Город получатель (РФ)
            data.get('cargo_description', ''), # Описание груза
            data.get('website_link', ''), # Ссылка на сайт
            data.get('photo', ''),       # Фото
            data.get('weight', ''),      # Вес
            data.get('volume', ''),      # Объем
            data.get('delivery_method', ''), # Способ доставки
            data.get('budget', ''),      # Бюджет
            data.get('comment', '')      # Комментарии
        ]
        sheet.append_row(row)
        print(f"Данные для chat_id {chat_id} успешно сохранены.")
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")

# Обработчик для любых сообщений, которые не входят в основной flow
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        bot.send_message(chat_id, "Для начала работы отправьте /start")
    else:
        bot.send_message(chat_id, "Пожалуйста, завершите текущую заявку или отправьте /start для начала новой.")

# ========== ЗАПУСК БОТА ==========
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()