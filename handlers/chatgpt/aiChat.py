import requests
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telebot import TeleBot
import json


def handle_chat_command(bot, message, scenarios):
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)

    for scenario in scenarios.keys():
        markup.add(KeyboardButton(scenario))
    
    bot.send_message(
        message.chat.id,
        "🧟‍♀️请选择对话场景:",
        reply_markup=markup
    )

def handle_chat_end_command(bot, message, assistant_message, sessions):
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
        bot.send_message(chat_id,assistant_message , reply_markup=ReplyKeyboardRemove())
    else:
        bot.send_message(chat_id, "当前没有活动的会话。", reply_markup=ReplyKeyboardRemove())
    

def handle_scenario_selection(bot, message, scenarios, sessions):
    chat_id = message.chat.id
    scenario = message.text
    system_content = scenarios[scenario]
    if chat_id not in sessions:
        # 初始化会话状态
        sessions[chat_id] = {
            "messages": [
                {
                    "role": "system",
                    "content": system_content
                }
            ]
        }


    
    bot.send_message(message.chat.id, f"你选择了场景: {scenario}，现在可以开始对话了。")


def handle_user_message(bot, message, sessions):
    chat_id = message.chat.id
    user_message = message.text

    # 添加用户消息到会话
    sessions[chat_id]["messages"].append({
        "role": "user",
        "content": user_message
    })
    
    # 检测是否收到了/chat_end命令
    if user_message == '/chat_end':
        # 向会话中添加一条消息表示会话即将结束
        sessions[chat_id]["messages"].append({
            "role": "user",
            "content": "我走了,和我道个别吧!"
        })
        # 使用send_api_request函数发送请求到API并接收返回的助手消息
        assistant_message = send_api_request(sessions[chat_id]["messages"])
        handle_chat_end_command(bot, message, assistant_message, sessions)
        return
    # 使用send_api_request函数发送请求到API并接收返回的助手消息
    assistant_message = send_api_request(sessions[chat_id]["messages"])
    
    # 添加助手消息到会话
    sessions[chat_id]["messages"].append({
        "role": "assistant",
        "content": assistant_message
    })
    
    # 检查会话消息数量，超过31条则删除第1条消息
    if len(sessions[chat_id]["messages"]) > 31:
        del sessions[chat_id]["messages"][1:3]

    # 发送助手消息给用户
    bot.send_message(chat_id, assistant_message)
    

def send_api_request(session_messages):
    payload = {
        "messages": session_messages,
        "model": "gpt-3.5-turbo-16k",
        "stream": True,
        "temperature": 1.5,
        "presence_penalty": 0.8
    }

    url = "http://localhost:8000/v1/chat/completions"

    token = "e1b4cf0e4dc27f3a8b2011901fa65f820a0b5442@eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY3RpdmF0ZWQiOnRydWUsImFnZSI6MSwiYmFuZWQiOmZhbHNlLCJjcmVhdGVfYXQiOjE3MTg4MzAwOTksImV4cCI6MTcxODgzMTg5OSwibW9kZSI6Miwib2FzaXNfaWQiOjExNDgyNjE4NTg3MDk1NDQ5NiwidmVyc2lvbiI6Mn0.L0hwyDG_ZjPAQdvYUpCrj7_RfUWhM12zrYeST-oYeSo...eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOjEwMjAwLCJkZXZpY2VfaWQiOiJlMWI0Y2YwZTRkYzI3ZjNhOGIyMDExOTAxZmE2NWY4MjBhMGI1NDQyIiwiZXhwIjoxNzIxNDIyMDk5LCJvYXNpc19pZCI6MTE0ODI2MTg1ODcwOTU0NDk2LCJwbGF0Zm9ybSI6IndlYiIsInZlcnNpb24iOjJ9.PuG-aUxRsIhNP8XmQiDOB0XK36RF2sk6wBWGt_aw71w"

    headers = {
    "Authorization": f"Bearer {token}"
    }
    response = requests.post(url, json=payload, headers=headers)
        
    assistant_message = ""
    
    if response.status_code == 200:
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data = decoded_line[len("data: "):]
                    if data == "[DONE]":
                        break
                    json_data = json.loads(data)
                    delta = json_data.get("choices")[0].get("delta", {})
                    content = delta.get("content", "")
                    assistant_message += content
        return assistant_message
    else:
        return f"请求失败: {response.status_code}"