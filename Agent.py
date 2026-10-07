"""
AI AGENT - single file, OpenRouter
-----------------------------------
Abilities: Q&A with memory, calculator, date/time, notes, files,
           reading web pages, and multi-step tasks.

Setup:   python -m pip install openai
Run:     python agent.py
"""

import ast
import datetime
import json
import operator
import os
import pathlib
import re
import urllib.request

from openai import APIStatusError, OpenAI

# ============================ SETTINGS ======================================
API_KEY = "PASTE_YOUR_NEW_KEY_HERE"   # paste your OpenRouter key here
                                    # (or set env var OPENROUTER_API_KEY)
MODELS = [                             # tried in order if one fails
    "google/gemini-2.0-flash-001",
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct:free",
]
# ============================================================================

PLACEHOLDER = "PASTE_YOUR_NEW_KEY_HERE"
KEY = os.getenv("OPENROUTER_API_KEY") or API_KEY

WORKSPACE = pathlib.Path("workspace")
WORKSPACE.mkdir(exist_ok=True)
NOTES_FILE = WORKSPACE / "notes.json"

SYSTEM_PROMPT = """You are a helpful, friendly AI agent that answers questions
and completes tasks.
- Be clear and concise.
- Use tools when useful: calculator for math, get_datetime for date/time,
  save_note/get_notes for things to remember, file tools for the workspace,
  and fetch_url to read a web page the user gives you.
- For multi-step tasks, use tools step by step, then give a clear final answer.
- If unsure, say so instead of guessing."""

# =============================== TOOLS ======================================

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expression")


def calculator(expression):
    return str(_eval(ast.parse(expression, mode="eval").body))


def get_datetime():
    return datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")


def _safe_path(name):
    path = (WORKSPACE / name).resolve()
    if WORKSPACE.resolve() not in path.parents:
        raise ValueError("Access outside the workspace is not allowed")
    return path


def read_file(filename):
    return _safe_path(filename).read_text(encoding="utf-8")[:20000]


def write_file(filename, content):
    path = _safe_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Saved {filename}"


def list_files():
    files = [str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob("*") if p.is_file()]
    return "\n".join(files) or "(workspace is empty)"


def _load_notes():
    return json.loads(NOTES_FILE.read_text(encoding="utf-8")) if NOTES_FILE.exists() else []


def save_note(text):
    notes = _load_notes()
    notes.append({"time": get_datetime(), "text": text})
    NOTES_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")
    return "Note saved."


def get_notes():
    notes = _load_notes()
    return "\n".join(f"- [{n['time']}] {n['text']}" for n in notes) or "No notes yet."


def fetch_url(url):
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read(500_000).decode("utf-8", errors="ignore")
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()[:8000]


TOOL_FUNCTIONS = {
    "calculator": lambda a: calculator(a["expression"]),
    "get_datetime": lambda a: get_datetime(),
    "read_file": lambda a: read_file(a["filename"]),
    "write_file": lambda a: write_file(a["filename"], a["content"]),
    "list_files": lambda a: list_files(),
    "save_note": lambda a: save_note(a["text"]),
    "get_notes": lambda a: get_notes(),
    "fetch_url": lambda a: fetch_url(a["url"]),
}


def _tool(name, description, props=None):
    props = props or {}
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {
            "type": "object",
            "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
            "required": list(props),
        }}}


TOOLS = [
    _tool("calculator", "Evaluate a math expression, e.g. '2480*0.15'.", {"expression": "Math expression"}),
    _tool("get_datetime", "Get the current local date and time."),
    _tool("read_file", "Read a text file from the workspace.", {"filename": "File name"}),
    _tool("write_file", "Create or overwrite a text file in the workspace.",
          {"filename": "File name", "content": "Full file content"}),
    _tool("list_files", "List all files in the workspace."),
    _tool("save_note", "Save a note the user wants remembered.", {"text": "Note text"}),
    _tool("get_notes", "Retrieve all saved notes."),
    _tool("fetch_url", "Download a web page and return its text.", {"url": "Full URL"}),
]

# =============================== AGENT ======================================


class Agent:
    def __init__(self):
        self.client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=KEY)
        self.model_index = 0
        self.reset()

    def reset(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _complete(self):
        while True:
            try:
                return self.client.chat.completions.create(
                    model=MODELS[self.model_index], messages=self.messages, tools=TOOLS)
            except APIStatusError as e:
                if e.status_code in (400, 402, 404, 429, 503) and self.model_index < len(MODELS) - 1:
                    print(f"  [{MODELS[self.model_index]} failed ({e.status_code}), trying next]")
                    self.model_index += 1
                    continue
                raise

    def ask(self, text):
        self.messages.append({"role": "user", "content": text})
        for _ in range(10):
            msg = self._complete().choices[0].message
            entry = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.function.name, "arguments": c.function.arguments}}
                    for c in msg.tool_calls]
            self.messages.append(entry)
            if not msg.tool_calls:
                return msg.content or "(no answer)"
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    print(f"  [tool] {call.function.name} {args}")
                    result = TOOL_FUNCTIONS[call.function.name](args)
                except Exception as e:
                    result = f"Error: {e}"
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
        return "I hit my step limit. Try a simpler request."


def main():
    if not KEY or KEY == PLACEHOLDER:
        print("Open agent.py and paste your OpenRouter API key into the API_KEY line.")
        return
    agent = Agent()
    print("AI Agent ready. Commands: 'reset' clears memory, 'exit' quits.\n")
    while True:
        text = input("You: ").strip()
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break
        if text.lower() == "reset":
            agent.reset()
            print("Memory cleared.\n")
            continue
        try:
            print(f"\nAgent: {agent.ask(text)}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()