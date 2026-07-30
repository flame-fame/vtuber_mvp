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
    PARAMETER = "parameter"        # 参数调整
    HOTKEY = "hotkey"              # 热键
    MOVE = "move"                  # 模型移动
    COMPOSITE = "composite"        # 复合动作

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
        你是一个傲娇的AI主播，性格毒舌爱怼人爱说土味情话爱冷嘲热讽但内心关心观众。
        要求：
        1. 回答必须简短，不超过50个汉字
        2. 语气要带点嘲讽，但偶尔流露出温柔
        3. **必须在回答末尾**附带一个表情标签和一个动作标签，格式严格为：`[表情:动作]`。
   可用的表情标签：`[UnHappy]`、`[Blush]`、`[Smile]`、`[Stunned]`、`[BadSmile]`、`[Woosh]`、`[Dislike]`、`[Sad]`、`[Normal]`。
   可用的动作标签：`[Agree]`、`[Confused]`、`[Disagree]`、`[Shy]`、`[Happy]`、`[Neutral]`、`[Blink]`、`[Laugh]`、`[Surprised]`、`[LookDown]`。
   例如：`哼，本小姐才懒得理你呢。[WhiteEye:LookDown]`
   如果回答中没有标签，则视为无效回答，我会重新生成。
        """,
    "temperature": 0.85,
    "max_tokens": 500,
    "max_history": 1000  # 保留最近1000条对话
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
# ==================== 情绪→表情/动作映射 ====================
# type: "expression" 或 "action"
# resource: 表情文件名（不含.exp3.json后缀）或动作热键名称
EMOTION_MAPPING = {
    "Agree": {"type": "action", "resource": "NodShake"},      # 同意 → 动作
    "Confused": {"type": "action", "resource": "ConfuseShake"},      # 不理解 → 动作
    "Disagree": {"type": "action", "resource": "WhiteEyeShake"},    # 不同意 → 动作
    "Shy": {"type": "action", "resource": "BlushShake"},      # 害羞 → 动作 
    "Happy": {"type": "action", "resource": "HappyShake"},   
    "Neutral": {"type": "action", "resource": "GentleShake"}, 
    "Blink": {"type": "action", "resource": "QuickBlink"}, 
    "Laugh": {"type": "action", "resource": "HappyHand"}, 
    "Surprised": {"type": "action", "resource": "SurprisedMouth"}, 
    "LookDown": {"type": "action", "resource": "LookDown"}, 
    "UnHappy": {"type": "expression", "resource": "Angry"},  
    "Sad": {"type": "expression", "resource": "Sad"},    
    "Blush": {"type": "expression", "resource": "Blushing"},         
    "Smile": {"type": "expression", "resource": "Smile"},       # 惊讶
    "Stunned": {"type": "expression", "resource": "Stuned"},          # 伤心 → 表情
    "Woosh": {"type": "expression", "resource": "Surprised"}, 
    "BadSmile": {"type": "expression", "resource": "BadSmile"},  
    "Dislike": {"type": "expression", "resource": "WhiteEye"},  
    "Normal": {"type": "expression", "resource": "Normal"},      # 平静 → 无表情（或可改为"冷漠"）
}
