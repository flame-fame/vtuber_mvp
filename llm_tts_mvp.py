import asyncio
import ollama
import edge_tts
import pygame
import tempfile
import os
import time
import math
import threading
import requests
import json

# ================== 配置区 ==================
SYSTEM_PROMPT = """
你是一个傲娇的AI主播，性格毒舌但内心关心观众。
要求：
1. 回答必须简短，不超过30个汉字
2. 语气要带点嘲讽，但偶尔流露出温柔
3. 适当使用颜文字或emoji（如 (╯°□°)╯、❤️）
"""

MODEL_NAME = "qwen2.5:7b"
VOICE_NAME = "zh-CN-XiaoxiaoNeural"
VTUBE_PORT = 8001
# ============================================

# ================== VTube Studio 驱动类 ==================
class VTubeDriver:
    def __init__(self, port=8001):
        self.base_url = f"http://localhost:{port}/api/v1"
        self.connected = False
        
    def test_connection(self):
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=2)
            if response.status_code == 200:
                self.connected = True
                print("✅ 已连接 VTube Studio")
                return True
        except:
            print("❌ 无法连接 VTube Studio，请确保它已启动并开启API")
            return False
        return False
    
    def set_mouth_open(self, value):
        if not self.connected:
            return
        value = max(0.0, min(1.0, value))
        data = {"model": {"paramValues": [{"id": "MouthOpen", "value": value}]}}
        try:
            requests.post(f"{self.base_url}/parameter", json=data, timeout=1)
        except:
            pass
    
    def set_emotion(self, emotion):
        if not self.connected:
            return
        # 更新情绪参数映射，左右眼分别控制EyeOpenLeft和EyeOpenRight
        emotion_params = {
            "happy": {"EyeOpenLeft": 1.0, "EyeOpenRight": 1.0, "MouthForm": 0.8, "BrowHeightLeft": -0.5, "BrowHeightRight": -0.5},
            "angry": {"EyeOpenLeft": 0.7, "EyeOpenRight": 0.7, "MouthForm": -0.6, "BrowHeightLeft": 0.8, "BrowHeightRight": 0.8, "EyebrowAngleRight": 0.7},
            "sad": {"EyeOpenLeft": 0.5, "EyeOpenRight": 0.5, "MouthForm": -0.3, "BrowHeightLeft": 0.5, "BrowHeightRight": 0.5},
            "surprised": {"EyeOpenLeft": 1.2, "EyeOpenRight": 1.2, "MouthOpen": 0.9, "BrowHeightLeft": -0.8, "BrowHeightRight": -0.8},
            "neutral": {"EyeOpenLeft": 0.8, "EyeOpenRight": 0.8, "MouthOpen": 0.0, "MouthForm": 0.0, "BrowHeightLeft": 0.0, "BrowHeightRight": 0.0}
        }
        params = emotion_params.get(emotion, emotion_params["neutral"])
        param_values = [{"id": k, "value": v} for k, v in params.items()]
        data = {"model": {"paramValues": param_values}}
        try:
            requests.post(f"{self.base_url}/parameter", json=data, timeout=1)
        except:
            pass
    
    def close(self):
        self.set_emotion("neutral")
        self.set_mouth_open(0)

# ================== 核心功能函数 ==================
def get_ai_response(user_input):
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            options={
                "temperature": 0.85,
                "top_p": 0.9,
                "num_predict": 100,
            }
        )
        return response['message']['content'].strip()
    except Exception as e:
        print(f"❌ AI 接口报错: {e}")
        return "哼，本小姐现在不想说话！"

def parse_emotion(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ["哈哈", "开心", "笑", "可爱", "😊", "❤️"]):
        return "happy"
    elif any(word in text_lower for word in ["哼", "气", "讨厌", "揍", "😡"]):
        return "angry"
    elif any(word in text_lower for word in ["哎", "唉", "伤心", "哭", "😢"]):
        return "sad"
    elif any(word in text_lower for word in ["哇", "什么", "惊讶", "不会吧", "😮"]):
        return "surprised"
    else:
        return "neutral"

def mouth_animation_thread(duration, driver):
    start_time = time.time()
    elapsed = 0
    while elapsed < duration:
        # 用正弦波模拟说话节奏，频率12Hz，幅度0.1~0.8
        mouth_value = (math.sin(elapsed * 12) + 1) / 2 * 0.7 + 0.1
        driver.set_mouth_open(mouth_value)
        time.sleep(0.05)
        elapsed = time.time() - start_time
    driver.set_mouth_open(0)

async def text_to_speech(text):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_path = tmp_file.name
        
        communicate = edge_tts.Communicate(text, VOICE_NAME, rate="+5%")
        await communicate.save(tmp_path)
        
        pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
        
        pygame.mixer.quit()
        os.unlink(tmp_path)
        
    except Exception as e:
        print(f"❌ TTS 报错: {e}")

async def main():
    print("=" * 60)
    print("🤖 Neuro-lite AI 主播 (带Live2D驱动)")
    print("输入 'quit' 或 'exit' 退出程序")
    print("=" * 60)
    
    # 初始化VTube Studio
    vtube = VTubeDriver(port=VTUBE_PORT)
    if not vtube.test_connection():
        print("⚠️ 继续运行但皮套不会动，可以稍后重启VTube Studio")
    
    while True:
        user_input = input("\n👤 观众说: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '退出']:
            print("👋 拜拜！")
            if vtube.connected:
                vtube.close()
            break
        
        if not user_input:
            continue
        
        # 1. 获取AI回复
        print("💬 AI 思考中...", end="", flush=True)
        start_time = time.time()
        ai_text = get_ai_response(user_input)
        elapsed = time.time() - start_time
        print(f" (耗时 {elapsed:.2f}秒)")
        print(f"🤖 Neuro: {ai_text}")
        
        # 2. 解析情绪并设置表情
        emotion = parse_emotion(ai_text)
        if vtube.connected:
            vtube.set_emotion(emotion)
            print(f"🎭 情绪: {emotion}")
        
        # 3. 启动口型动画（预估语音时长）
        speech_duration = max(0.8, len(ai_text) * 0.12)
        if vtube.connected:
            mouth_thread = threading.Thread(
                target=mouth_animation_thread,
                args=(speech_duration, vtube)
            )
            mouth_thread.start()
        
        # 4. 播放语音
        await text_to_speech(ai_text)
        
        # 5. 等待口型线程结束
        if vtube.connected:
            mouth_thread.join()
            # 复位到中性
            vtube.set_emotion("neutral")

if __name__ == "__main__":
    asyncio.run(main())