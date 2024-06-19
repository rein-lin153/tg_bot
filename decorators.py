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
            message = args[0]
            chat_id = message.chat.id  # 从 message 对象中获取 chat_id
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
                except requests.exceptions.ReadTimeout as e:  # 捕获ReadTimeout异常
                   bot.send_message(chat_id, "请求超时,尝试重试...")
                   attempts += 1
                   time.sleep(delay)  # 等待一段时间后重试
            if attempts >= retries:  # 如果达到最大重试次数
                bot.send_message(chat_id, "请求失败，请稍后再试。")  # 通知用户请求失败
        return wrapper
    return decorator
