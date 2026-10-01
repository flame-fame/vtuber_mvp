import ollama
import re
import asyncio
import random
import time
from datetime import datetime
from typing import Tuple, Dict
from config import *
from memory_manager import MemoryManager
from persona import PersonaLoader
from strategy_router import StrategyRouter


class AIBrain:
    """AI 对话核心"""
    
    def __init__(self):
        # 1. 加载人格
        self.persona = PersonaLoader(PERSONA_CONFIG['path'])
        self.system_prompt = self.persona.build_system_prompt()

        # 2. 模型参数
        self.model = AI_CONFIG["model_name"]
        self.temperature = AI_CONFIG["temperature"]
        self.max_tokens = AI_CONFIG["max_tokens"]

        # 3. 历史与状态
        self.conversation_history = []
        self.max_history = AI_CONFIG["max_history"]
        self.emotions_list = [
            "neutral", "happy", "very_happy", "sad", "angry", "surprised",
            "shy", "serious", "teasing", "bored", "confused", "disgusted",
            "excited", "pain", "sleepy", "tsundere"
        ]
        self.actions_list = [
            "nod", "shake_head", "tilt_head", "shrug", "laugh", "cry", "think",
            "body_bounce", "body_sway", "hip_sway", "spin_jump", "cheer_jump", "head_bob"
        ]
        self.last_interaction_time = time.time()

        # 4. 记忆库 + 预注入信念
        self.memory = MemoryManager()
        self._preload_beliefs()

        # 5. 策略路由
        self.router = StrategyRouter(self, persona=self.persona)

        print(f"🎭 人格已加载：{self.persona.get_meta().get('name')}")
        print(f"🧭 策略权重：{self.router.weights}")

    def _preload_beliefs(self):
        """启动时把人设信念注入记忆库（仅一次，去重由 add_memory 处理）"""
        beliefs = self.persona.get_beliefs()
        for b in beliefs:
            self.memory.add_memory(
                content=b["statement"],
                topic=b["category"],
                speaker="self",
                keywords=b.get("keywords", [])
            )
        print(f"📖 已预注入 {len(beliefs)} 条人格信念")

    async def chat(self, user_input: str) -> Tuple[str, str, float]: 
        """
        与AI对话
        Returns:
            (ai_response, emotion, action): AI回复文本和情绪标签、动作标签
        """
        try:
            # 1. 策略路由选一个策略
            strategy = self.router.pick(user_input)
            print(f"🎯 策略: {strategy.name}")

            # 2. 策略生成增强 prompt
            enhanced_input = strategy.build_prompt(user_input)

            # 3. 构建消息
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history[-self.max_history:])
            messages.append({"role": "user", "content": enhanced_input})
            
            # 调用模型
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        ollama.chat,
                        model=self.model,
                        messages=messages,
                        options={
                            "temperature": self.temperature,
                            "num_predict": self.max_tokens,
                        }
                    ),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                print("❌ AI思考超时")
                return "思考太久了，本小姐走神了！", "bored", "think"
            
            ai_text = response['message']['content'].strip()
            
            # 提取情绪标签
            emotion = self._extract_emotion(ai_text)
            # 提取动作标签
            action = self._extract_action(ai_text)
            #print(f"💦 extracted Emotion: {emotion}, Action: {action}")
            
            # 移除情绪标签
            clean_text = self.clean_response_text(ai_text)
            
            # 更新历史
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": ai_text})
            self.last_interaction_time = time.time()
    
            print(f"🤖 AI 回复: {ai_text}")
            return clean_text, emotion, action
            
        except Exception as e:
            # 打印错误信息  
            print(f"❌ AI 接口报错: {e}")
            return "哼，本小姐现在不想说话！", "neutral", "think"


    # ---------- 文本清理 ----------
    def clean_response_text(self, ai_text: str) -> str:
        """清理响应文本，移除情绪标签和动作标签"""
        # 1. 先统一将全角括号转为半角
        ai_text_fixed = ai_text.replace('［', '[').replace('］', ']')
        # 2. 移除所有 [xxx:yyy] 或 [xxx] 或 [xxx]:yyy 模式的标签（不限于末尾）
        clean_text = re.sub(r'\[[^\[\]]*\]|\[[^\[\]]*\]:[^\[\]]*', '', ai_text_fixed).strip()
        # 处理残留的冒号分隔（如 [@_@]:Smile 这种）
        clean_text = re.sub(r'\[[^\[\]]*\]:[^\[\]]*', '', clean_text).strip()
        return clean_text
    
    def format_history_for_prompt(self) -> str:
        """格式化对话历史，准备用于模型输入"""
        if not self.conversation_history:
            return "暂无历史对话"
        history_text = ""
        for msg in self.conversation_history[-5:]:  # 最近5条
            role = "用户" if msg["role"] == "user" else "AI"
            content = msg["content"][:50]  # 截断过长的内容
            history_text += f"{role}: {content}\n"
        return history_text
    
    def _extract_emotion(self, text):
         # 先统一括号为半角
        text = text.replace('［', '[').replace('］', ']')
        # 优先匹配 [表情:动作] 中的表情部分
        match = re.search(r'\[(\w+):', text)
        if match and match.group(1) in self.emotions_list:
            return match.group(1)
        # 再尝试匹配单独的 [表情]
        for emo in self.emotions_list:
            if f"[{emo}]" in text:
                return emo
        return "neutral"
    
    def _extract_action(self, text: str) -> str:
        """从文本中提取动作标签"""
        text = text.replace('［', '[').replace('］', ']')
        # 先匹配 [表情:动作] 中的动作
        match = re.search(r':(\w+)\]', text)
        if match and match.group(1) in self.actions_list:
            return match.group(1)
        # 再匹配单独的 [动作] 或 [表情]:动作 中的动作
        for action in self.actions_list:
            if f"[{action}]" in text or f"]:{action}" in text:
                return action
        return "think"

    def _extract_intensity(self, text: str) -> float:
        """从文本中提取强度值"""
        # 匹配格式如 [Happy:0.8] 或 [Sad:0.5]
        match = re.search(r'\[(\w+):([0-9.]+)\]', text)
        if match:
            return float(match.group(2))
        return 0.5  # 默认强度值
    
    # ---------- 关闭 ----------
    def close(self):
        """关闭时调用"""
        self.clear_history()
        print("🧠 记忆已清空。")

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []

    def update_last_interaction(self):
        """更新最近一次交互"""
        self.last_interaction_time = time.time()