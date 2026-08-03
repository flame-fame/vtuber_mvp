# 文件名：main.py
import time
import threading
import asyncio
from config import *
from ai_brain import AIBrain
from tts_engine import TTSEngine
from vts_controller import VTSController

class AIVTuber:
    def __init__(self):
        print("🚀 正在初始化 AI 主播核心...")
        # 1. 初始化组件
        self.brain = AIBrain(
            model_name=AI_CONFIG["model_name"],
            system_prompt=AI_CONFIG["system_prompt"],
            temperature=AI_CONFIG["temperature"],
            max_tokens=AI_CONFIG["max_tokens"]
        )
        self.tts = TTSEngine(voice=TTS_CONFIG["voice"], rate=TTS_CONFIG["rate"])
        self.vts = VTSController()
        self.thread = None

        # 2. 连接 VTS
        if not self.vts.connect():
            print("❌ 无法连接到 VTube Studio，请检查是否开启并配置了API。")
            exit(1)

    async def run(self):  
        """主循环"""
        print("\n--- 输入文字开始对话 (输入 'quit' 退出, 'history' 查看历史, 'clear' 清空记忆) ---")
        while True:
            try:
                time.sleep(0.5)
                user_input = input("\n👤 我: ").strip()
                if not user_input:
                    continue                
                if user_input.lower() == 'quit':
                    self.brain.close()
                    print("👋 再见！")
                    break
                if user_input.lower() == 'history':
                    for item in self.brain.conversation_history:
                        print(item)
                    continue
                if user_input.lower() == 'clear':
                    await self.brain.clear_history()
                    print("🧠 记忆已清空。")
                    continue

                # 1. AI 思考
                print("💬 思考中...")
                start_time = time.time()
                reply_text, emotion, action = await self.brain.chat(user_input)
                elapsed_time = time.time() - start_time
                print(f"思考耗时: {elapsed_time:.4f} 秒")
                
                try:
                    self.vts.activate_expression(emotion, active=True)
                    # 确保 TTS 引擎使用当前事件循环
                    self.tts.set_loop(asyncio.get_running_loop())
                    await self.tts._speak_async(reply_text)
                finally:
                    self.vts.activate_expression(emotion, active=False)

            except Exception as e:
                print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    app = AIVTuber()
    asyncio.run(app.run())