import telebot
from telebot import types
import gspread
from google.oauth2.service_account import Credentials
import datetime
import os
import json
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ========== КОНФИГУРАЦИЯ ==========

# Токен бота из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Настройки Google Sheets и Drive
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
SPREADSHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME', 'Заявки на доставку из Китая')
GOOGLE_DRIVE_FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')

# Загрузка credentials из переменной окружения
def get_google_credentials():
    credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if credentials_json:
        # Чтение из переменной окружения (для production)
        credentials_dict = json.loads(credentials_json)
        return Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
    else:
        # Локальная разработка - из файла
        try:
            return Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        except Exception as e:
            print(f"Ошибка загрузки credentials: {e}")
            return None

# Инициализация бота и Google API
bot = telebot.TeleBot(BOT_TOKEN)
credentials = get_google_credentials()

if credentials:
    gc = gspread.authorize(credentials)
    try:
        spreadsheet = gc.open(SPREADSHEET_NAME)
        sheet = spreadsheet.sheet1
        print("✅ Успешное подключение к Google Таблице")
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Таблице: {e}")
        sheet = None
else:
    print("❌ Не удалось инициализировать Google credentials")
    sheet = None

# Словарь для временного хранения данных пользователей
user_data = {}

# ========== КЛАСС ДЛЯ РАБОТЫ С ФОТО ==========
class PhotoManager:
    def __init__(self, bot_token, drive_credentials, drive_folder_id):
        self.bot_token = bot_token
        self.drive_credentials = drive_credentials
        self.drive_folder_id = drive_folder_id
        self.temp_dir = "temp_photos"
        # Создаем временную директорию если её нет
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    def download_photo(self, file_id, chat_id):
        """Скачивание фото с Telegram"""
        try:
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_info.file_path}"
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_{chat_id}_{timestamp}.jpg"
            file_path = os.path.join(self.temp_dir, filename)
            
            response = requests.get(file_url)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            return filename, file_path
        except Exception as e:
            print(f"Ошибка скачивания фото: {e}")
            return None, None
    
    def upload_to_drive(self, file_path, filename):
        """Загрузка на Google Drive"""
        try:
            drive_service = build('drive', 'v3', credentials=self.drive_credentials)
            
            file_metadata = {
                'name': filename,
                'parents': [self.drive_folder_id]
            }
            
            media = MediaFileUpload(file_path, resumable=True)
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            # Делаем файл публично доступным
            drive_service.permissions().create(
                fileId=file['id'],
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
            
            return file.get('webViewLink')
        except Exception as e:
            print(f"Ошибка загрузки на Drive: {e}")
            return None
    
    def process_photo(self, file_id, chat_id):
        """Полный процесс обработки фото"""
        if not self.drive_credentials or not self.drive_folder_id:
            return "Фото загружено (Drive не настроен)"
        
        # Скачиваем
        filename, file_path = self.download_photo(file_id, chat_id)
        if not filename:
            return "Ошибка загрузки фото"
        
        # Загружаем на Drive
        drive_link = self.upload_to_drive(file_path, filename)
        
        # Очищаем временный файл
        try:
            os.remove(file_path)
        except:
            pass
        
        return drive_link if drive_link else f"Фото: {filename} (не загружено в Drive)"

# Инициализация менеджера фото
if credentials and GOOGLE_DRIVE_FOLDER_ID:
    photo_manager = PhotoManager(
        bot_token=BOT_TOKEN,
        drive_credentials=credentials,
        drive_folder_id=GOOGLE_DRIVE_FOLDER_ID
    )
else:
    photo_manager = None
    print("⚠️  Менеджер фото не инициализирован: отсутствуют credentials или folder_id")

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

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
    🤖 *Помощь по боту*

    Команды:
    /start - начать новую заявку
    /help - показать эту справку
    /status - проверить статус бота

    По вопросам работы бота обращайтесь к нашему менеджеру.
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def send_status(message):
    status_text = """
    ✅ *Статус бота*

    Бот работает нормально.
    Google Таблица: {sheet_status}
    Google Drive: {drive_status}
    """.format(
        sheet_status="✅ Подключена" if sheet else "❌ Ошибка подключения",
        drive_status="✅ Настроен" if photo_manager and GOOGLE_DRIVE_FOLDER_ID else "❌ Не настроен"
    )
    bot.send_message(message.chat.id, status_text, parse_mode='Markdown')

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
        # Обрабатываем фото
        photo_id = message.photo[-1].file_id
        
        if photo_manager:
            photo_result = photo_manager.process_photo(photo_id, chat_id)
            user_data[chat_id]['photo'] = photo_result
        else:
            user_data[chat_id]['photo'] = "Фото загружено (Drive не настроен)"
        
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
    if chat_id in user_data:
        del user_data[chat_id]

def save_data_to_sheet(chat_id, username, data):
    """Функция для сохранения данных в Google Таблицу"""
    if not sheet:
        print(f"❌ Не удалось сохранить данные: таблица не доступна")
        return
        
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            "Новая заявка на доставку",  # Название блоков
            timestamp,                   # Дата заявки / Timestamp
            str(chat_id),                # User ID
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
        print(f"✅ Данные для chat_id {chat_id} успешно сохранены.")
    except Exception as e:
        print(f"❌ Ошибка при сохранении данных: {e}")

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
    print("🚀 Бот запускается...")
    print(f"✅ Токен бота: {'Установлен' if BOT_TOKEN else 'Отсутствует'}")
    print(f"✅ Google Таблица: {'Доступна' if sheet else 'Не доступна'}")
    print(f"✅ Google Drive: {'Настроен' if photo_manager and GOOGLE_DRIVE_FOLDER_ID else 'Не настроен'}")
    
    try:
        print("🔄 Запуск long-polling...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
