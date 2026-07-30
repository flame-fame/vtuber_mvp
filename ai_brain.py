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
        self.max_history = AI_CONFIG["max_history"]  
        self.emotions_list = ["UnHappy", "Blush", "Smile", "Stunned", "BadSmile", "Woosh", "Dislike", "Sad", "Normal"]
        self.actions_list = ["Agree", "Confused", "Disagree", "Shy", "Happy", "Neutral", "Blink", "Laugh", "Surprised", "LookDown"]
        
    def chat(self, user_input: str) -> Tuple[str, str, float]:
        """
        与AI对话
        
        Returns:
            (ai_response, emotion, action): AI回复文本和情绪标签、动作标签
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
            print(f"🤖 AI Text: {ai_text}")
            # 提取情绪标签
            emotion = self._extract_emotion(ai_text)
             # 提取强度值
            #intensity = self._extract_intensity(ai_text)
            # 提取动作标签
            action = self._extract_action(ai_text)
            print(f"💦 extracted Emotion: {emotion}, Action: {action}")
            
            # 移除情绪标签
            clean_text = re.sub(r'\[(\w+):([\w+]+)\]$', '', ai_text).strip()
            
            # 更新历史
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": ai_text})
            
           
            
            return clean_text, emotion, action
            
        except Exception as e:
            # 打印错误信息  
            print(f"❌ AI 接口报错: {e}")
            return "哼，本小姐现在不想说话！", "Normal", "Neutral"
    
    def _extract_emotion(self, text):
        # 优先匹配 [表情:动作] 中的表情部分
        match = re.search(r'\[(\w+):', text)
        if match and match.group(1) in self.emotions_list:
            return match.group(1)
        # 再尝试匹配单独的 [表情]
        for emo in self.emotions_list:
            if f"[{emo}]" in text:
                return emo
        return "Normal"
    
    def _extract_action(self, text: str) -> str:
        """从文本中提取动作标签"""
        for action in self.actions_list:
            if f"[{action}]" in text:
                return action
        return "Neutral"

    def _extract_intensity(self, text: str) -> float:
        """从文本中提取强度值"""
        # 匹配格式如 [Happy:0.8] 或 [Sad:0.5]
        match = re.search(r'\[(\w+):([0-9.]+)\]', text)
        if match:
            return float(match.group(2))
        return 0.5  # 默认强度值
    
    
    def close(self):
        """关闭时调用"""
        self.clear_history()
        print("🧠 记忆已清空。")

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []