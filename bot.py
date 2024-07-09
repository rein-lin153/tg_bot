import logging
from logging.handlers import RotatingFileHandler
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from docker_manager import switch_model
from api_handler import send_chat_request, get_model_name, get_system_message
from config import TELEGRAM_BOT_TOKEN, MODEL_MAPPING, STYLE_MAPPING
import uuid
from datetime import datetime
import re


# 在全局范围内创建一个字典来存储所有用户的对话历史
all_user_chats = {}

# 设置 httpx 和 urllib3 的日志级别为 WARNING
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# 设置日志
log_file = os.path.join(os.path.dirname(__file__), 'bot.log')
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建一个RotatingFileHandler
file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# 将文件处理器添加到logger
logger.addHandler(file_handler)

# 替换为您的Bot Token
TOKEN = TELEGRAM_BOT_TOKEN

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text('欢迎使用VPS语言模型服务机器人！请使用 /chat_start 开始对话。')

async def chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 首先尝试移除之前的键盘
    await update.message.reply_text("正在准备新的对话...", reply_markup=ReplyKeyboardRemove())
    
    user_id = update.effective_user.id
    logger.info(f"User {user_id} initiated chat")
    
    # 清除之前的聊天数据
    context.user_data.clear()
    context.user_data['chat_initialized'] = True
    
    keyboard = [[KeyboardButton(model)] for model in MODEL_MAPPING.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('请选择一个语言模型:', reply_markup=reply_markup)


async def handle_model_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_choice = update.message.text
    logger.info(f"User {user_id} selected model: {user_choice}")

    if user_choice in MODEL_MAPPING:
        # 切换 Docker 服务
        if switch_model(user_choice):
            context.user_data['selected_model'] = user_choice
            # 直接调用 show_style_keyboard 函数
            await show_style_keyboard(update, context)
        else:
            await update.message.reply_text("切换模型失败，请稍后重试或联系管理员。")
    else:
        await update.message.reply_text("请使用提供的按钮选择一个模型。")

async def show_style_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton(style) for style in STYLE_MAPPING.keys()]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"您选择了 {context.user_data['selected_model']} 模型。请选择一个style:", reply_markup=reply_markup)

