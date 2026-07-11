# ==================== 配置文件 ====================
# 动作优先级\动作类型
from enum import Enum
class ActionPriority(Enum):
    """动作优先级（数值越高优先级越高）"""
    BACKGROUND = 0      # 背景级：空闲状态
    LOW = 1             # 低：默认表情
    NORMAL = 2          # 普通：情绪表达
    HIGH = 3            # 高：重要反应
    CRITICAL = 4        # 关键：打断当前所有动作

class ActionType(Enum):
    """动作类型"""
    EXPRESSION = "expression"      # 表情文件
    ANIMATION = "animation"        # 动作文件
    PARAMETER = "parameter"        # 参数调整
    HOTKEY = "hotkey"              # 热键
    MOVE = "move"                  # 模型移动
    COMPOSITE = "composite"        # 复合动作

# VTube Studio 配置
VTS_CONFIG = {
    "ws_url": "ws://localhost:8001",
    "plugin_name": "MyAIVTuber",
    "plugin_developer": "LXL",
    "token_file": "vts_token.txt",
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
        "priority": ActionPriority.NORMAL
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
        "priority": ActionPriority.NORMAL
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
        "priority": ActionPriority.HIGH
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
        "priority": ActionPriority.NORMAL
    },
    "Peaceful": {
        "expression_file": None,
        "base_params": {
            "MouthOpen": 0.0,
            "EyeOpenLeft": 0.7,
            "EyeOpenRight": 0.7
        },
        "duration": 1.0,
        "priority": ActionPriority.BACKGROUND
    }
}

