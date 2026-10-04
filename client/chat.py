import asyncio
import json
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server = StdioServerParameters(command=sys.executable, args=["-m", "server.main"])
claude = anthropic.AsyncAnthropic()
MODEL = "claude-opus-5-5"
SYSTEM = ("You are StudyBuddy, a study assistant for a course on Claude tool use and MCP "
          "(lessons 32-49). Use the tools to look up lessons, save notes and run quizzes. "
          "Keep answers short.")


def to_claude_tools(mcp_tools):
    # MCP and the Claude API describe tools almost the same way; only the schema key differs
    return [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in mcp_tools]


async def run_turn(session, tools, messages):
    while True:
        response = await claude.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"  [tool] {block.name}({json.dumps(block.input)})")
            r = await session.call_tool(block.name, block.input)
            text = "\n".join(c.text for c in r.content if c.type == "text")
            if r.isError:
                print(f"  [tool error] {text}")
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": text, "is_error": r.isError})
        messages.append({"role": "user", "content": results})  # all results in ONE message


async def main():
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = to_claude_tools((await session.list_tools()).tools)
            print(f"Connected: {len(tools)} tools. Type 'quit' to exit.\n")

            messages = []
            while True:
                user = input("you> ").strip()
                if user in ("quit", "exit"):
                    break
                if not user:
                    continue
                messages.append({"role": "user", "content": user})
                reply = await run_turn(session, tools, messages)
                print(f"\nclaude> {reply}\n")


asyncio.run(main())