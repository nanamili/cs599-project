"""
Agent 评估基准测试
10 条测试用例，覆盖三大 Agent：意图识别准确率、工具调用正确率、回复质量评分
"""

import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# ============================================
# 测试用例
# ============================================
TEST_CASES = [
    # === Scheduler 测试 ===
    {
        "id": "S01", "query": "帮我预约下周一的透射电镜，上午9点到下午1点",
        "expected_intent": "scheduler",
        "expected_tools": ["tool_check_availability", "tool_create_booking"],
        "description": "预约请求 → 应检测冲突 + 创建预约",
    },
    {
        "id": "S02", "query": "下周三ICP-MS有哪些时间段可以用？",
        "expected_intent": "scheduler",
        "expected_tools": ["tool_check_availability"],
        "description": "可用性查询 → 应调用可用性检查",
    },
    {
        "id": "S03", "query": "取消我上次的预约",
        "expected_intent": "scheduler",
        "expected_tools": ["tool_get_user_bookings", "tool_cancel_booking"],
        "description": "取消预约 → 应先查记录再取消",
    },
    {
        "id": "S04", "query": "有哪些仪器不需要证书就能用？",
        "expected_intent": "scheduler",
        "expected_tools": ["tool_get_equipment_list"],
        "description": "仪器筛选 → 应列出全部仪器",
    },

    # === QA 测试 ===
    {
        "id": "Q01", "query": "透射电镜的样品怎么制备？需要注意什么安全问题？",
        "expected_intent": "qa",
        "expected_tools": ["tool_search_sop"],
        "description": "SOP知识问答 → 应RAG检索+标注安全",
    },
    {
        "id": "Q02", "query": "ICP-MS开机步骤是什么？",
        "expected_intent": "qa",
        "expected_tools": ["tool_search_sop"],
        "description": "操作流程 → 应检索SOP",
    },
    {
        "id": "Q03", "query": "HPC集群怎么提交GPU作业？",
        "expected_intent": "qa",
        "expected_tools": ["tool_search_sop"],
        "description": "HPC操作 → 应检索SOP",
    },

    # === Monitor 测试 ===
    {
        "id": "M01", "query": "检查系统最近两周有什么异常情况",
        "expected_intent": "monitor",
        "expected_tools": ["tool_check_anomalies"],
        "description": "异常扫描 → 应检测爽约/未持证",
    },
    {
        "id": "M02", "query": "生成这个月的仪器使用统计报告",
        "expected_intent": "monitor",
        "expected_tools": ["tool_generate_usage_stats"],
        "description": "使用统计 → 应生成报告",
    },
    {
        "id": "M03", "query": "最近谁爽约了？",
        "expected_intent": "monitor",
        "expected_tools": ["tool_check_anomalies"],
        "description": "爽约查询 → 应查异常记录",
    },
]


