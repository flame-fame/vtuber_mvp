# debug_extractor.py
"""诊断摘要提取：看模型原始输出"""
import ollama
import re
from config import AI_CONFIG


PROMPT = """请从对话中提取用户核心兴趣点。

严格按以下 JSON 格式输出，不要任何其他文字：
{{"topic": "话题标签(4字以内)", "content": "用户兴趣摘要(20字以内)"}}

如果没有值得记忆的信息，返回 {{"topic": "", "content": ""}}
对话：
用户：{user_input}
AI：{ai_reply}
"""


def main():
    model = AI_CONFIG["model_name"]
    print(f"🔍 提取模型: {model}\n")

    cases = [
        ("我今天在原神里抽到胡桃了！", "哇，恭喜！胡桃可是很强的角色呢"),
        ("我家猫又把我键盘踩坏了", "哈哈，猫咪就是喜欢刷存在感"),
    ]

    for user_input, ai_reply in cases:
        print("=" * 60)
        print(f"输入: {user_input}")
        prompt = PROMPT.format(user_input=user_input, ai_reply=ai_reply[:100])

        # 方案 A：不用 format=json，看模型自然输出
        print("\n--- 方案 A：自然输出 ---")
        try:
            resp = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": 100}
            )
            raw_a = resp["message"]["content"]
            print(f"原始输出（repr）: {repr(raw_a)}")
            print(f"原始输出（显示）:\n{raw_a}")
        except Exception as e:
            print(f"❌ 失败: {e}")

        # 方案 B：用 format=json 强制 JSON
        print("\n--- 方案 B：format='json' ---")
        try:
            resp = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format="json",  # ← 关键
                options={"temperature": 0.1, "num_predict": 100}
            )
            raw_b = resp["message"]["content"]
            print(f"原始输出（repr）: {repr(raw_b)}")
            print(f"原始输出（显示）:\n{raw_b}")
        except Exception as e:
            print(f"❌ 失败: {e}")
        print()


if __name__ == "__main__":
    main()