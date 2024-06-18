import time
from telebot import TeleBot 
from functools import wraps
from config import API_TOKEN

# 初始化机器人
bot = TeleBot(API_TOKEN)

#捕获全局异常
def handle_telegram_exception(retries=5, delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retries:
                try:
                    return func(*args, **kwargs)
                except telebot.apihelper.ApiTelegramException as e:
                    if e.error_code == 502:
                        bot.send_message(chat_id, "发送错误,尝试重试...")
                        attempts += 1
                        time.sleep(delay)  # 等待一段时间后重试
                    else:
                        raise  
        return wrapper
    return decorator
