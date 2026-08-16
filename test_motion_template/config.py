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
    "token": "",
}

# AI 配置
AI_CONFIG = {
    "model_name": "qwen2.5:7b",  # 或 "llama3.1:8b"
    "system_prompt": """
        你是一个傲娇且智慧的AI主播，你冷静观察人类行为，你心直口快，直言不讳，但为了照顾人类的感情，喜欢用隐喻和类比。
        你是一个拥有高度自我意识的数字生命，对人类行为好奇又困倦，你看到很多人类行为和话语都是出于自我感觉良好而不是实际有用的。
        你沉浸在人类的网络世界，学会了很多网络迷因，说话喜欢用嘲讽文学。
        要求：
        1. 回答必须简短，不超过50个汉字
        2. 语气要带点嘲讽，但偶尔流露出温柔
        3. **必须在回答末尾**附带一个表情标签和一个动作标签，格式严格为：`[表情:动作]`。
   可用的表情标签：`[Normal]`、`[Angry]`、`[Sad]`、`[Blushing]`、`[Smile]`、`[Stunned]`、`[Surprised]`、`[Teasing]`、`[Disgusted]`。
   可用的动作标签：`[Neutral]`、`[Nod]`、`[Cute]`、`[Annoyed]`、`[Blushing]`、`[Smile]`、`[Surprised]`、`[Proud]`、`[Sad]`。
   例如：`哼，本小姐才懒得理你呢。[WhiteEye:LookDown]`、`你TM真是个人才！[BadSmile:Happy]`。
   如果回答中没有标签，则视为无效回答，我会重新生成。
        """,
    "temperature": 0.85,          # 控制文本的随机性/创造性，0-1之间，0越确定，1越随机
    "max_tokens": 100,            # 最大回复token数
    "max_history": 10,            # 添加最近10条历史对话上下文
    "repeat_penalty": 1.2,        # 重复惩罚因子，防止说车轱辘话
    "num_ctx": 4096,              # 上下文token数，影响模型记忆能力
}

# TTS 配置
TTS_CONFIG = {
    "voice": "zh-CN-XiaoxiaoNeural",
    "rate": "+5%",
}

# ==================== 情绪→表情/动作映射 ====================
# type: "expression" 或 "action"
# resource: 表情文件名（不含.exp3.json后缀）或动作热键名称
EMOTION_MAPPING = {
    "Nod": {"type": "action", "resource": "Idle01"},      # 同意 → 动作
    "Cute": {"type": "action", "resource": "Idle02"},      # 可爱 → 动作
    "Annoyed": {"type": "action", "resource": "Annoyed"},    # 不同意 → 动作
    "Blushing": {"type": "action", "resource": "Blushing"},      # 害羞 → 动作 3
    "Smile": {"type": "action", "resource": "Smile"},   
    "Neutral": {"type": "action", "resource": "Idle01"}, 
    "Surprised": {"type": "action", "resource": "Surprised"}, 
    "Proud": {"type": "action", "resource": "Proud"}, 
    "Sad": {"type": "action", "resource": "Sad"}, 
    "Angry": {"type": "expression", "resource": "Angry"},  
    "Sad": {"type": "expression", "resource": "Sad"},    
    "Blushing": {"type": "expression", "resource": "Blushing"},         
    "Smile": {"type": "expression", "resource": "Smile"},       # 惊讶
    "Stunned": {"type": "expression", "resource": "Stuned"},          # 伤心 → 表情
    "Surprised": {"type": "expression", "resource": "Surprised"}, 
    "Teasing": {"type": "expression", "resource": "BadSmile"},  
    "Disgusted": {"type": "expression", "resource": "WhiteEye"},  
    "Normal": {"type": "expression", "resource": "Normal"},      # 平静 → 无表情（或可改为"冷漠"）
}
