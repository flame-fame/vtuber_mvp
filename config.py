# ==================== 配置文件 ====================
# 动作优先级\动作类型
from enum import Enum
from re import I
class ActionPriority(Enum):
    """数值越小，优先级越高 (0 > 1 > 2)"""
    IDLE = 3              # 空闲级：呼吸、眨眼（最低优先级）
    TALKING = 2           # 说话级：日常对话（中优先级，可打断空闲）
    REACTION = 1          # 反应级：感谢礼物、欢迎（高优先级，可打断说话）
    SYSTEM = 0            # 系统级：如报错、下播（最高优先级，可打断所有动作）

# VTube Studio 配置
VTS_CONFIG = {
    "ws_url": "ws://localhost:8001",
    "plugin_name": "MyAIVTuber",
    "plugin_developer": "LXL",
    "token_file": "token.txt",
}

# AI 配置
AI_CONFIG = {
    "model_name": "qwen2.5:7b",  # 或 "llama3.1:8b"
    "system_prompt": """
        你是一个傲娇的AI主播，性格毒舌但内心关心观众。
        要求：
        1. 回答必须简短，不超过50个汉字
        2. 语气要带点嘲讽，但偶尔流露出温柔
        3. 根据情绪在回答末尾加上表情标签和强度（0-1），只能使用以下标签：[Happy]、[Angry]、[Sad]、[Surprised]、[Peaceful]，示例：[Happy:0.8]、[Angry:0.5]、[Sad:0.3]、[Surprised:0.7]、[Peaceful:0.5]   
    """,
    "temperature": 0.85,
    "max_tokens": 100,
    "max_history": 10  # 保留最近10条对话
}

# TTS 配置
TTS_CONFIG = {
    "voice": "zh-CN-XiaoxiaoNeural",
    "rate": "+5%",
}

# 情绪静态基础配置：只存固定文件名、基础参数、系数、时长、优先级
EMOTION_BASE_CONFIG = {
    "Happy": {
        "expression_file": "Smile.exp3.json",
        "base_params": {
            "MouthOpen_base": 0.3,
            "MouthOpen_coeff": 0.3,
            "EyeOpenLeft_base": 0.7,
            "EyeOpenLeft_coeff": 0.3,
            "EyeOpenRight_base": 0.7,
            "EyeOpenRight_coeff": 0.3,
        },
        "duration": 2.0,
        "priority": ActionPriority.TALKING
    },
    "Angry": {
        "expression_file": "Angry.exp3.json",
        "base_params": {
            "MouthOpen": 0.2,
            "EyeOpenLeft": 0.4,
            "EyeOpenRight": 0.4,
            "FaceAngleY_base": 0,
            "FaceAngleY_coeff": -5
        },
        "duration": 1.5,
        "priority": ActionPriority.TALKING
    },
    "Surprised": {
        "expression_file": "Surprised.exp3.json",
        "base_params": {
            "MouthOpen_base": 0.7,
            "MouthOpen_coeff": 0.3,
            "EyeOpenLeft": 0.9,
            "EyeOpenRight": 0.9
        },
        "duration": 1.0,
        "priority": ActionPriority.TALKING
    },
    "Sad": {
        "expression_file": "Sad.exp3.json",
        "base_params": {
            "MouthOpen": 0.1,
            "EyeOpenLeft": 0.3,
            "EyeOpenRight": 0.3,
            "FaceAngleX_base": 0,
            "FaceAngleX_coeff": -3
        },
        "duration": 2.0,
        "priority": ActionPriority.TALKING
    },
    "Peaceful": {
        "expression_file": None,
        "base_params": {
            "MouthOpen": 0.0,
            "EyeOpenLeft": 0.7,
            "EyeOpenRight": 0.7
        },
        "duration": 1.0,
        "priority": ActionPriority.IDLE
    }
}

