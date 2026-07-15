import time
import sys
from config import *
from ai_brain import AIBrain
from tts import TTSEngine
from action_scheduler import ActionScheduler

class AIVTuber:
    """AI主播主程序"""
    
    def __init__(self):
        # 初始化各模块
        self.action_scheduler = ActionScheduler()
        self.action_scheduler.on_action_start = self._on_action_start
        self.action_scheduler.on_action_end = self._on_action_end
        self.brain = AIBrain(AI_CONFIG["model_name"], AI_CONFIG["system_prompt"], AI_CONFIG["temperature"], AI_CONFIG["max_tokens"])
        self.tts = TTSEngine(TTS_CONFIG["voice"], TTS_CONFIG["rate"])
    
        # 运行状态
        self.running = True
        
    def start(self):
        """启动AI主播"""
        print("="*60)
        print("🤖 AI 主播 v2.0 (集成VTS)")
        print("="*60)
        
        # 1. 连接VTS
        if not self.action_scheduler:
            print("❌ 调度器初始化失败")
            return
        # 2. 主循环
        print("\n💡 输入 'quit' 退出，输入 'clear' 清空记忆")
        print("💡 输入 'reset' 重置VTS模型")
        print("-"*60)
        
        while self.running:
            try:
                # 获取用户输入
                user_input = input("\n👤 观众说: ").strip()
                
                if not user_input:
                    continue
                    
                # 处理命令
                if user_input.lower() in ['quit', 'exit', '退出']:
                    self.running = False
                    break
                elif user_input.lower() == 'clear':
                    self.brain.clear_history()
                    print("🧹 对话历史已清空")
                    continue
                elif user_input.lower() == 'reset':
                    self._reset_model()
                    continue
                
                # AI对话
                print("💬 AI 思考中...", end="", flush=True)
                start_time = time.time()
                
                ai_text, emotion, intensity = self.brain.chat(user_input)
                
                elapsed = time.time() - start_time
                print(f" (耗时 {elapsed:.2f}秒)")
                print(f"🤖 AI主播: {ai_text}")
                print(f"😊 情绪: {emotion}，强度：{intensity}")
                
                self._drive_model(emotion, intensity)

                # TTS语音
                if ai_text:
                    self.tts.speak(ai_text)
                
            except KeyboardInterrupt:
                self.running = False
                print("\n👋 再见！")
                break
            except Exception as e:
                print(f"⚠️ 发生错误: {e}")
        
        # 清理资源
        self._cleanup()

    def _reset_model(self):
        idle_action=self.action_scheduler.create_hotkey_action("Peaceful", priority=ActionPriority.HIGH)
        self.action_scheduler.add_action(idle_action, immediate=True)
        print("✅ VTS模型已重置为 'Peaceful'")

    def _drive_model(self, emotion: str, intensity: float = 1.0):
       self.action_scheduler.add_emotion_action(emotion, intensity, immediate=True)
       print(f"✅ VTS模型已驱动为 {emotion}，强度 {intensity}")
    
    def _cleanup(self):
        """清理资源"""
        self.action_scheduler.stop()
        print("👋 程序已退出")

    def _on_action_start(self, action):
        print(f"🎯 皮套动作: {action.action_id}")
    
    def _on_action_end(self, action):
        pass  # 或记录日志
    

# ================= 程序入口 =================
if __name__ == "__main__":
    app = AIVTuber()
    app.start()