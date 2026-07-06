import ollama
import re
from typing import Tuple, Dict

class AIBrain:
    """AI 对话核心"""
    
    def __init__(self, config: Dict):
        self.model = config.get("model_name", "qwen2.5:7b")
        self.system_prompt = config.get("system_prompt", "")
        self.temperature = config.get("temperature", 0.85)
        self.max_tokens = config.get("max_tokens", 100)
        self.conversation_history = []
        self.max_history = 10  # 保留最近10条对话
        
    def chat(self, user_input: str) -> Tuple[str, str]:
        """
        与AI对话
        
        Returns:
            (ai_response, emotion): AI回复文本和情绪标签
        """
        try:
            # 构建消息列表
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]
            # 添加历史对话
            messages.extend(self.conversation_history[-self.max_history * 2:])
            # 添加当前用户输入
            messages.append({"role": "user", "content": user_input})
            
            # 调用模型
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            )
            
            ai_text = response['message']['content'].strip()
            
            # 提取情绪标签
            emotion = self._extract_emotion(ai_text)
            
            # 移除情绪标签（可选）
            clean_text = re.sub(r'\[(开心|生气|难过|惊讶|平静)\]$', '', ai_text).strip()
            
            # 更新历史
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": ai_text})
            
            return clean_text, emotion
            
        except Exception as e:
            print(f"❌ AI 接口报错: {e}")
            return "哼，本小姐现在不想说话！", "平静"
    
    def _extract_emotion(self, text: str) -> str:
        """从文本中提取情绪标签"""
        emotions = ["开心", "生气", "难过", "惊讶", "平静"]
        for emotion in emotions:
            if f"[{emotion}]" in text:
                return emotion
        return "平静"
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []