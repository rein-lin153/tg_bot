import requests
from telebot.types import ReplyKeyboardMarkup ,KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telebot import TeleBot
import json
import os
from urllib.request import urlopen
import re
import random

# 假设有一个全局字典来跟踪每个用户的回复模式
user_reply_mode = {}


def handle_chat_command(bot, message, scenarios):
    markup = InlineKeyboardMarkup()  # 使用 InlineKeyboardMarkup 而不是 InlineKeyboardButton

    for scenario in scenarios.keys():
        button = InlineKeyboardButton(scenario, callback_data=f"scenario_{scenario}")
        markup.add(button)  # 确保传递的是 InlineKeyboardButton 实例
    
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
    

def handle_scenario_selection(bot, call, scenarios, sessions):
    chat_id = call.message.chat.id
    selected_scenario = call.data  # 获取用户选择的场景
    split_scenario = selected_scenario.split("scenario_")
    if len(split_scenario) > 1:
        split_scenario = split_scenario[1]  # 获取分割后的第二部分，即场景名称
    else:
        print("Error: Scenario name not found in the message")
    system_content = scenarios[split_scenario]
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
        # 创建新的按钮
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add(KeyboardButton('语音回复'))
        markup.add(KeyboardButton('文字回复'))
        bot.send_message(chat_id, f"你选择了场景: {split_scenario}，现在可以开始对话了。", reply_markup=markup)
    else:
        bot.send_message(chat_id, "请先/chat_end结束当前场景。")



# 示例的回调处理函数
def handle_callback_query(bot, call, scenarios, sessions):
    if call.data.startswith('scenario_'):
        handle_scenario_selection(bot, call, scenarios, sessions)


def handle_user_message(bot, message, sessions):
    chat_id = message.chat.id
    user_message = message.text

    # 检查用户是否选择了语音回复模式
    if user_message == '语音回复':
        user_reply_mode[chat_id] = 'voice'
        bot.send_message(chat_id, "已开启语音回复模式。接下来的会话消息都会以语音形式发送。")
        return
    
    # 检查用户是否选择了文字回复模式
    elif user_message == '文字回复':
        user_reply_mode[chat_id] = 'text'
        bot.send_message(chat_id, "已开启文字回复模式。接下来的会话消息都会以文字形式发送。")
        return
    
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
            "content": "拜拜"
        })
        # 使用send_api_request函数发送请求到API并接收返回的助手消息
        assistant_message = send_api_request(sessions[chat_id]["messages"])
        handle_chat_end_command(bot, message, assistant_message, sessions)
        return

    # 使用send_api_request函数发送请求到API并接收返回的助手消息
    assistant_message = send_api_request(sessions[chat_id]["messages"])
    
    
    assistant_message = assistant_message.split("你的描述")[0] 

    # 添加助手消息到会话
    sessions[chat_id]["messages"].append({
        "role": "assistant",
        "content": assistant_message
    })

    # 根据用户的回复模式发送相应的消息
    if user_reply_mode.get(chat_id) == 'voice':
        assistant_message = assistant_message.replace("~", "")
        assistant_message = add_uv_break(assistant_message)

        print(assistant_message)
        # 调用你的语音生成函数
        result = generate_and_send_voice_message(assistant_message)
        if result['code'] == 0:  # 检查是否成功
            urls = result['audio_files']
            for url in urls:  # 遍历所有 URL，因为可能有多个音频文件
                print(f"音频文件 URL: {url}")
                try:
                    audio = urlopen(url).read()
                    bot.send_audio(chat_id=chat_id, audio=audio)
                except Exception as e:
                    print(f"发送音频时出错: {str(e)}")
                    bot.reply_to(message, "抱歉，无法发送音频文件。")
        else:
            print(f"生成音频失败: {result['msg']}")
            # 可以选择向用户发送错误消息
            bot.send_message(chat_id=chat_id, text="抱歉，生成音频时出现错误。")
    else:
        # 默认以文字形式发送助手消息给用户
        bot.send_message(chat_id, assistant_message)

    # 检查会话消息数量，超过31条则删除第1条消息
    if len(sessions[chat_id]["messages"]) > 31:
        del sessions[chat_id]["messages"][1:3]
    

def generate_and_send_voice_message(assistant_message):
    tts_url = 'http://127.0.0.1:9966/tts'
    tts_data = {
        "text": assistant_message,
        "prompt": "",
        "voice": "11.csv",
        "speed": 5,
        "temperature": 0.02401,
        "top_p": 0.6,
        "top_k": 19,
        "refine_max_new_token": 384,
        "infer_max_new_token": 2048,
        "text_seed": 42,
        "skip_refine": 0,
        "is_stream": 0,
        "custom_voice": 5648
    }
    
    try:
        res = requests.post(tts_url, data=tts_data)
        response = res.json()
        
        if response['code'] == 0:
            audio_files = []
            for audio_file in response['audio_files']:
                local_path = audio_file['filename']
                
                # 上传文件到指定的服务器
                with open(local_path, 'rb') as file:
                    upload_res = requests.post('http://130.61.77.41:45704/', files={'file': file})
                
                if upload_res.status_code == 200:
                    download_url = upload_res.text.strip()  # 假设返回的是纯文本URL
                    audio_files.append(download_url)
                else:
                    return {'code': 1, 'msg': f'上传文件失败: {upload_res.text}'}
            
            return {'code': 0, 'msg': 'ok', 'audio_files': audio_files}
        else:
            return {'code': 1, 'msg': f"TTS生成失败：{response['msg']}"}
    except Exception as e:
        return {'code': 1, 'msg': f'处理过程中出错：{str(e)}'}


    
    

def send_api_request(session_messages):
    payload = {
        "messages": session_messages,
        "model": "gpt-3.5-turbo-16k",
        "stream": True,
        "temperature": 1.5,
        "presence_penalty": 0.8
    }

    url = "http://127.0.0.1:8000/v1/chat/completions"

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


def add_uv_break(text):
    # 定义标点符号
    punctuation = r'[，。？]'
    
    # 查找所有标点符号的位置
    matches = list(re.finditer(punctuation, text))
    
    # 创建一个新的字符串列表
    new_text = []
    last_index = 0
    
    for match in matches:
        start, end = match.span()
        
        # 将标点符号前的部分添加到新字符串列表中
        new_text.append(text[last_index:start + 1])
        
        # 随机决定是否添加 [uv_break]
        if random.choice([True, False]):
            new_text.append('[uv_break]')
        
        last_index = end
    
    # 添加剩余的部分
    new_text.append(text[last_index:])
    
    return ''.join(new_text)