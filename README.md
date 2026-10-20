# Agent V0：LLM Chat Agent

这个版本不使用 Agent 框架，也没有工具调用。

它已经具备：

- 从 `.env` 加载模型配置。
- 在终端连续接收用户输入。
- 使用 `messages` 保存本次程序运行期间的对话历史。
- 调用 OpenAI-compatible 模型并显示回答。
- 输入 `exit` 结束对话。
- 捕获并显示模型调用错误。

在项目根目录运行：

```powershell
pip install -r .\versions\v0\requirements.txt
python .\versions\v0\main.py
```

简单测试：连续询问两条有关联的问题，观察模型能否根据 `messages` 理解上下文。