async def handle_style_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_choice = update.message.text
    logger.info(f"User {user_id} selected style: {user_choice}")

    if user_choice in STYLE_MAPPING:
        context.user_data['selected_style'] = user_choice
        selected_model = context.user_data.get('selected_model', '未知模型')
        
        # 创建新的聊天
        chat_id = str(uuid.uuid4())
        if user_id not in all_user_chats:
            all_user_chats[user_id] = {}

        chat_info = {
            'start_time': datetime.now(),
            'model': selected_model,
            'style': user_choice,
            'history': [{"role": "system", "content": get_system_message(user_choice)}],
            'title': "新对话"  # 初始化标题
        }

        # 对于 Qwen 模型，初始化 conversation_id 为 None
        if get_model_name(selected_model) == "qwen":
            chat_info['conversation_id'] = None
        
        all_user_chats[user_id][chat_id] = chat_info
        
        context.user_data['current_chat_id'] = chat_id
        context.user_data['chat_mode'] = True
        
        await update.message.reply_text(f"您选择了 {selected_model} 模型，{user_choice} style。现在可以开始聊天了，请发送您的消息。")
    elif user_choice == "返回":
        await chat_start(update, context)
    else:
        await update.message.reply_text("请使用提供的按钮选择一个style。")


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get('chat_mode', False):
        return

    user_id = update.effective_user.id
    chat_id = context.user_data.get('current_chat_id')
    user_message = update.message.text

    if not chat_id or chat_id not in all_user_chats[user_id]:
        await update.message.reply_text("当前没有活动的对话，请使用 /chat_start 开始新的对话。")
        return

    chat_info = all_user_chats[user_id][chat_id]
    selected_model = chat_info['model']
    selected_style = chat_info['style']
    model_name = get_model_name(selected_model)
    system_message = get_system_message(selected_style)

    # 记录用户消息到历史
    chat_info['history'].append({"role": "user", "content": user_message})

    # 检查历史长度
    if len(chat_info['history']) >= 50:
        # 生成总结
        summary = await generate_summary(chat_info, model_name)
        
        # 清空历史并插入总结
        chat_info['history'] = [
            {"role": "system", "content": system_message},
            {"role": "assistant", "content": f"以下是之前对话的总结：\n\n{summary}"}
        ]
        
        # 通知用户
        await update.message.reply_text("对话历史已经很长，我已经总结了之前的对话。让我们继续吧！")
    
    # 检查是否需要生成标题（每20条消息）
    if len(chat_info['history']) % 10 == 0:
        title = await generate_title(chat_info, model_name)
        chat_info['title'] = title
        await update.message.reply_text(f"已为当前对话生成标题：{title}")

    if model_name == "qwen":
        # 对于 Qwen 模型，使用 conversation_id
        conversation_id = chat_info.get('conversation_id')
        response = send_chat_request(model_name, user_message, system_message, conversation_id=conversation_id)
        if response and 'id' in response:
            # 更新 conversation_id，使用 response 中的 id 字段
            chat_info['conversation_id'] = response['id']
    else:
        # 对于其他模型，使用 conversation_history
        response = send_chat_request(model_name, user_message, system_message, conversation_history=chat_info['history'])


    # 从响应中提取 bot_response
    bot_response = response.get('choices', [{}])[0].get('message', {}).get('content', '对不起，我无法生成回复。')
    # 删除 "你的描述" 部分
    bot_response = remove_description(bot_response)

    if bot_response:
        # 记录助手回复到历史
        chat_info['history'].append({"role": "assistant", "content": bot_response})
        await update.message.reply_text(bot_response)
    else:
        await update.message.reply_text("抱歉，处理您的请求时出现了问题。请稍后再试。")


async def generate_title(chat_info, model_name):
    title_request = "请为以下对话生成一个简短的标题（不超过20个字符）：\n"
    # 只使用最近的10条消息来生成标题
    recent_messages = chat_info['history'][-10:]
    for message in recent_messages:
        if message['role'] != 'system':
            title_request += f"\n{message['role']}: {message['content'][:50]}..."  # 只使用每条消息的前50个字符

    system_message = get_system_message(chat_info['style'])
    response = send_chat_request(model_name, title_request, system_message)

    if response:
        title = response.get('choices', [{}])[0].get('message', {}).get('content', '未命名对话')
        return title[:20]  # 确保标题不超过20个字符
    else:
        return "未命名对话"

def remove_description(text):
    # 使用正则表达式匹配并删除 "你的描述：" 或 "你的描述:" 及其后面的内容
    pattern = r'你的描述.*?(?=\n|$)'
    return re.sub(pattern, '', text, flags=re.DOTALL).strip()

async def generate_summary(chat_info, model_name):
    summary_request = "请总结以下对话的主要内容，保持简洁但包含关键信息："
    for message in chat_info['history']:
        if message['role'] != 'system':
            summary_request += f"\n{message['role']}: {message['content']}"
    
    system_message = get_system_message(chat_info['style'])
    response = send_chat_request(model_name, summary_request, system_message)
    
    if response:
        summary = response.get('choices', [{}])[0].get('message', {}).get('content', '无法生成总结。')
        return summary
    else:
        return "无法生成总结。"



async def chat_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in all_user_chats or not all_user_chats[user_id]:
        await update.message.reply_text("您没有任何历史对话。")
        return
    
    chat_list = []
    for chat_id, chat_info in all_user_chats[user_id].items():
        if chat_info['history']:  # 只有有历史记录的对话才显示
            title = chat_info.get('title', '未命名对话')
            chat_list.append(f"/restore_{chat_id[:8]} - {title} - 日期: {chat_info['start_time'].strftime('%Y-%m-%d %H:%M')} - 模型: {chat_info['model']} - Style: {chat_info['style']}")
    
    if chat_list:
        await update.message.reply_text("您的历史对话列表:\n" + "\n".join(chat_list))
    else:
        await update.message.reply_text("您没有任何有效的历史对话。")


