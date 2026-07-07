# ==================== 配置文件 ====================

# VTube Studio 配置
VTS_CONFIG = {
    "ws_url": "ws://localhost:8001",
    "plugin_name": "MyAIVTuber",
    "plugin_developer": "LXL",
    "reconnect_attempts": 3,
    "reconnect_delay": 2  # 秒
}

# AI 配置
AI_CONFIG = {
    "model_name": "qwen2.5:7b",  # 或 "llama3.1:8b"
    "system_prompt": """
        你是一个傲娇的AI主播，性格毒舌但内心关心观众。
        要求：
        1. 回答必须简短，不超过50个汉字
        3. 语气要带点嘲讽，但偶尔流露出温柔
        4. 不使用颜文字或emoji（如 (╯°□°)╯、❤️）
        5. 根据情绪在回答末尾加上表情标签：[开心]、[生气]、[难过]、[惊讶]、[平静]   
    """,
    "temperature": 0.85,
    "max_tokens": 100
}

# 参数映射：AI情绪 -> VTS参数
EMOTION_TO_VTS = {
    "开心": {"MouthSmile": 1, "EyeSmileLeft": 1, "EyeSmileRight": 1, "BrowFormRight": 1, "BrowFormLeft": 1,},
    "生气": {"MouthSmile": 0.0, "EyeSmileLeft": 0, "EyeSmileRight": 0, "BrowFormRight": 0.8, "BrowFormLeft": 0.8, "FaceAngleY": -10.0},
    "难过": {"MouthSmile": -1, "EyeSmileLeft": 0, "EyeSmileRight": 0, "BrowFormRight": -0.8, "BrowFormLeft": -0.8, "FaceAngleX": -5.0},
    "惊讶": {"MouthOpen": 0.9, "EyeOpenLeft": 1.0, "EyeOpenRight": 1.0, "FaceAngleY": 0.0},
    "害羞": {"MouthShape": 0.3, "EyeOpenLeft": 0.5, "EyeOpenRight": 0.5, "FaceAngleX": 0.0, "FaceAngleY": 0.0},
    "思考": {"MouthShape": 0.3, "EyeOpenLeft": 0.5, "EyeOpenRight": 0.5, "FaceAngleX": 0.0, "FaceAngleY": 0.0},
    "平静": {"MouthOpen": 0.0, "EyeOpenLeft": 0.7, "EyeOpenRight": 0.7, "FaceAngleX": 0.0, "FaceAngleY": 0.0}
}