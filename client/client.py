import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server = StdioServerParameters(command=sys.executable, args=["-m", "server.main"])


async def main():
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()          # handshake: agree on version + capabilities

            tools = await session.list_tools()
            print("TOOLS:")
            for t in tools.tools:
                print(f"  {t.name}: {t.description.splitlines()[0]}")

            resources = await session.list_resources()
            print("RESOURCES:")
            for r in resources.resources:
                print(f"  {r.uri}")

            templates = await session.list_resource_templates()
            print("RESOURCE TEMPLATES:")
            for t in templates.resourceTemplates:
                print(f"  {t.uriTemplate}")

            prompts = await session.list_prompts()
            print("PROMPTS:")
            for p in prompts.prompts:
                args = [a.name for a in (p.arguments or [])]
                print(f"  {p.name}({', '.join(args)})")
                
                
            
            print("\n--- TOOL: Claude will decide to call these ---")
            result = await session.call_tool("get_lesson", {"lesson_id": 37})
            print(result.content[0].text, "| isError:", result.isError)

            bad = await session.call_tool("get_lesson", {"lesson_id": 99})
            print(bad.content[0].text, "| isError:", bad.isError)

            print("\n--- RESOURCE: your app reads data ---")
            res = await session.read_resource("notes://37")
            print(res.contents[0].text)

            print("\n--- PROMPT: the user picks a template ---")
            p = await session.get_prompt("make_quiz", {"topic": "retries"})
            print(p.messages[0].content.text)


asyncio.run(main())