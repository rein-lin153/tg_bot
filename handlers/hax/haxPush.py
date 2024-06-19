import requests
from datetime import datetime, timedelta
import threading
import time

# Server酱的API URL和密钥
SERVER_CHAN_API_URL = "https://sctapi.ftqq.com/SCT250564TkWvOCFYKkHe0QGOUo9Pw9C1x.send"

# 设置初始到期时间
expiry_date = datetime(2024, 6, 24)

# 计算到期时间的前三天
def calculate_notification_date():
    return expiry_date - timedelta(days=3)

notification_date = calculate_notification_date()

def handle_renew_succeed(bot, message):
    chat_id = message.chat.id

    success_message = renew()

    # 回复消息
    bot.send_message(chat_id, success_message)



# 发送消息的函数
def send_notification(title):
    try:
        params = {
            'title': title
        }
        response = requests.get(SERVER_CHAN_API_URL, params=params)
        response.raise_for_status()  # 检查请求是否成功
        print("消息发送成功:", response.text)
    except requests.RequestException as e:
        print(f"发送消息时出错: {e}")

# 检查到期时间的线程函数
def check_expiry():
    global expiry_date
    while True:
        days_until_expiry = (expiry_date.date() - datetime.now().date()).days
        notification_template = "hax服务{}天后到期，快去续期！"
        message = notification_template.format(days_until_expiry)
        
        if days_until_expiry == 3:
            send_notification(message)
            time.sleep(24 * 60 * 60)  # 第一次检查后，等待24小时再检查
        elif days_until_expiry == 2:
            for _ in range(3):
                send_notification(message)
                time.sleep(8 * 60 * 60)  # 每8小时发送一次
        elif days_until_expiry == 1:
            for _ in range(10):
                send_notification(message)
                time.sleep(2 * 60 * 60)  # 每2小时发送一次
        else:
            # 每小时检查一次
            time.sleep(3600)

# 接收续期请求
def renew():
    global expiry_date
    global notification_date
    
    # 检查当前时间是否到达或超过过期时间的前三天
    if datetime.now() < notification_date:
        start_date = notification_date.strftime('%d')
        end_date = (notification_date + timedelta(days=2)).strftime('%d')
        return f"请在{start_date}-{end_date}日内续期,过期日期为: {expiry_date.date()}"

    # 更新到期时间和通知日期
    expiry_date = datetime.now() + timedelta(days=5)
    notification_date = calculate_notification_date()
    return "Hax续期成功, 到期时间为: {}".format(expiry_date.strftime('%Y-%m-%d'))

# 启动检查到期时间的线程
threading.Thread(target=check_expiry, daemon=True).start()