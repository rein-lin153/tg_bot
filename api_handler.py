# api_handler.py
import requests
import json
import logging
from config import API_URL, API_TOKENS, MODEL_MAPPING, STYLE_MAPPING

logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_chat_request(model, user_message, system_message="", conversation_history=None, conversation_id=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_TOKENS[model]}"
    }

    if model == "qwen":
        data = {
            "model": "qwen",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }
        if conversation_id:
            data["conversation_id"] = conversation_id
    else:
        data = {
            "model": model,
            "messages": conversation_history if conversation_history else [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }
    # 打印请求数据
    logging.info(f"Sending request to {model}:")
    logging.info(f"Request data: {data}")

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        # 打印响应
        logging.info(f"Received response from {model}:")
        logging.info(f"Response status: {response.status_code}")
        logging.info(f"Response content: {response.text}")
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None

def get_model_name(selected_model):
    return MODEL_MAPPING.get(selected_model, "unknown_model")

def get_system_message(selected_style):
    return STYLE_MAPPING.get(selected_style, "")