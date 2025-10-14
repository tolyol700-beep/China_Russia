import os
import logging
from app import bot, sheet, MANAGER_CHAT_IDS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Запуск Telegram бота для доставки...")
    logger.info(f"📊 Статус системы:")
    logger.info(f"   🤖 Бот: ✅ активен")
    logger.info(f"   📊 Google Таблица: {'✅ Подключена' if sheet else '❌ Файл'}")
    logger.info(f"   👥 Менеджеры: {MANAGER_CHAT_IDS}")
    
    try:
        # Запускаем бота в режиме polling
        logger.info("🔧 Бот запущен в режиме polling...")
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")

if __name__ == '__main__':
    main()