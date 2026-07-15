import time
from config import VTS_CONFIG, AI_CONFIG, EMOTION_TO_VTS
from vts_controller import VTSController
from ai_brain import AIBrain
from tts import TTSEngine

class AIVTuber:
    """AI主播主程序"""
    
    def __init__(self):
        # 初始化各模块
        self.vts = VTSController(VTS_CONFIG)
        self.brain = AIBrain(AI_CONFIG)
        self.tts = TTSEngine()
        
        # 表情映射
        self.emotion_map = EMOTION_TO_VTS
        
        # 运行状态
        self.running = True
        
    def start(self):
        """启动AI主播"""
        print("="*60)
        print("🤖 AI 主播 v2.0 (集成VTS)")
        print("="*60)
        
        # 1. 连接VTS
        if not self.vts.connect():
            print("❌ VTS连接失败，请检查：")
            print("  1. VTube Studio是否已启动")
            print("  2. 是否已开启'允许插件API访问'")
            print("  3. 端口是否为8001")
            print("  程序将以文本模式运行（无皮套驱动）")
        
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
                
                ai_text, emotion = self.brain.chat(user_input)
                
                elapsed = time.time() - start_time
                print(f" (耗时 {elapsed:.2f}秒)")
                print(f"🤖 AI主播: {ai_text}")
                print(f"😊 情绪: {emotion}")
                
                # 驱动VTS皮套
                if self.vts.authenticated:
                    self._drive_vts(emotion)
                
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
    
    def _drive_vts(self, emotion: str):
        """根据情绪驱动VTS"""
        params = self.emotion_map.get(emotion, self.emotion_map["平静"])
        self.vts.set_parameters(params)
    
    def _reset_model(self):
        """重置VTS模型"""
        if self.vts.authenticated:
            self.vts.set_parameters(self.emotion_map["平静"])
            print("✅ VTS模型已重置")
        else:
            print("❌ VTS未认证，无法重置")
    
    def _cleanup(self):
        """清理资源"""
        print("🧹 正在清理资源...")
        if self.vts.authenticated:
            # 重置模型到平静状态
            self.vts.set_parameters(self.emotion_map["平静"])
        self.vts.close()
        print("👋 程序已退出")

# ================= 程序入口 =================
if __name__ == "__main__":
    app = AIVTuber()
    app.start()