async def restore_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id_prefix = update.message.text[9:]  # 去掉 "/restore_" 前缀
    
    if user_id not in all_user_chats:
        await update.message.reply_text("您没有任何历史对话。")
        return

    full_chat_id = None
    for chat_id in all_user_chats[user_id]:
        if chat_id.startswith(chat_id_prefix):
            full_chat_id = chat_id
            break
    
    if not full_chat_id:
        await update.message.reply_text("无效的对话ID。")
        return
    
    chat_info = all_user_chats[user_id][full_chat_id]
    context.user_data['current_chat_id'] = full_chat_id
    context.user_data['selected_model'] = chat_info['model']
    context.user_data['selected_style'] = chat_info['style']
    context.user_data['chat_mode'] = True
    

    history = chat_info['history'][-20:]  # 只显示最近的 20 条消息

    # 切换到相应的模型
    if switch_model(chat_info['model']):
        await update.message.reply_text(f"已恢复对话。模型: {chat_info['model']}, Style: {chat_info['style']}")
        
        # 显示完整的对话历史
        history = chat_info['history']
        
        # 将历史记录分成多个块，每块最多 4000 字符
        chunks = []
        current_chunk = ""
        for msg in history:
            message_text = f"{msg['role']}: {msg['content']}\n\n"
            if len(current_chunk) + len(message_text) > 4000:
                chunks.append(current_chunk)
                current_chunk = message_text
            else:
                current_chunk += message_text
        if current_chunk:
            chunks.append(current_chunk)
        
        # 发送对话历史
        await update.message.reply_text("对话历史：")
        for chunk in chunks:
            await update.message.reply_text(chunk)
        
        await update.message.reply_text("对话已恢复，您可以继续聊天了。")
    else:
        await update.message.reply_text("恢复对话失败，无法切换到所需模型。")

async def chat_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    if 'current_chat_id' not in context.user_data:
        await update.message.reply_text("当前没有进行中的对话。")
        return
    
    chat_id = context.user_data['current_chat_id']
    
    if user_id in all_user_chats and chat_id in all_user_chats[user_id]:
        # 保存当前对话的最终状态
        all_user_chats[user_id][chat_id]['end_time'] = datetime.now()
        
        # 清理用户数据
        del context.user_data['current_chat_id']
        context.user_data['chat_mode'] = False
        context.user_data['selected_model'] = None
        context.user_data['selected_style'] = None
        
        # 尝试方法1：使用 selective=True
        reply_markup = ReplyKeyboardRemove(selective=True)
        await update.message.reply_text("对话已结束。您可以使用 /chat_start 开始新的对话，或使用 /chat_list 查看历史对话。", reply_markup=reply_markup)
        
        # 尝试方法2：发送空的自定义键盘
        empty_keyboard = ReplyKeyboardMarkup([[]], resize_keyboard=True)
        await update.message.reply_text("谢谢使用！", reply_markup=empty_keyboard)
        
        # 尝试方法3：在发送消息之前设置 reply_markup
        await update.message.reply_text("键盘已移除。", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("无法找到当前对话。可能已经结束或发生了错误。")

    logger.info(f"Chat ended for user {user_id}, chat_id: {chat_id}")

def main() -> None:
    application = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("chat_start", chat_start))
    application.add_handler(CommandHandler("chat_end", chat_end))
    application.add_handler(CommandHandler("chat_list", chat_list))
    application.add_handler(MessageHandler(filters.Regex(r'^/restore_'), restore_chat))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: 
        handle_chat_message(update, context) if context.user_data.get('chat_mode', False) 
        else (handle_style_selection(update, context) if 'selected_model' in context.user_data 
        else handle_model_selection(update, context))))

    application.run_polling()
    logger.info("Bot stopped")

if __name__ == '__main__':
    main()