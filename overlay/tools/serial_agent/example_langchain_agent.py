#!/usr/bin/env python3
"""Example: firmware debug agent with LangChain tools."""

from __future__ import annotations

from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI

from langchain_tools import build_langchain_tools


def main() -> None:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools = build_langchain_tools()
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )
    task = (
        "你是固件调试专家。先列出串口，打开 /dev/ttyACM1，执行 uname -a 和 dmesg | tail -n 20，"
        "最后关闭串口并总结异常。"
    )
    print(agent.run(task))


if __name__ == "__main__":
    main()
