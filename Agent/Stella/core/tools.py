"""Local tools available to the language model."""

import locale
import mimetypes
import os
import shutil
import subprocess
import sys
from typing import Any


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
DECODE_ENCODINGS = tuple(dict.fromkeys(("utf-8", locale.getpreferredencoding(False), "gbk")))

PATH_PROP = {"type": "string", "description": "文件或目录路径，支持相对路径和绝对路径"}


def _function_tool(name: str, description: str, properties=None, required=None) -> dict[str, Any]:
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


TOOLS = [
    _function_tool("getDate", "获取当前电脑的日期和时间，通过调用本地 date 命令实现"),
    _function_tool("getCurrentDir", "获取当前工作目录"),
    _function_tool("listDir", "列出指定目录下的所有文件和子目录", {"path": PATH_PROP}, ["path"]),
    _function_tool("getFileType", "获取指定文件的文件类型（如文本、图片、Python 源码等）", {"path": PATH_PROP}, ["path"]),
    _function_tool("readFile", "获取指定文件的内容，仅支持纯文本格式文件", {"path": PATH_PROP}, ["path"]),
    _function_tool(
        "createFile",
        "根据指定的目录和文件名创建新文件，可选写入初始内容",
        {
            "directory": {"type": "string", "description": "新文件所在的目录路径"},
            "filename": {"type": "string", "description": "新文件名，如 note.txt"},
            "content": {"type": "string", "description": "文件初始内容，缺省为空文件"},
        },
        ["directory", "filename"],
    ),
    _function_tool(
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
    _function_tool("createDir", "创建新目录（包含多级目录）", {"path": PATH_PROP}, ["path"]),
    _function_tool("removeDir", "删除目录，支持非空目录（连同其中所有文件和子目录一起删除）", {"path": PATH_PROP}, ["path"]),
    _function_tool("removeFile", "删除指定的文件", {"path": PATH_PROP}, ["path"]),
    _function_tool(
        "rename",
        "重命名指定的文件或目录，文件和目录均支持",
        {
            "path": PATH_PROP,
            "new_name": {"type": "string", "description": "新名称或新的完整路径"},
        },
        ["path", "new_name"],
    ),
]


def _detect_encoding(data: bytes) -> str | None:
    for encoding in DECODE_ENCODINGS:
        try:
            data.decode(encoding)
            return encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _read_bytes(path: str, limit: int = MAX_READ_BYTES) -> bytes:
    with open(path, "rb") as file:
        data = file.read(limit)
    return data[:-4] if len(data) == limit else data


def get_date() -> str:
    command = "date /t & time /t" if sys.platform.startswith("win") else "date"
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )
    return ((result.stdout or "") + (result.stderr or "")).strip()


def get_current_dir() -> str:
    return f"当前工作目录：{os.getcwd()}"


def list_dir(path: str) -> str:
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：目录不存在：{target}"
    if not os.path.isdir(target):
        return f"错误：不是目录：{target}"
    with os.scandir(target) as entries:
        items = [("[目录] " if entry.is_dir() else "[文件] ") + entry.name for entry in entries]
    items.sort(key=str.lower)
    return f"{target} 下共 {len(items)} 项：\n" + "\n".join(items) if items else f"目录为空：{target}"


def get_file_type(path: str) -> str:
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：路径不存在：{target}"
    if os.path.isdir(target):
        return f"这是一个目录：{target}"
    extension = os.path.splitext(target)[1].lower()
    mime_type = EXT_TYPES.get(extension)
    if mime_type is None:
        mime_type = mimetypes.guess_type(target)[0] or f"未知类型（扩展名 {extension or '无'}）"
    is_text = _detect_encoding(_read_bytes(target)) is not None
    form = "纯文本文件" if is_text else "二进制文件"
    return f"文件类型：{mime_type}\n内容形式：{form}\n大小：{os.path.getsize(target)} 字节\n路径：{target}"


def read_file(path: str) -> str:
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
    return text[:MAX_READ_CHARS] + "\n...（内容过长，已截断）" if len(text) > MAX_READ_CHARS else text


def create_file(directory: str, filename: str, content: str = "") -> str:
    target = os.path.abspath(os.path.join(directory, filename))
    if os.path.isdir(target):
        return f"错误：同名目录已存在：{target}"
    if os.path.exists(target):
        return f"错误：文件已存在：{target}（如需修改请使用 editFile）"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    data = str(content).encode("utf-8")
    with open(target, "wb") as file:
        file.write(data)
    return f"已创建文件：{target}（{len(data)} 字节）"


def edit_file(path: str, content: str, mode: str = "overwrite") -> str:
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
        text, action = data.decode(encoding) + str(content), "追加写入"
    elif mode == "overwrite":
        text, action = str(content), "覆盖写入"
    else:
        return f"错误：不支持的 mode：{mode}（可选 overwrite / append）"
    with open(target, "wb") as file:
        file.write(text.encode(encoding, errors="replace"))
    return f"已{action}：{target}（当前 {os.path.getsize(target)} 字节）"


def create_dir(path: str) -> str:
    target = os.path.abspath(path)
    if os.path.exists(target):
        return f"目录已存在：{target}" if os.path.isdir(target) else f"错误：已存在同名文件：{target}"
    os.makedirs(target)
    return f"已创建目录：{target}"


def remove_dir(path: str) -> str:
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


def remove_file(path: str) -> str:
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return f"错误：文件不存在：{target}"
    if os.path.isdir(target):
        return f"错误：这是目录，不是文件：{target}（请使用 removeDir）"
    os.remove(target)
    return f"已删除文件：{target}"


def rename_path(path: str, new_name: str) -> str:
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


HANDLERS = {
    "getDate": lambda _: get_date(),
    "getCurrentDir": lambda _: get_current_dir(),
    "listDir": lambda arguments: list_dir(arguments["path"]),
    "getFileType": lambda arguments: get_file_type(arguments["path"]),
    "readFile": lambda arguments: read_file(arguments["path"]),
    "createFile": lambda arguments: create_file(arguments["directory"], arguments["filename"], arguments.get("content", "")),
    "editFile": lambda arguments: edit_file(arguments["path"], arguments["content"], arguments.get("mode") or "overwrite"),
    "createDir": lambda arguments: create_dir(arguments["path"]),
    "removeDir": lambda arguments: remove_dir(arguments["path"]),
    "removeFile": lambda arguments: remove_file(arguments["path"]),
    "rename": lambda arguments: rename_path(arguments["path"], arguments["new_name"]),
}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    handler = HANDLERS.get(name)
    if handler is None:
        return f"未知的工具: {name}"
    try:
        return handler(arguments)
    except Exception as exc:
        return f"错误：{type(exc).__name__}: {exc}"