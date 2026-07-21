#!/usr/bin/env python3
"""Example: firmware debug agent with CrewAI tools."""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from crewai_tools import build_crewai_tools


def main() -> None:
    tools = build_crewai_tools()
    fw_agent = Agent(
        role="固件调试专家",
        goal="通过串口快速定位系统启动和驱动异常",
        backstory="你熟悉 Linux 嵌入式串口日志、启动链路和驱动诊断。",
        tools=tools,
        verbose=True,
    )

    task = Task(
        description=(
            "列出串口，打开 /dev/ttyACM1，执行 `uname -a` 与 `dmesg | tail -n 30`，"
            "输出诊断结论并关闭串口。"
        ),
        expected_output="包含关键日志和问题判断的简短报告",
        agent=fw_agent,
    )

    crew = Crew(agents=[fw_agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print(result)


if __name__ == "__main__":
    main()
