import configparser
import sys

from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
section = config["llm"]

client = OpenAI(base_url=section["base_url"], api_key=section["api_key"])

history = []

while True:
    prompt = input("please input your prompt：")
    print("---")
    history.append({"role": "user", "content": prompt})

    stream = client.chat.completions.create(
        model=section["model"],
        messages=history,
        stream=True,
    )

    reply = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            reply += delta
            print(delta, end="", flush=True)
    print()
    history.append({"role": "assistant", "content": reply})
