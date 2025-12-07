import anyio
from claude_agent_sdk import ClaudeAgentOptions, query

async def main():
    options = ClaudeAgentOptions(
        system_prompt="You're a helpful agent",
        permission_mode="default",
        cwd="."
    )

    # Ask the agent to perform an action that requires tools
    async for message in query(
        prompt="Create a file named 'hello_from_agent.txt' with the content 'This was created by the Claude Agent SDK!'",
        options=options
    ):
        print(message)



anyio.run(main)