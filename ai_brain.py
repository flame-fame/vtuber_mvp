import ollama
import re
from typing import Tuple, Dict
from config import *

class AIBrain:
    """AI 对话核心"""
    
    def __init__(self, model_name: str , system_prompt: str, temperature: float, max_tokens: int):
        self.model = model_name
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.conversation_history = []
        self.max_history = AI_CONFIG["max_history"]  # 保留最近10条对话
        
    def chat(self, user_input: str) -> Tuple[str, str, float]:
        """
        与AI对话
        
        Returns:
            (ai_response, emotion, intensity): AI回复文本和情绪强度值
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
             # 提取强度值
            intensity = self._extract_intensity(ai_text)
            
            # 移除情绪标签
            clean_text = re.sub(r'\[(\w+):([0-9.]+)\]$', '', ai_text).strip()
            
            # 更新历史
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": ai_text})
            
           
            
            return clean_text, emotion, intensity
            
        except Exception as e:
            # 打印错误信息  
            print(f"❌ AI 接口报错: {e}")
            return "哼，本小姐现在不想说话！", "Peaceful", 0.5
    
    def _extract_emotion(self, text: str) -> str:
        """从文本中提取情绪标签"""
        emotions = ["Happy", "Angry", "Sad", "Surprised", "Peaceful"]
        for emotion in emotions:
            if f"[{emotion}]" in text:
                return emotion
        return "Peaceful"
            
    def _extract_intensity(self, text: str) -> float:
        """从文本中提取强度值"""
        # 匹配格式如 [Happy:0.8] 或 [Sad:0.5]
        match = re.search(r'\[(\w+):([0-9.]+)\]', text)
        if match:
            return float(match.group(2))
        return 0.5  # 默认强度值
    
    
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []