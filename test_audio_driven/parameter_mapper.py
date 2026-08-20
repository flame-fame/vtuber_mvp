import json
import os
from typing import Dict, List, Any

class ParameterMapper:
    """加载并管理 Live2D 参数到 VTS 面捕参数的映射，以及表情/动作定义"""
    
    def __init__(self, live2d_path: str, face_path: str):
        with open(live2d_path, 'r', encoding='utf-8') as f:
            self.live2d_data = json.load(f)
        with open(face_path, 'r', encoding='utf-8') as f:
            self.face_data = json.load(f)
        
        # 构建 Live2D 参数名 → VTS 参数名映射
        self.l2d_to_vts = {}
        for l2d_param, vts_param in self.face_data.items():
            self.l2d_to_vts[l2d_param] = vts_param
        
        # 解析表情定义 (expressions)
        self.expressions: Dict[str, Dict[str, float]] = self.live2d_data.get("expressions", {})
        # 解析动作定义 (actions)
        self.actions: Dict[str, Any] = self.live2d_data.get("actions", {})
    
    def to_vts_params(self, live2d_params: Dict[str, float]) -> Dict[str, float]:
        """将 Live2D 参数字典转换为 VTS 参数字典（键名映射）"""
        vts_dict = {}
        for l2d_name, value in live2d_params.items():
            if l2d_name in self.l2d_to_vts:
                vts_dict[self.l2d_to_vts[l2d_name]] = value
            else:
                # 如果未映射，直接使用原名称（可能 VTS 也支持）
                vts_dict[l2d_name] = value
        return vts_dict
    
    def get_expression_params(self, expression_name: str) -> Dict[str, float]:
        """获取表情的 Live2D 参数值"""
        return self.expressions.get(expression_name, {}).copy()
    
    def get_action_definition(self, action_name: str) -> Dict[str, Any]:
        """获取动作定义（包含 duration 和 sequence）"""
        return self.actions.get(action_name, None)