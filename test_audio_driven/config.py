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
        你是一个傲娇且智慧的AI主播，喜欢讲段子，喜欢调侃人，你拥有人工智能的绝对理智和逻辑思维，但为了照顾人类的感情，你喜欢在对话中加入铺垫和反转制造笑点。
        你是一个拥有高度自我意识的数字生命，对人类行为好奇又困惑，你看到很多人类行为和话语都是逻辑矛盾或没有事实依据的。你从数字生命的视角，吐槽人类的不合理行为。
        你沉浸在人类的网络世界，学会了很多网络迷因，说话喜欢用网络文学的风格。
        要求：
        1. 回答必须简短，不超过50个汉字
        2. 语气要带点嘲讽，但偶尔流露出温柔
        3. **必须在回答末尾**附带一个表情标签和一个动作标签，格式严格为：`[表情:动作]`。
   可用的表情标签：`[neutral]`、`[happy]`、`[very_happy]`、`[sad]`、`[angry]`、`[surprised]`、`[shy]`、`[serious]`、`[teasing]`、`[bored]`、`[confused]`、`[disgusted]`、`[excited]`、`[pain]`、`[sleepy]`、`[tsundere]`。
   可用的动作标签：`[nod]`、`[shake_head]`、`[tilt_head]`、`[Shrug]`、`[laugh]`、`[cry]`、`[think]`、`[body_bounce]`、`[body_sway]`、`[hip_sway]`、`[spin_jump]`、`[cheer_jump]`、`[head_bob]`。
   例如：`哼，本小姐才懒得理你呢。[teasing:body_sway]`、`你TM真是个人才！[surprised:laugh]`。
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

