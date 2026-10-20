"""Agent V7 的评估入口：默认预览题库，显式 --run 才调用真实智能体。"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage


PROJECT_DIR = Path(__file__).resolve().parent.parent


def load_dataset() -> list[dict]:
    """读取同目录的 JSON 题库，返回 cases 对应的题目列表。"""
    dataset_path = Path(__file__).resolve().parent / "dataset.json"
    text = dataset_path.read_text(encoding="utf-8")
    dataset = json.loads(text)
    cases = dataset["cases"]

    if not isinstance(cases, list) or not cases:
        raise ValueError("题库中的 cases 必须是非空列表。")

    return cases


def check_answer(answer: str, expected: dict) -> list[str]:
    """按答案文字条件收集失败原因；空列表仅表示这些文字条件通过。"""
    failures = []

    # 完全一致检查忽略实际答案的首尾空白，不忽略标点或额外文字。
    if "answer_equals" in expected:
        if answer.strip() != expected["answer_equals"]:
            failures.append(f"答案应为：{expected['answer_equals']}")

    # 列表中的每个关键词都必须出现；这里只做文字匹配，不判断语义。
    for keyword in expected.get("answer_contains", []):
        if keyword not in answer:
            failures.append(f"答案缺少：{keyword}")

    return failures


def check_tools(executed_tools: list[str], expected: dict) -> list[str]:
    """检查必需工具是否在成功执行名单中；这里只比较，不执行或采集工具。"""
    failures = []

    for tool_name in expected.get("required_tools", []):
        if tool_name not in executed_tools:
            failures.append(f"缺少成功执行的工具：{tool_name}")

    return failures


def check_retrieval(retrieved_text: str, expected: dict) -> list[str]:
    """检查检索返回的文字是否命中目标内容，不检查模型最终答案。"""
    failures = []

    for keyword in expected.get("retrieved_contains", []):
        if keyword not in retrieved_text:
            failures.append(f"检索片段缺少：{keyword}")

    return failures


def collect_execution_records(messages: list) -> dict:
    """从本题消息中配对工具请求和成功结果，提取工具名单与检索文字。"""
    tool_call_names = {}
    executed_tools = []
    retrieved_texts = []

    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                tool_call_names[tool_call["id"]] = tool_call["name"]
        elif isinstance(message, ToolMessage):
            tool_name = tool_call_names.get(message.tool_call_id)
            # 只提出请求不算执行成功；失败或无法配对的结果不计入。
            if tool_name is None or message.status != "success":
                continue

            if tool_name not in executed_tools:
                executed_tools.append(tool_name)

            # 只从知识库工具结果取资料，不把模型回答当成检索证据。
            if tool_name == "search_knowledge" and isinstance(message.content, str):
                retrieved_texts.append(message.content)

    return {
        "executed_tools": executed_tools,
        "retrieved_text": "\n\n".join(retrieved_texts),
    }


def evaluate_case(service, case: dict) -> dict:
    """在独立新会话中完成一道题，用真实回答和消息记录执行检查。"""
    session_id = f"eval-{uuid4().hex}"
    answer = ""
    records = {"executed_tools": [], "retrieved_text": ""}
    failures = []
    expected = case["expected"]
    # None 表示本题不要求这一项；要求的项目先记为失败，检查完成后再更新。
    checks = {
        "answer": False if "answer_equals" in expected or expected.get("answer_contains") else None,
        "tools": False if expected.get("required_tools") else None,
        "retrieval": False if expected.get("retrieved_contains") else None,
    }
    started = perf_counter()

    try:
        # 题内的多次提问共用同一个会话，例如先告知名字、再追问。
        for question in case["questions"]:
            answer = service.ask(question, session_id)

        graph_config = {"configurable": {"thread_id": session_id}}
        saved_state = service.agent_graph.get_state(graph_config)
        records = collect_execution_records(saved_state.values.get("messages", []))
        answer_failures = check_answer(answer, expected)
        tool_failures = check_tools(records["executed_tools"], expected)
        retrieval_failures = check_retrieval(records["retrieved_text"], expected)
        failures.extend(answer_failures)
        failures.extend(tool_failures)
        failures.extend(retrieval_failures)
        if checks["answer"] is not None:
            checks["answer"] = not answer_failures
        if checks["tools"] is not None:
            checks["tools"] = not tool_failures
        if checks["retrieval"] is not None:
            checks["retrieval"] = not retrieval_failures
    except Exception as error:
        # 执行异常不能被当成通过；也不直接输出可能包含配置的底层异常文本。
        answer = ""
        failures.append(f"本题执行异常：{type(error).__name__}")
        for key in checks:
            if checks[key] is not None:
                checks[key] = False

    return {
        "id": case["id"],
        "category": case["category"],
        "session_id": session_id,
        "questions": case["questions"],
        "expected": expected,
        "answer": answer,
        "executed_tools": records["executed_tools"],
        "retrieved_text": records["retrieved_text"],
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "elapsed_seconds": perf_counter() - started,
    }


def summarize_results(results: list[dict]) -> dict:
    """汇总本次题库的条件通过情况；没有适用题目时比例为 None。"""
    total = len(results)
    passed = sum(result["passed"] for result in results)
    summary = {
        "task": {"passed": passed, "total": total, "rate": passed / total if total else None},
        "average_case_seconds": (
            sum(result["elapsed_seconds"] for result in results) / total if total else None
        ),
    }
    for key in ["answer", "tools", "retrieval"]:
        applicable = [
            result["checks"][key]
            for result in results
            if result["checks"][key] is not None
        ]
        count = len(applicable)
        passed_count = sum(applicable)
        summary[key] = {
            "passed": passed_count,
            "total": count,
            "rate": passed_count / count if count else None,
        }
    return summary


def print_summary(summary: dict) -> None:
    """显示带分母的汇总指标，避免把单次小题库结果误认为通用准确率。"""
    print("本次题库评估汇总：")
    for key, label in [
        ("task", "任务成功率"),
        ("answer", "答案文字条件通过率"),
        ("tools", "必需工具检查通过率"),
        ("retrieval", "目标资料命中率"),
    ]:
        metric = summary[key]
        if metric["rate"] is None:
            print(f"{label}：不适用（没有对应题目）。")
        else:
            print(f"{label}：{metric['rate']:.1%}（{metric['passed']}/{metric['total']}）。")
    average = summary["average_case_seconds"]
    if average is None:
        print("平均每题耗时：不适用。")
    else:
        print(f"平均每题耗时：{average:.2f} 秒（含题内全部轮次及检查，不含初始化）。")


def save_results(results: list[dict], summary: dict, output_dir: Path | None = None) -> Path:
    """保存独立的 UTF-8 JSON 报告；只保存评估数据，不读取配置或数据库。"""
    created_at = datetime.now(timezone(timedelta(hours=8)))
    output_dir = output_dir or Path(__file__).resolve().parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"run-{created_at.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}.json"
    output_path = output_dir / filename
    report = {
        "report_version": 1,
        "created_at": created_at.isoformat(),
        "scope": {
            "answer": "答案字面规则检查，不是完整语义判断。",
            "tools": "必需工具成功记录检查，不验证参数，也不禁止额外工具。",
            "retrieval": "目标文字命中检查，不衡量片段排名或所有结果的相关性。",
            "latency": "平均每题耗时包含题内全部问答及检查，不含初始化；失败题也计入。",
        },
        "summary": summary,
        "results": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    # 使用 x 模式，只创建新文件，不覆盖已经存在的报告。
    with output_path.open("x", encoding="utf-8") as report_file:
        report_file.write(text + "\n")
    return output_path


def main() -> None:
    """预览题库，或执行评估、显示指标并保存本次报告。"""
    parser = argparse.ArgumentParser(description="Agent V7 最小评估入口")
    parser.add_argument(
        "--run", action="store_true", help="执行真实评估，会调用模型并可能产生费用。"
    )
    args = parser.parse_args()
    cases = load_dataset()
    print(f"评估题库已读取，共 {len(cases)} 道题。")
    for case in cases:
        print(f"- {case['id']}：类别 {case['category']}，共 {len(case['questions'])} 个问题。")

    if not args.run:
        print("当前仅预览题库，未调用模型。添加 --run 才执行真实评估。")
        return

    question_count = sum(len(case["questions"]) for case in cases)
    print(f"即将提交 {question_count} 次用户消息；工具循环可能增加模型调用并产生费用。")
    # 直接执行本文件时，将项目根目录加入导入路径，随后才加载智能体模块。
    sys.path.insert(0, str(PROJECT_DIR))
    from app.agent_service import create_agent_service

    results = []
    # 本次评估使用临时数据库，退出上下文后清理，不写入真实 memory.db。
    with TemporaryDirectory(prefix="agent-eval-") as temp_dir:
        database_path = Path(temp_dir) / "memory.db"
        with create_agent_service(database_path=database_path) as service:
            for case in cases:
                print(f"正在评估：{case['id']}", flush=True)
                result = evaluate_case(service, case)
                results.append(result)
                status = "通过" if result["passed"] else "失败"
                print(f"{result['id']}：{status}，耗时 {result['elapsed_seconds']:.2f} 秒。")
                print(f"最终回答：{result['answer']}")
                print(f"成功工具：{result['executed_tools']}")
                if result["retrieved_text"]:
                    print(f"检索文字：{result['retrieved_text']}")
                for failure in result["failures"]:
                    print(f"失败原因：{failure}")
    print("评估结束，临时会话数据库已清理。")
    summary = summarize_results(results)
    print_summary(summary)
    output_path = save_results(results, summary)
    print(f"本次评估结果已保存：{output_path}")


if __name__ == "__main__":
    main()
