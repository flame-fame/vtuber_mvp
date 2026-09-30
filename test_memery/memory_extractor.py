# memory_extractor.py
"""
记忆提取器：用 Ollama 把对话压缩成结构化摘要
"""
import ollama
import asyncio
import re
import json
from config import AI_CONFIG


EXTRACT_PROMPT = """你是一个信息提取助手。请从对话中提取用户的核心兴趣点。

要求：
1. 输出严格的 JSON，不要任何解释
2. 格式：{{"topic": "话题标签", "content": "扩充后的用户兴趣摘要", "keywords": ["关键词1", "关键词2"]}}
3. content 要求 30~50 字，必须包含"上位概念"和"具体细节"
4. keywords 是 3~5 个可以被检索到的中文词
5. 只要用户提到任何具体事物（宠物、地点、职业、爱好、情绪事件），就必须提取
6. 只有当用户输入完全无意义（如"嗯"、"哦"、"哈哈"）时，才返回空

示例 1：
对话：用户说"我今天在原神里抽到胡桃了！"，AI说"恭喜！"
输出：{{"topic": "原神", "content": "用户是游戏玩家，喜欢玩原神这款二次元手游，最爱角色是胡桃", "keywords": ["原神", "游戏", "手游", "二次元", "胡桃"]}}

示例 2：
对话：用户说"我家猫又把我键盘踩坏了"，AI说"哈哈"
输出：{{"topic": "宠物", "content": "用户养了一只猫，猫很调皮，经常踩坏用户的键盘", "keywords": ["猫", "宠物", "键盘", "橘猫", "调皮"]}}

示例 3：
对话：用户说"我最近在深圳加班到吐"，AI说"辛苦了"
输出：{{"topic": "工作", "content": "用户在深圳工作，是程序员或互联网从业者，近期加班严重，工作压力大", "keywords": ["深圳", "加班", "工作", "程序员", "压力"]}}

示例 4：
对话：用户说"嗯"，AI说"嗯嗯"
输出：{{"topic": "", "content": "", "keywords": []}}

对话：
用户：{user_input}
AI：{ai_reply}
"""


class MemoryExtractor:
    def __init__(self, model: str = None):
        self.model = model or AI_CONFIG["model_name"]

    def _empty(self):
        """统一的空返回"""
        return {"topic": "", "content": "", "keywords": []}

    def extract(self, user_input: str, ai_reply: str) -> dict:
        if len(user_input.strip()) < 3 or user_input in ["嗯", "哦", "哈哈", "?", "？"]:
            return self._empty()
        try:
            prompt = EXTRACT_PROMPT.format(user_input=user_input, ai_reply=ai_reply[:100])
            resp = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.1, "num_predict": 200}
            )
            text = resp["message"]["content"].strip()
            
            # 剥 markdown
            text = re.sub(r'```(?:json)?\s*', '', text).replace('```', '').strip()
            # 抓 JSON（贪婪）
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                raw = match.group()
                raw = raw.replace("'", '"')
                raw = re.sub(r',\s*}', '}', raw)
                try:
                    data = json.loads(raw)
                    # 逐字段容错，永不 KeyError
                    topic = str(data.get("topic", "") or "").strip()
                    content = str(data.get("content", "") or "").strip()
                    keywords = data.get("keywords", [])
                    if not isinstance(keywords, list):
                        keywords = []
                    keywords = [str(k).strip() for k in keywords if str(k).strip()]
                    return {
                        "topic": topic,
                        "content": content,
                        "keywords": keywords
                    }
                except json.JSONDecodeError as je:
                    print(f"⚠️ JSON 解析失败: {je}, 原文: {raw[:150]}")
            
            # 正则兜底
            topic_m = re.search(r'"topic"\s*:\s*"([^"]*)"', text)
            content_m = re.search(r'"content"\s*:\s*"([^"]*)"', text)
            if topic_m or content_m:
                return {
                    "topic": topic_m.group(1) if topic_m else "",
                    "content": content_m.group(1) if content_m else "",
                    "keywords": []
                }
        except Exception as e:
            print(f"⚠️ 摘要提取失败: {e}")
        return self._empty()

    async def extract_async(self, user_input: str, ai_reply: str) -> dict:
        return await asyncio.to_thread(self.extract, user_input, ai_reply)