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
        self.vts.init_animation_system("live2d_param_mapping.json", "face_param_mapping.json")
        self.thread = None
        self.scheduler = None
        self.tts.set_vts(self.vts, self.vts.player)  # 注入 VTS 和播放器


        # 在 AI 回复后调用：
        async def on_ai_response(self, emotion, action):
            await self.vts.set_expression(emotion, fade_time=1.0)      # 设置表情（持续）
            if action and action != "neutral":
                await self.vts.request_action(action, 1)  # 动作  

    async def run(self):  
        """主循环"""
        # 连接 VTS
        if not self.vts.connect():
            print("❌ 无法连接到 VTube Studio，请检查是否开启并配置了API。")
            exit(1)
        else:
            # 初始化动画系统（文件路径根据实际位置）
            self.scheduler = self.vts.init_animation_system("live2d_param_mapping.json", "face_param_mapping.json")
            # 启动调度器（异步）
            asyncio.create_task(self.scheduler.start())
            # 设置初始表情
            await self.vts.set_expression("neutral", fade_time=0.5)

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
                mode = 2
                if mode == 1:
                    try:
                        self.vts.activate_expression(emotion, active=True)
                        # 确保 TTS 引擎使用当前事件循环
                        self.tts.set_loop(asyncio.get_running_loop())
                        await self.tts._speak_async(reply_text)
                    finally:
                        self.vts.activate_expression(emotion, active=False)

                elif mode == 2:
                        # 1. 设置表情
                        self.vts.set_expression(emotion, fade_time=1.0)
                        
                        # 3. 创建 TTS 任务（不等待，让它们并发执行）
                        self.tts.set_loop(asyncio.get_running_loop())
                        await self.tts._speak_async(reply_text)
                    
                   
            except Exception as e:
                print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    app = AIVTuber()
    asyncio.run(app.run())