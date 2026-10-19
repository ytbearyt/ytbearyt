import configparser
import json
import locale
import subprocess
import sys

from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
section = config["llm"]

client = OpenAI(base_url=section["base_url"], api_key=section["api_key"])

tools = [
    {
        "type": "function",
        "function": {
            "name": "getDate",
            "description": "获取当前电脑的日期和时间，通过调用本地 date 命令实现",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }
]


def getDate():
    if sys.platform.startswith("win"):
        command = "date /t & time /t"
    else:
        command = "date"
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    return output.strip()


def execute_tool(name, arguments):
    if name == "getDate":
        return getDate()
    return f"未知的工具: {name}"


def stream_chat(messages):
    stream = client.chat.completions.create(
        model=section["model"],
        messages=messages,
        tools=tools,
        stream=True,
    )

    reply = ""
    calls = {}
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if delta.content:
            reply += delta.content
            print(delta.content, end="", flush=True)
        if delta.tool_calls:
            for tc in delta.tool_calls:
                call = calls.setdefault(
                    tc.index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                )
                if tc.id:
                    call["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        call["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        call["function"]["arguments"] += tc.function.arguments
    print()

    ordered = [calls[index] for index in sorted(calls)]
    return reply, ordered


history = []

while True:
    prompt = input("please input your prompt：")
    print("---")
    history.append({"role": "user", "content": prompt})

    while True:
        reply, tool_calls = stream_chat(history)

        message = {"role": "assistant", "content": reply}
        if tool_calls:
            message["tool_calls"] = tool_calls
        history.append(message)

        if not tool_calls:
            break

        for call in tool_calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            print(f"[tool] {name}({arguments})")
            result = execute_tool(name, arguments)
            print(f"[tool result] {result}")
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": name,
                    "content": result,
                }
            )
