import configparser
import json
import locale
import mimetypes
import os
import shutil
import subprocess
import sys

from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
section = config["llm"]

client = OpenAI(base_url=section["base_url"], api_key=section["api_key"])

def fn(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


PATH_PROP = {
    "type": "string",
    "description": "文件或目录路径，支持相对路径和绝对路径",
}

tools = [
    fn(
        "getDate",
        "获取当前电脑的日期和时间，通过调用本地 date 命令实现",
    ),
    fn(
        "getCurrentDir",
        "获取当前工作目录",
    ),
    fn(
        "listDir",
        "列出指定目录下的所有文件和子目录",
        {"path": PATH_PROP},
        ["path"],
    ),
    fn(
        "getFileType",
        "获取指定文件的文件类型（如文本、图片、Python 源码等）",
        {"path": PATH_PROP},
        ["path"],
    ),
    fn(
        "readFile",
        "获取指定文件的内容，仅支持纯文本格式文件",
        {"path": PATH_PROP},
        ["path"],
    ),
    fn(
        "createFile",
        "根据指定的目录和文件名创建新文件，可选写入初始内容",
        {
            "directory": {"type": "string", "description": "新文件所在的目录路径"},
            "filename": {"type": "string", "description": "新文件名，如 note.txt"},
            "content": {"type": "string", "description": "文件初始内容，缺省为空文件"},
        },
        ["directory", "filename"],
    ),
    fn(
        "editFile",
        "编辑指定文件的内容，仅支持纯文本格式文件；mode 为 overwrite 表示整体覆盖，append 表示在末尾追加",
        {
            "path": PATH_PROP,
            "content": {"type": "string", "description": "要写入的文本内容"},
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append"],
                "description": "写入方式：overwrite 覆盖（默认），append 追加",
            },
        },
        ["path", "content"],
    ),
    fn(
        "createDir",
        "创建新目录（包含多级目录）",
        {"path": PATH_PROP},
        ["path"],
    ),
    fn(
        "removeDir",
        "删除目录，支持非空目录（连同其中所有文件和子目录一起删除）",
        {"path": PATH_PROP},
        ["path"],
    ),
    fn(
        "removeFile",
        "删除指定的文件",
        {"path": PATH_PROP},
        ["path"],
    ),
    fn(
        "rename",
        "重命名指定的文件或目录，文件和目录均支持",
        {
            "path": PATH_PROP,
            "new_name": {
                "type": "string",
                "description": "新名称（如 note2.txt，相对于原所在目录）或新的完整路径",
            },
        },
        ["path", "new_name"],
    ),
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


MAX_READ_CHARS = 20000
MAX_READ_BYTES = 2 * 1024 * 1024

EXT_TYPES = {
    ".py": "text/x-python（Python 源代码文件）",
    ".log": "text/plain（日志文本文件）",
    ".ini": "text/plain（INI 配置文本文件）",
    ".cfg": "text/plain（配置文本文件）",
    ".yaml": "text/yaml（YAML 文本文件）",
    ".yml": "text/yaml（YAML 文本文件）",
    ".sh": "text/x-shellscript（Shell 脚本文本文件）",
    ".bat": "text/plain（Windows 批处理文本文件）",
    ".ps1": "text/plain（PowerShell 脚本文本文件）",
    ".md": "text/markdown（Markdown 文本文件）",
    ".csv": "text/csv（CSV 文本文件）",
}

DECODE_ENCODINGS = ("utf-8", locale.getpreferredencoding(False), "gbk")


def _detect_encoding(data):
    if not data:
        return "utf-8"
    for encoding in DECODE_ENCODINGS:
        try:
            data.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _read_bytes(path, limit=MAX_READ_BYTES):
    with open(path, "rb") as f:
        data = f.read(limit)
    if len(data) == limit:
        data = data[:-4]
    return data


def getCurrentDir():
    return f"当前工作目录：{os.getcwd()}"


def listDir(path):
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：目录不存在：{target}"
    if not os.path.isdir(target):
        return f"错误：不是目录：{target}"
    entries = []
    with os.scandir(target) as it:
        for entry in it:
            entries.append(("[目录] " if entry.is_dir() else "[文件] ") + entry.name)
    entries.sort(key=str.lower)
    if not entries:
        return f"目录为空：{target}"
    return f"{target} 下共 {len(entries)} 项：\n" + "\n".join(entries)


def getFileType(path):
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：路径不存在：{target}"
    if os.path.isdir(target):
        return f"这是一个目录：{target}"
    ext = os.path.splitext(target)[1].lower()
    if ext in EXT_TYPES:
        kind = EXT_TYPES[ext]
    else:
        mime, _ = mimetypes.guess_type(target)
        kind = mime if mime else f"未知类型（扩展名 {ext or '无'}）"
    encoding = _detect_encoding(_read_bytes(target))
    form = "纯文本文件" if encoding else "二进制文件"
    return f"文件类型：{kind}\n内容形式：{form}\n大小：{os.path.getsize(target)} 字节\n路径：{target}"


def readFile(path):
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：文件不存在：{target}"
    if os.path.isdir(target):
        return f"错误：这是目录，不是文件：{target}"
    if os.path.getsize(target) > MAX_READ_BYTES:
        return f"错误：文件过大（{os.path.getsize(target)} 字节），仅支持 {MAX_READ_BYTES} 字节以内的纯文本文件"
    data = _read_bytes(target)
    encoding = _detect_encoding(data)
    if encoding is None:
        return f"错误：{target} 不是纯文本格式文件，readFile 仅支持纯文本文件"
    text = data.decode(encoding)
    if not text:
        return "（文件为空）"
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + "\n...（内容过长，已截断）"
    return text


def createFile(directory, filename, content=""):
    target = os.path.abspath(os.path.join(directory, filename))
    if os.path.isdir(target):
        return f"错误：同名目录已存在：{target}"
    if os.path.exists(target):
        return f"错误：文件已存在：{target}（如需修改请使用 editFile）"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    data = str(content).encode("utf-8")
    with open(target, "wb") as f:
        f.write(data)
    return f"已创建文件：{target}（{len(data)} 字节）"


def editFile(path, content, mode="overwrite"):
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：文件不存在：{target}（如需新建请使用 createFile）"
    if os.path.isdir(target):
        return f"错误：这是目录，不是文件：{target}"
    if os.path.getsize(target) > MAX_READ_BYTES:
        return f"错误：文件过大，仅支持 {MAX_READ_BYTES} 字节以内的纯文本文件"
    data = _read_bytes(target)
    encoding = _detect_encoding(data)
    if encoding is None:
        return f"错误：{target} 不是纯文本格式文件，editFile 仅支持纯文本文件"
    mode = mode or "overwrite"
    if mode == "append":
        text = data.decode(encoding) + str(content)
        action = "追加写入"
    elif mode == "overwrite":
        text = str(content)
        action = "覆盖写入"
    else:
        return f"错误：不支持的 mode：{mode}（可选 overwrite / append）"
    with open(target, "wb") as f:
        f.write(text.encode(encoding, errors="replace"))
    return f"已{action}：{target}（当前 {os.path.getsize(target)} 字节）"


def createDir(path):
    target = os.path.abspath(path)
    if os.path.exists(target):
        if os.path.isdir(target):
            return f"目录已存在：{target}"
        return f"错误：已存在同名文件：{target}"
    os.makedirs(target)
    return f"已创建目录：{target}"


def removeDir(path):
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：目录不存在：{target}"
    if not os.path.isdir(target):
        return f"错误：这是文件，不是目录：{target}（请使用 removeFile）"
    if os.path.dirname(target) == target:
        return f"错误：不允许删除根目录：{target}"
    if os.path.normcase(target) == os.path.normcase(os.getcwd()):
        return "错误：不允许删除当前工作目录"
    shutil.rmtree(target)
    return f"已删除目录及其全部内容：{target}"


def removeFile(path):
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：文件不存在：{target}"
    if os.path.isdir(target):
        return f"错误：这是目录，不是文件：{target}（请使用 removeDir）"
    os.remove(target)
    return f"已删除文件：{target}"


def rename(path, new_name):
    source = os.path.abspath(path)
    if not os.path.exists(source):
        return f"错误：路径不存在：{source}"
    name = str(new_name).strip()
    if not name:
        return "错误：新名称不能为空"
    if os.path.isabs(name) or os.path.sep in name or (os.path.altsep and os.path.altsep in name):
        target = os.path.abspath(name)
    else:
        target = os.path.abspath(os.path.join(os.path.dirname(source), name))
    if target == source:
        return f"新名称与原名称相同，无需重命名：{source}"
    if not os.path.isdir(os.path.dirname(target)):
        return f"错误：目标所在目录不存在：{os.path.dirname(target)}"
    if os.path.exists(target) and os.path.normcase(target) != os.path.normcase(source):
        return f"错误：目标已存在：{target}"
    os.rename(source, target)
    kind = "目录" if os.path.isdir(target) else "文件"
    return f"已重命名{kind}：{source} -> {target}"


handlers = {
    "getDate": lambda a: getDate(),
    "getCurrentDir": lambda a: getCurrentDir(),
    "listDir": lambda a: listDir(a["path"]),
    "getFileType": lambda a: getFileType(a["path"]),
    "readFile": lambda a: readFile(a["path"]),
    "createFile": lambda a: createFile(a["directory"], a["filename"], a.get("content", "")),
    "editFile": lambda a: editFile(a["path"], a["content"], a.get("mode") or "overwrite"),
    "createDir": lambda a: createDir(a["path"]),
    "removeDir": lambda a: removeDir(a["path"]),
    "removeFile": lambda a: removeFile(a["path"]),
    "rename": lambda a: rename(a["path"], a["new_name"]),
}


def execute_tool(name, arguments):
    handler = handlers.get(name)
    if handler is None:
        return f"未知的工具: {name}"
    try:
        return handler(arguments)
    except Exception as exc:
        return f"错误：{type(exc).__name__}: {exc}"


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

if __name__ == "__main__":
    while True:
        try:
            prompt = input("please input your prompt：")
        except (EOFError, KeyboardInterrupt):
            print()
            break
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