def run_eval():
    """运行完整评估"""
    from src.agents.graph import run_with_stream

    results = []
    intent_correct = 0
    tool_hits_total = 0
    tool_total = 0

    print("=" * 60)
    print("LabAgent 评估基准测试")
    print("=" * 60)

    for i, tc in enumerate(TEST_CASES):
        print(f"\n[{tc['id']}] {tc['description']}")
        print(f"  Query: {tc['query']}")

        # 收集 trace
        traces = []
        response = ""
        start = time.time()

        try:
            for chunk in run_with_stream(tc["query"], f"eval_{tc['id']}"):
                if chunk["type"] == "token":
                    response += chunk["data"]
                elif chunk["type"] == "trace":
                    traces.extend(chunk["data"])
                elif chunk["type"] == "final":
                    if not response:
                        response = chunk.get("data", "")
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({**tc, "intent_match": False, "tool_hits": 0, "tool_total": len(tc["expected_tools"]),
                           "response_len": 0, "latency": 0, "error": str(e)})
            continue

        elapsed = round(time.time() - start, 1)

        # 意图分类检查
        supervisor_traces = [t for t in traces if "Supervisor" in t.get("agent", "") and "意图" in t.get("action", "")]
        detected_intent = "unknown"
        for t in supervisor_traces:
            detail = t.get("detail", "")
            if "scheduler" in detail.lower():
                detected_intent = "scheduler"
            elif "qa" in detail.lower():
                detected_intent = "qa"
            elif "monitor" in detail.lower():
                detected_intent = "monitor"

        intent_match = detected_intent == tc["expected_intent"]

        # 工具调用检查
        tool_calls = [t for t in traces if "调用工具" in t.get("action", "")]
        called_tool_names = []
        for t in tool_calls:
            action = t.get("action", "")
            for name in tc["expected_tools"]:
                if name in action:
                    called_tool_names.append(name)

        tool_hits = len(set(called_tool_names))
        tool_total_for_case = len(tc["expected_tools"])

        # 回复质量检查
        quality_checks = []
        if len(response) > 100:
            quality_checks.append("length_ok")
        if tc["expected_intent"] == "qa" and ("安全" in response or "注意" in response or "⚠" in response):
            quality_checks.append("safety_marked")
        if tc["expected_intent"] == "monitor" and ("异常" in response or "爽约" in response or "违规" in response):
            quality_checks.append("anomaly_detected")

        # 记录
        if intent_match:
            intent_correct += 1
        tool_hits_total += tool_hits
        tool_total += tool_total_for_case

        status = "PASS" if intent_match and tool_hits >= 1 else "PARTIAL" if tool_hits >= 1 else "FAIL"
        print(f"  Intent: {detected_intent} (expected: {tc['expected_intent']}) {'OK' if intent_match else 'FAIL'}")
        print(f"  Tools: {tool_hits}/{tool_total_for_case} matched ({called_tool_names})")
        print(f"  Response: {len(response)} chars, {elapsed}s, Quality: {quality_checks}")
        print(f"  [{status}]")

        results.append({
            "id": tc["id"],
            "description": tc["description"],
            "intent_match": intent_match,
            "detected_intent": detected_intent,
            "expected_intent": tc["expected_intent"],
            "tool_hits": tool_hits,
            "tool_total": tool_total_for_case,
            "quality_checks": quality_checks,
            "response_len": len(response),
            "latency": elapsed,
        })

    # ========================================
    # 汇总报告
    # ========================================
    print("\n" + "=" * 60)
    print("评估汇总")
    print("=" * 60)

    n = len(results)
    intent_acc = intent_correct / n * 100
    tool_acc = tool_hits_total / tool_total * 100 if tool_total > 0 else 0
    avg_latency = sum(r["latency"] for r in results) / n
    avg_length = sum(r["response_len"] for r in results) / n
    quality_pass = sum(1 for r in results if len(r.get("quality_checks", [])) > 0)

    print(f"""
┌──────────────────────────────────────────────┐
│         LabAgent 评估基准报告                 │
├──────────────────────────────────────────────┤
│  测试用例数:        {n:>3}                    │
│  意图识别准确率:    {intent_acc:>5.1f}%       │
│  工具调用命中率:    {tool_acc:>5.1f}%         │
│  平均响应时间:      {avg_latency:>5.1f}s      │
│  平均回复长度:      {avg_length:>5.0f} chars  │
│  质量检查通过:      {quality_pass:>3}/{n}     │
└──────────────────────────────────────────────┘
""")

    # 按 Agent 分类统计
    by_agent = {"scheduler": [], "qa": [], "monitor": []}
    for r in results:
        by_agent[r["expected_intent"]].append(r)

    for agent, cases in by_agent.items():
        if cases:
            acc = sum(1 for c in cases if c["intent_match"]) / len(cases) * 100
            print(f"  {agent}: {acc:.0f}% intent accuracy ({len(cases)} cases)")

    # 输出 JSON（供报告引用）
    report = {
        "summary": {
            "total_cases": n,
            "intent_accuracy": round(intent_acc, 1),
            "tool_hit_rate": round(tool_acc, 1),
            "avg_latency_s": round(avg_latency, 1),
            "avg_response_chars": round(avg_length, 0),
            "quality_pass_rate": f"{quality_pass}/{n}",
        },
        "details": results,
    }
    print(f"\nJSON Report: {json.dumps(report['summary'], ensure_ascii=False, indent=2)}")
    return report


if __name__ == "__main__":
    run_eval()
