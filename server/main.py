from mcp.server.fastmcp import FastMCP
from server import db, tools, resources, prompts

mcp = FastMCP("studybuddy", log_level="WARNING")
db.init_db()
tools.register(mcp)
resources.register(mcp)
prompts.register(mcp)

if __name__ == "__main__":
    mcp.run()