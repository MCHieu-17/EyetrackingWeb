#!/usr/bin/env python3
"""Vẽ sơ đồ pipeline chatbot hiện tại.

Lưu ý: pipeline trong `app/workflow/pipeline.py` là async generator tự viết,
KHÔNG phải LangGraph — nên không có `graph.get_graph()` để gọi. Script này vẽ
đúng luồng thật của `run_chat()` bằng Graphviz.

Chạy:
    python scripts/graph.py
    python scripts/graph.py /tmp/chatbot-pipeline.png

Yêu cầu: lệnh `dot` của Graphviz có trong PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

DOT_SOURCE = r"""
digraph chatbot {
  rankdir=TB;
  graph [
    fontname="Helvetica",
    bgcolor="white",
    pad="0.5",
    nodesep="0.45",
    ranksep="0.55",
    label="Chatbot RAG — luồng run_chat() (async generator, không phải LangGraph)",
    labelloc="t",
    fontsize=14
  ];
  node [
    fontname="Helvetica",
    fontsize=11,
    shape=box,
    style="rounded,filled",
    color="#c9d3c4",
    fillcolor="#f7f9f4",
    penwidth=1.2,
    margin="0.18,0.10"
  ];
  edge [
    fontname="Helvetica",
    fontsize=9,
    color="#6b7a66",
    arrowsize=0.7
  ];

  start [label="POST /chat/stream", shape=oval, fillcolor="#e8f1e6", color="#9db596"];
  route [label="route\n(router.py)"];
  overview [label="assignment_overview?\n(hỏi số câu / đề bài)", shape=diamond, style="filled", fillcolor="#fff7e6", color="#d9b36c", margin="0.02,0.02"];
  intent [label="intent thuộc\nRETRIEVAL_INTENTS?", shape=diamond, style="filled", fillcolor="#fff7e6", color="#d9b36c", margin="0.02,0.02"];
  retrieve [label="retrieve\nhybrid search trong course_id"];
  answer [label="answer\n(LLM + prompt theo intent)"];
  needs_verify [label="intent cần verify?", shape=diamond, style="filled", fillcolor="#fff7e6", color="#d9b36c", margin="0.02,0.02"];
  verify [label="verify_answer\ncitation + no-solution"];
  retry [label="còn lượt retry?", shape=diamond, style="filled", fillcolor="#fff7e6", color="#d9b36c", margin="0.02,0.02"];
  safe [label="safe_response\n(không verify được)", fillcolor="#fdecec", color="#d99a9a"];
  sanitize [label="sanitize_citations"];
  stream [label="stream SSE\ncitations → token → done", shape=oval, fillcolor="#e8f1e6", color="#9db596"];
  error [label="error event", shape=oval, fillcolor="#fdecec", color="#d99a9a"];

  start -> route;
  route -> overview;
  overview -> stream [label="có (trả lời trực tiếp)"];
  overview -> intent [label="không"];
  intent -> retrieve [label="có"];
  intent -> answer [label="không (không retrieve)"];
  retrieve -> answer;
  answer -> needs_verify;
  needs_verify -> verify [label="có (retrieval)"];
  needs_verify -> sanitize [label="không"];
  verify -> sanitize [label="ok"];
  verify -> retry [label="fail"];
  retry -> answer [label="có"];
  retry -> safe [label="hết"];
  safe -> sanitize;
  sanitize -> stream;

  // Mọi exception trong run_chat() đều rơi vào nhánh này.
  route -> error [style=dashed, label="exception", constraint=false];
  retrieve -> error [style=dashed, constraint=false];
  answer -> error [style=dashed, constraint=false];
  verify -> error [style=dashed, constraint=false];
}
"""


def main() -> int:
    if shutil.which("dot") is None:
        print("Không tìm thấy Graphviz 'dot'. Cài: sudo apt install graphviz", file=sys.stderr)
        return 1

    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/chatbot-pipeline.png")
    output.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["dot", "-Tpng", "-Gdpi=160", "-o", str(output)],
        input=DOT_SOURCE,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    print(f"Đã vẽ: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
