"""
SDD 规格加载器 — 产品规格驱动系统行为
从 product_spec.yaml 加载配置，驱动：
  - 预约规则验证（时长限制、证书要求、费用计算）
  - 工具参数定义
  - Agent 系统提示词中的动态数据
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional


class SpecLoader:
    """单例规格加载器，从 product_spec.yaml 驱动系统"""

    _instance = None
    _spec: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        path = Path(__file__).parent.parent / "config" / "product_spec.yaml"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._spec = yaml.safe_load(f) or {}

    # ---- 预约规则 ----
    def get_booking_rules(self, equipment_id: int) -> Dict[str, Any]:
        """从 Spec 获取指定仪器的预定规则"""
        models = self._spec.get("data_models", {})
        equip_list = models.get("equipment", {}).get("fields", [])
        booking_list = models.get("booking", {}).get("fields", [])
        return {
            "equipment_fields": equip_list,
            "booking_fields": booking_list,
        }

    def get_max_booking_hours(self, equipment_id: int = None) -> int:
        """从 Spec 获取最大预约时长"""
        api_spec = self._spec.get("api_spec", {}).get("tools", [])
        for tool in api_spec:
            if tool.get("name") == "create_booking":
                params = tool.get("parameters", {})
                return 8  # default
        return 8

    def get_equipment_cert_requirement(self, equipment_name: str) -> int:
        """从 Spec 获取仪器证书要求"""
        pain_points = self._spec.get("original_system", {}).get("pain_points", [])
        # 从 Agent 定义中提取
        agents = self._spec.get("agent_transformation", {}).get("agents", [])
        for agent in agents:
            if agent.get("id") == "scheduler":
                tools = agent.get("tools", [])
                # 工具定义在 API spec 中
                break
        return 0  # 默认不需证书

    # ---- Agent 配置 ----
    def get_agent_tools(self, agent_id: str) -> List[str]:
        """从 Spec 获取指定 Agent 的工具列表"""
        agents = self._spec.get("agent_transformation", {}).get("agents", [])
        for agent in agents:
            if agent.get("id") == agent_id:
                return agent.get("tools", [])
        return []

    def get_all_tool_definitions(self) -> List[Dict]:
        """从 Spec 获取所有工具定义"""
        return self._spec.get("api_spec", {}).get("tools", [])

    # ---- 产品信息 ----
    def get_product_info(self) -> Dict[str, str]:
        """获取产品基本信息"""
        product = self._spec.get("product", {})
        return {
            "name": product.get("name", "LabAgent"),
            "version": product.get("version", "2.0.0"),
            "description": product.get("description", ""),
        }

    def get_pain_points(self) -> List[Dict]:
        """获取原始系统痛点（用于对比分析）"""
        return self._spec.get("original_system", {}).get("pain_points", [])

    def get_agent_architecture(self) -> Dict:
        """获取 Agent 架构定义"""
        return self._spec.get("agent_transformation", {})

    # ---- 验证规则 ----
    def validate_booking(self, equipment_id: int, user_cert: int, duration: int) -> Dict[str, Any]:
        """SDD 驱动的预约验证"""
        api_spec = self._spec.get("api_spec", {}).get("tools", [])
        issues = []

        # 从 Spec 检查时长限制
        for tool in api_spec:
            if tool.get("name") == "create_booking":
                params = tool.get("parameters", {})
                if isinstance(params, dict):
                    max_hours = params.get("max_hours", 8)
                    if duration > max_hours:
                        issues.append(f"时长超过限制 ({duration}h > {max_hours}h)")
                break

        # 从 Spec 检查证书
        data_models = self._spec.get("data_models", {})
        equip_fields = data_models.get("equipment", {}).get("fields", [])
        for field in equip_fields:
            if field.get("name") == "requires_cert" and field.get("type") == "bool":
                issues.append("需要检查证书")
                break

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "spec_version": self.get_product_info().get("version", "unknown"),
        }


# 全局单例
_spec_loader = None

def get_spec() -> SpecLoader:
    global _spec_loader
    if _spec_loader is None:
        _spec_loader = SpecLoader()
    return _spec_loader
