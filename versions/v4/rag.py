"""Agent V4 的知识库模块：读取、切分、向量化和内存知识库检索。"""

from pathlib import Path
from typing import Callable

import numpy as np
from fastembed import TextEmbedding


def load_knowledge_text() -> str:
    """读取项目内的知识文档，并返回完整文本。"""
    document_path = Path(__file__).resolve().parent / "data" / "agent_notes.md"
    return document_path.read_text(encoding="utf-8")


def split_knowledge_text(text: str) -> list[str]:
    """按 Markdown 二级标题切分，返回保留章节标题文字的文本片段。"""
    chunks = []

    # 分隔符是换行加二级标题标记；标题文字和该章节正文仍在一起。
    for section in text.split("\n## "):
        chunk = section.strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def create_embedding_model() -> TextEmbedding:
    """创建中文向量模型，首次使用时下载并缓存到项目目录。"""
    cache_dir = Path(__file__).resolve().parent / "data" / "embedding_models"
    cache_dir.mkdir(parents=True, exist_ok=True)

    return TextEmbedding(
        model_name="BAAI/bge-small-zh-v1.5",
        cache_dir=str(cache_dir),
        providers=["CPUExecutionProvider"],
    )


def embed_knowledge_chunks(
    model: TextEmbedding, chunks: list[str]
) -> list[list[float]]:
    """将文本片段转换成向量，返回顺序与输入片段一致。"""
    vectors = []

    for vector in model.embed(chunks):
        # 库返回数值数组，这里转换为普通 Python 列表，便于后续使用。
        vectors.append(vector.tolist())

    return vectors


def create_knowledge_store(
    chunks: list[str], vectors: list[list[float]]
) -> list[dict]:
    """把原文、向量和来源放在同一条记录中，暂时只保存在内存。"""
    if len(chunks) != len(vectors):
        raise ValueError("文本片段和向量的数量必须一致。")

    knowledge_store = []

    # zip 按位置配对：第一个片段配第一个向量，依此类推。
    for chunk, vector in zip(chunks, vectors):
        knowledge_store.append(
            {
                "text": chunk,
                "vector": vector,
                "source": "data/agent_notes.md",
            }
        )

    return knowledge_store


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个向量的余弦相似度，分数越高表示向量方向越接近。"""
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    if denominator == 0:
        return 0.0

    return float(np.dot(left, right) / denominator)


def retrieve_knowledge(
    query: str,
    model: TextEmbedding,
    knowledge_store: list[dict],
    top_k: int = 2,
) -> list[dict]:
    """将问题向量化，返回相似度最高的前 top_k 条原文及来源。"""
    if not query.strip():
        raise ValueError("检索问题不能为空。")
    if top_k < 1:
        raise ValueError("top_k 必须大于或等于 1。")
    if not knowledge_store:
        return []

    # 问题和文档必须使用同一个向量模型；query_embed 是库提供的查询方法。
    query_vectors = list(model.query_embed(query))
    query_vector = query_vectors[0].tolist()
    results = []

    for record in knowledge_store:
        score = cosine_similarity(query_vector, record["vector"])
        results.append(
            {
                "text": record["text"],
                "source": record["source"],
                "score": score,
            }
        )

    # 按 score 从高到低排序，再取前 top_k 条；不改变原知识库记录。
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def create_retriever_tool() -> Callable[[str], str]:
    """启动时建立知识库，返回只需要接收检索问题的工具函数。"""
    text = load_knowledge_text()
    chunks = split_knowledge_text(text)
    print("正在加载知识库向量模型，首次使用需要联网下载。", flush=True)
    model = create_embedding_model()
    vectors = embed_knowledge_chunks(model, chunks)
    knowledge_store = create_knowledge_store(chunks, vectors)
    print(f"知识库已准备，共 {len(knowledge_store)} 条记录。")

    def search_knowledge(query: str) -> str:
        """查询青竹 Agent 学习营的基本信息、作业、阶段验收和设备借用规则。"""
        print(f"知识库检索问题：{query}")
        results = retrieve_knowledge(query, model, knowledge_store)
        if not results:
            return "知识库中没有可用资料。"

        passages = []
        for index, result in enumerate(results, start=1):
            passage = (
                f"片段 {index}，来源：{result['source']}，"
                f"相似度：{result['score']:.4f}\n{result['text']}"
            )
            print(passage)
            passages.append(passage)

        return "\n\n".join(passages)

    return search_knowledge


if __name__ == "__main__":
    knowledge_text = load_knowledge_text()
    chunks = split_knowledge_text(knowledge_text)
    print(f"知识文档已读取，共 {len(knowledge_text)} 个字符。")
    print(f"知识文档已切分，共 {len(chunks)} 个片段。")

    print("正在加载中文向量模型，首次运行需要联网下载。", flush=True)
    embedding_model = create_embedding_model()
    vectors = embed_knowledge_chunks(embedding_model, chunks)
    print(f"向量化完成，共 {len(vectors)} 个向量。")

    knowledge_store = create_knowledge_store(chunks, vectors)
    print(f"内存知识库已建立，共 {len(knowledge_store)} 条记录。")

    query = input("请输入知识库问题：")
    results = retrieve_knowledge(query, embedding_model, knowledge_store)
    print(f"检索完成，返回 {len(results)} 条结果。")

    for index, result in enumerate(results, start=1):
        print(f"\n结果 {index}：来源 {result['source']}")
        print(f"相似度：{result['score']:.4f}")
        print(result["text"])
