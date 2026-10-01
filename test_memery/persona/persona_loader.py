# persona/persona_loader.py
"""
人格加载器：从 YAML 读取人格配置，生成 system_prompt 和运行时参数
"""
import yaml
from pathlib import Path
from typing import Dict, List


class PersonaLoader:
    def __init__(self, path: str):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"人格配置文件不存在: {path}")
        self.data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self._validate()

    def _validate(self):
        """基本字段校验"""
        required = ["meta", "identity", "core_traits", "beliefs"]
        for key in required:
            if key not in self.data:
                raise ValueError(f"人格配置缺少必需字段: {key}")

    # ---------- 核心：拼 system_prompt ----------
    def build_system_prompt(self) -> str:
        d = self.data
        lines = []

        # 1. 身份
        lines.append(f"你是{d['identity']['role']}「{d['meta']['name']}」。")
        lines.append(f"自称：{d['identity'].get('self_reference', '我')}，"
                     f"口癖：{d['identity'].get('catchphrase', '')}")

        # 2. 核心特质
        lines.append("\n【你的核心性格】")
        for t in d.get("core_traits", []):
            lines.append(f"- {t}")

        # 3. 三观/信念
        lines.append("\n【你的信念，必须始终一致】")
        for b in d.get("beliefs", []):
            lines.append(f"- [{b['category']}] {b['statement']}")

        # 4. 知识范围
        domains = d.get("knowledge_domains", [])
        if domains:
            lines.append("\n【你擅长的领域】")
            for k in domains:
                lines.append(f"- {k}")

        gaps = d.get("knowledge_gaps", [])
        if gaps:
            lines.append("\n【你不擅长的领域（可以自嘲）】")
            for k in gaps:
                lines.append(f"- {k}")

        # 5. 禁忌
        taboos = d.get("taboos", [])
        if taboos:
            lines.append("\n【绝对不能做的事】")
            for t in taboos:
                lines.append(f"- {t}")

        # 6. Few-shot 示例
        examples = d.get("few_shot_examples", [])
        if examples:
            lines.append("\n【你的说话范例，必须模仿这种语气】")
            for ex in examples:
                lines.append(f"用户：{ex['user']}")
                lines.append(f"你：{ex['assistant']}")

        # 7. 格式要求
        fmt = d.get("format_rules", "")
        if fmt:
            lines.append("\n【输出格式要求】")
            lines.append(fmt)

        return "\n".join(lines)

    # ---------- 运行时参数 ----------
    def get_beliefs(self) -> List[Dict]:
        """返回信念列表，用于预注入记忆库"""
        return self.data.get("beliefs", [])

    def get_strategy_weights(self) -> Dict[str, float]:
        """返回策略权重"""
        return self.data.get("strategy_weights", {
            "memory": 0.2, "praise": 0.2, "self_mock": 0.2,
            "extend": 0.2, "probe": 0.2
        })

    def get_emotion_rules(self) -> List[Dict]:
        """返回情绪映射规则"""
        return self.data.get("emotion_rules", [])

    def get_meta(self) -> Dict:
        return self.data.get("meta", {})

    def get_identity(self) -> Dict:
        return self.data.get("identity", {})