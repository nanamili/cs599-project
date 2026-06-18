"""
RAG检索工具 — QA Agent 的知识检索工具箱
提供SOP文档语义检索、设备信息查询等功能
"""

from typing import List, Dict, Any, Optional
from ..rag.retriever import search_sop, init_knowledge_base


def search_equipment_sop(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    在SOP知识库中检索与查询相关的仪器操作规范

    适用场景:
    - "电镜样品怎么制备？"
    - "ICP-MS开机步骤是什么？"
    - "HPC集群如何提交GPU作业？"
    - "核磁共振有什么安全注意事项？"

    Args:
        query: 自然语言查询
        top_k: 返回的相关文档块数量
    """
    # 确保知识库已初始化
    store = init_knowledge_base()

    results = search_sop(query, top_k=top_k)

    formatted = []
    for r in results:
        # 截断过长的内容
        content = r["content"]
        if len(content) > 600:
            content = content[:600] + "\n\n... (内容较长，完整文档请查阅原始SOP)"

        formatted.append({
            "content": content,
            "source_file": r["source_file"],
            "section_title": r["section_title"],
            "relevance_score": round(1.0 - r.get("distance", 0), 4),
        })

    return formatted


def get_sop_summary(equipment_name: str) -> Dict[str, Any]:
    """
    获取某台仪器的SOP摘要（安全须知 + 预约规则）

    Args:
        equipment_name: 仪器名称关键词，如 "透射电镜"、"ICP-MS"、"HPC"
    """
    results = search_sop(equipment_name, top_k=5)

    safety_items = []
    booking_rules = []

    for r in results:
        content = r["content"]
        # 提取安全相关内容
        if "安全" in content.lower() or "⚠" in content or "禁止" in content:
            for line in content.split("\n"):
                line = line.strip()
                if any(kw in line for kw in ["安全", "⚠", "禁止", "必须", "注意", "风险"]):
                    safety_items.append(line.lstrip("- *").strip())

        # 提取预约规则
        if "预约规则" in content or "预约" in content.lower():
            for line in content.split("\n"):
                line = line.strip()
                if any(kw in line for kw in ["预约", "时长", "小时", "维护", "取消"]):
                    booking_rules.append(line.lstrip("- *").strip())

    return {
        "equipment_name": equipment_name,
        "safety_notices": safety_items[:8],
        "booking_rules": booking_rules[:5],
        "has_full_sop": len(results) > 0,
    }
