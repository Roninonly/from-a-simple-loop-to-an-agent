# Agent V1：Tool-Using Agent

这个版本在 V0 基础上加入了结构化 Tool Calling，并继续使用手写 Agent Loop。

它已经具备：

- `calculator` 计算工具。
- `get_current_time` 本机时间工具。
- 模型自主选择工具。
- 同一回复中的多个工具调用。
- 工具结果与 `tool_call_id` 对应。
- 根据工具结果继续请求模型。
- 每个用户问题最多请求模型 5 次。
- 工具错误回传和最终自然语言回答。

在项目根目录运行：

```powershell
pip install -r .\versions\v1\requirements.txt
python .\versions\v1\main.py
```

简单测试：

```text
请计算 123×123，并告诉我现在几点。
```
