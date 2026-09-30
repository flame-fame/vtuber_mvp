# memory_manager.py
"""
向量记忆管理器：基于 ChromaDB + Ollama Embedding
功能：
1. 存储对话摘要（不存原始对话）
2. 语义检索相关记忆
3. 冷场时随机抽取旧话题
4. 时间衰减 + 话题去重
"""
import time
import asyncio
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import chromadb
from chromadb.config import Settings
import ollama

from config import MEMORY_CONFIG


class MemoryManager:
    def __init__(self):
        # 1. 初始化 ChromaDB（持久化到本地）
        self.client = chromadb.PersistentClient(
            path=MEMORY_CONFIG["db_path"],
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="ai_vtuber_memory",
            metadata={"hnsw:space": "cosine"}  # 余弦距离
        )
        self.embed_model = MEMORY_CONFIG["embed_model"]
        self.top_k = MEMORY_CONFIG["top_k"]
        self.similarity_threshold = MEMORY_CONFIG["similarity_threshold"]
        self.recent_topics = []  # 最近抛过的话题，避免重复
        print(f"🧠 记忆库已加载，当前记忆数: {self.collection.count()}")

    # ---------- 嵌入 ----------
    def _embed(self, text: str) -> List[float]:
        """调用 Ollama 生成向量"""
        try:
            resp = ollama.embeddings(model=self.embed_model, prompt=text)
            return resp["embedding"]
        except Exception as e:
            print(f"⚠️ 嵌入失败: {e}")
            return [0.0] * 768  # 兜底

    # ---------- 写入 ----------
    def add_memory(self, content: str, topic: str, speaker: str = "user", keywords: list = None):
        if not content or len(content) < 2:
            return

        # 不保存相似记忆
        try:
            existing = self.collection.query(
                query_embeddings=[self._embed(content)],
                n_results=1,
                include=["distances"]
            )
            if existing["distances"] and existing["distances"][0]:
                similarity = 1 - existing["distances"][0][0]
                if similarity > 0.95:  # 高度相似，视为重复
                    print(f"⏭️ 跳过重复记忆 (相似度 {similarity:.3f})")
                    return
        except Exception:
            pass

        # 把 keywords 拼进 content，强化检索
        keywords = keywords or []
        if keywords:
            kw_str = "/".join(keywords[:5])
            content = f"{content}（{kw_str}）"
        
        # 去重检查用原始 content 前缀
        existing = self.collection.get(where={"content": content})
        if existing and existing["ids"]:
            return
        
        mem_id = f"mem_{int(time.time() * 1000)}_{random.randint(0, 999)}"
        try:
            self.collection.add(
                ids=[mem_id],
                embeddings=[self._embed(content)],
                documents=[content],
                metadatas=[{
                    "topic": topic,
                    "speaker": speaker,
                    "timestamp": time.time(),
                    "date_str": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "keywords": ",".join(keywords or [])  # 单独存一份便于过滤
                }]
            )
            print(f"💾 记忆已写入: [{topic}] {content}")
        except Exception as e:
            print(f"⚠️ 写入记忆失败: {e}")

    async def add_memory_async(self, content: str, topic: str, speaker: str = "user", keywords: list = None):
        await asyncio.to_thread(self.add_memory, content, topic, speaker, keywords)

    # ---------- 检索 ----------
    def search(self, query: str, top_k: int = None) -> List[Dict]:
        """
        检索相关记忆，返回格式化列表
        """
        # 空 query 直接返回
        if not query or not query.strip():
            return []
        
        top_k = top_k or self.top_k
        if self.collection.count() == 0:
            return []
        
        try:
            results = self.collection.query(
                query_embeddings=[self._embed(query)],
                n_results=min(top_k, self.collection.count()),
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            print(f"⚠️ 检索失败: {e}")
            return []

        memories = []
        if not results["documents"] or not results["documents"][0]:
            return memories

        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            similarity = 1 - dist  # cosine 距离转相似度
            if similarity < self.similarity_threshold:
                continue
            # 时间衰减：超过 7 天的记忆降权
            age_days = (time.time() - meta.get("timestamp", 0)) / 86400
            if age_days > 30:
                continue
            memories.append({
                "content": doc,
                "topic": meta.get("topic", ""),
                "speaker": meta.get("speaker", ""),
                "date_str": meta.get("date_str", ""),
                "similarity": round(similarity, 3),
                "age_days": round(age_days, 1)
            })
        return memories

    def format_for_prompt(self, memories: List[Dict]) -> str:
        """把检索结果格式化成可以塞进 prompt 的文本"""
        if not memories:
            return ""
        lines = ["【相关记忆】"]
        for m in memories:
            lines.append(f"- {m['speaker']}曾提到：{m['content']}（{m['date_str']}）")
        return "\n".join(lines)

    # ---------- 冷场抛话题 ----------
    def get_random_old_topic(self, exclude_recent: bool = True) -> Optional[Dict]:
        """
        随机抽取一条 1~30 天前的记忆作为主动话题
        """
        if self.collection.count() == 0:
            return None
        try:
            all_data = self.collection.get(include=["documents", "metadatas"])
        except Exception as e:
            print(f"⚠️ 获取记忆失败: {e}")
            return None

        now = time.time()
        candidates = []
        for doc, meta in zip(all_data["documents"], all_data["metadatas"]):
            age_days = (now - meta.get("timestamp", 0)) / 86400
            # 只取 0.5 ~ 30 天前的
            if age_days < 0.5 or age_days > 30:
                continue
            topic = meta.get("topic", "")
            if exclude_recent and topic in self.recent_topics:
                continue
            candidates.append({
                "content": doc,
                "topic": topic,
                "age_days": round(age_days, 1)
            })

        if not candidates:
            return None
        chosen = random.choice(candidates)
        # 记录最近抛过的话题
        self.recent_topics.append(chosen["topic"])
        if len(self.recent_topics) > 5:
            self.recent_topics.pop(0)
        return chosen

    # ---------- 维护 ----------
    def prune(self, max_count: int = 5000):
        """超过上限时，按时间淘汰最旧的记忆"""
        if self.collection.count() <= max_count:
            return
        all_data = self.collection.get(include=["metadatas"])
        items = list(zip(all_data["ids"], all_data["metadatas"]))
        items.sort(key=lambda x: x[1].get("timestamp", 0))
        to_delete = [i[0] for i in items[: len(items) - max_count]]
        if to_delete:
            self.collection.delete(ids=to_delete)
            print(f"🗑️ 已淘汰 {len(to_delete)} 条旧记忆")

    def clear(self):
        """清空记忆库（调试用）"""
        self.client.delete_collection("ai_vtuber_memory")
        self.collection = self.client.get_or_create_collection(
            name="ai_vtuber_memory",
            metadata={"hnsw:space": "cosine"}
        )
        print("🧹 记忆库已清空")