import subprocess
import logging

logger = logging.getLogger(__name__)

def run_command(command):
    try:
        result = subprocess.run(command, check=True, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        return None

def stop_docker_service(service_name):
    command = f"docker stop {service_name}"
    output = run_command(command)
    if output:
        logger.info(f"Stopped Docker service: {service_name}")
        return True
    return False

def start_docker_service(service_name):
    command = f"docker start {service_name}"
    output = run_command(command)
    if output:
        logger.info(f"Started Docker service: {service_name}")
        return True
    return False

def switch_model(new_model):
    # 定义模型名称到Docker服务名称的映射
    model_to_service = {
        "跃问YueWen": "step-free-api",
        "阿里通义 (Qwen)": "qwen-free-api",
        "DeepSeek": "deepseek-free-api"
    }

    # 停止所有服务
    for service in model_to_service.values():
        stop_docker_service(service)

    # 启动新选择的服务
    if new_model in model_to_service:
        return start_docker_service(model_to_service[new_model])
    else:
        logger.error(f"Unknown model: {new_model}")
        return False