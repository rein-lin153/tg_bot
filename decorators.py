import time
import telebot
from functools import wraps
from config import API_TOKEN
import requests  # 导入 requests 模块

# 初始化机器人
bot = telebot.TeleBot(API_TOKEN)

#捕获全局异常
def handle_telegram_exception(retries=5, delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            if isinstance(args[0], telebot.types.Message):  # 检查消息类型是否为 Message
                chat_id = args[0].chat.id
            elif isinstance(args[0], telebot.types.CallbackQuery):  # 检查消息类型是否为 CallbackQuery
                chat_id = args[0].message.chat.id
            else:
                chat_id = None

            while attempts < retries:
                try:
                    return func(*args, **kwargs)
                except telebot.apihelper.ApiTelegramException as e:
                    if e.error_code == 502:
                        if chat_id:
                            bot.send_message(chat_id, "发送错误,尝试重试...")
                        attempts += 1
                        time.sleep(delay)  # 等待一段时间后重试
                    else:
                        raise  
                except requests.exceptions.ReadTimeout as e:  # 捕获ReadTimeout异常
                    if chat_id:
                        bot.send_message(chat_id, "请求超时,尝试重试...")
                    attempts += 1
                    time.sleep(delay)  # 等待一段时间后重试

            if attempts >= retries:  # 如果达到最大重试次数
                if chat_id:
                    bot.send_message(chat_id, "请求失败，请稍后再试。")  # 通知用户请求失败
        return wrapper
    return decorator
