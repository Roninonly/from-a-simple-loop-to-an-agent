# Agent V2：LangGraph Agent

这个版本在 V1 的功能基础上，用 LangGraph 状态图替代手写的内部 Agent Loop。

它已经具备：

- 使用 `AgentState` 保存和合并对话消息。
- 使用模型节点调用绑定工具后的聊天模型。
- 使用 `ToolNode` 执行计算器和时间工具。
- 根据模型是否产生 `tool_calls` 选择工具路线或结束路线。
- 工具执行后自动回到模型节点生成最终回答。
- 使用 `recursion_limit` 防止单轮图循环无限进行。
- 在终端连续对话，并在本次程序运行期间保留上下文。

在项目根目录运行：

```powershell
pip install -r .\versions\v2\requirements.txt
python .\versions\v2\main.py
```

简单测试：

```text
请计算 123×123，并告诉我现在几点。
```
