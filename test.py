import telebot
import requests
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen

# 替换为你的Bot Token
TOKEN = '7315961704:AAFmaiy0UfKr1uAa0q01RTQCu8O6FdpSM8A'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['test'])
def test_audio(message):
    # 替换为你要测试的音频 URL
    url = "http://130.61.77.41:45704/uploads/test.mp3"
    
    chat_id = message.chat.id
    
    # 首先尝试发送原始 URL
    print(f"尝试发送的 URL: {url}")
    try:
        audio = urlopen(url).read()
        bot.send_audio(chat_id=chat_id, audio=audio)
        bot.reply_to(message, "音频发送成功！")
    except Exception as e:
        print(f"发送音频时出错: {str(e)}")
        bot.reply_to(message, "抱歉，无法发送音频文件。")

# 启动机器人
bot.polling()