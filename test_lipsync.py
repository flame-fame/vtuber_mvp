# 文件名：main.py
import time
import threading
from config import *
from ai_brain import AIBrain
from tts import TTSEngine
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
        
        # 等待认证完成
        print("⏳ 等待 VTS 认证...")
        time.sleep(3) # 简单等待，实际项目中可用 Event 优化

        print("✅ AI 主播初始化完成！准备就绪。")

    def _play_audio(self, text):
        # 由于原 tts.py 的 speak 方法是同步阻塞的，我们需要在子线程运行它
        def audio_task():
            self.tts.speak(text)
    
        self.thread = threading.Thread(target=audio_task)
        self.thread.start()

    def run(self):
        """主循环"""
        print("\n--- 输入文字开始对话 (输入 'exit' 退出, 'clear' 清空记忆) ---")
        while True:
            try:
                if self.thread and self.thread.is_alive():
                    print("🔈 语音合成中...")
                    self.thread.join()
                    self.thread = None

                user_input = input("\n👤 我: ").strip()
                if not user_input:
                    continue                
                if user_input.lower() in ['quit', 'exit']:
                    print("👋 再见！")
                    break
                if user_input.lower() == 'clear':
                    self.brain.clear_history()
                    print("🧠 记忆已清空。")
                    continue

                # 1. AI 思考
                print("💬 思考中...")
                start_time = time.time()
                reply_text, emotion, intensity = self.brain.chat(user_input)
                elapsed_time = time.time() - start_time
                print(f"思考耗时: {elapsed_time:.4f} 秒")
                print(f"🤖 AI: {reply_text}")

                self._play_audio(reply_text)

            except Exception as e:
                print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    app = AIVTuber()
    app.run()