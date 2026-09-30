# debug_embedding.py
"""诊断嵌入模型：向量维度、相似度分布"""
import ollama
import numpy as np
from config import MEMORY_CONFIG


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def main():
    model = MEMORY_CONFIG["embed_model"]
    print(f"🔍 当前嵌入模型: {model}")
    print(f"📁 记忆库路径: {MEMORY_CONFIG['db_path']}")
    print(f"🎚️ 相似度阈值: {MEMORY_CONFIG['similarity_threshold']}\n")

        # 1. 检查模型是否存在
    try:
        models = ollama.list()
        print(f"  原始返回: {models}")  # ← 先打印看结构
        # 兼容两种字段名
        available = []
        for m in models.get("models", []):
            name = m.get("model") or m.get("name") or ""
            available.append(name)
        print(f"✅ Ollama 已有模型: {available}")
        if not any(model in m for m in available):
            print(f"❌ 模型 {model} 未安装！请执行: ollama pull {model}")
            return
    except Exception as e:
        print(f"❌ 无法连接 Ollama: {e}")
        import traceback; traceback.print_exc()
        return

    # 2. 测试向量维度
    texts = [
        "游戏",                          # query
        "用户喜欢玩原神，最爱角色是胡桃",   # 应该最相关
        "用户养了一只橘猫叫豆豆",          # 不相关
        "用户是深圳的程序员，经常加班",     # 不相关
        "AI 自嘲说自己数学不好",           # 不相关
    ]
    vecs = []
    for t in texts:
        try:
            v = ollama.embeddings(model=model, prompt=t)["embedding"]
            vecs.append(v)
            print(f"  [{len(v)}维] {t}")
        except Exception as e:
            print(f"❌ 嵌入失败 {t}: {e}")
            return

    # 3. 计算 query 与每条的相似度
    print(f"\n📊 以「游戏」为 query 的相似度:")
    print("-" * 60)
    query_vec = vecs[0]
    for i, t in enumerate(texts[1:], 1):
        sim = cosine(query_vec, vecs[i])
        print(f"  {sim:.4f}  {t}")
    print("-" * 60)

    # 4. 计算所有两两相似度矩阵（看模型区分度）
    print(f"\n📊 两两相似度矩阵（越高越像）:")
    n = len(texts)
    print("        " + "  ".join(f"[{i}]" for i in range(n)))
    for i in range(n):
        row = [f"{cosine(vecs[i], vecs[j]):.2f}" for j in range(n)]
        print(f"  [{i}]  " + "  ".join(row))

    print("\n💡 诊断建议:")
    print("  - 若「游戏」vs「原神」相似度 < 0.4，说明模型对中文区分度差")
    print("  - 若所有相似度都 > 0.6，说明模型退化为'所有句子都差不多'")
    print("  - 推荐换 bge-m3 或 quentinz/bge-large-zh-v1.5")


if __name__ == "__main__":
    main()