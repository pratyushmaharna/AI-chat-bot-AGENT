# AI Chat Bot Agent

A simple command-line AI agent in Python. It answers questions, remembers the conversation, and uses tools to complete tasks. It runs on [OpenRouter](https://openrouter.ai), so you can use many different AI models.

## Features

- Q&A with conversation memory
- Calculator for math
- Current date and time
- Notes (saved to `workspace/notes.json`)
- Create, read and list files in a safe `workspace/` folder
- Read web pages from a link
- Multi-step tasks (the agent chains tools automatically)
- Automatic fallback to the next model if one fails

## Requirements

- Python 3.9+
- An OpenRouter API key from https://openrouter.ai/keys

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/pratyushmaharna/AI-chat-bot-AGENT.git
   cd AI-chat-bot-AGENT
   ```

2. Install the dependency:
   ```bash
   python -m pip install openai
   ```

3. Set your API key as an environment variable (never put it in the code):

   **Windows (Command Prompt):**
   ```
   setx OPENROUTER_API_KEY "your-key-here"
   ```
   Then close and reopen your terminal.

   **macOS / Linux:**
   ```bash
   export OPENROUTER_API_KEY="your-key-here"
   ```

4. Run:
   ```bash
   python Agent.py
   ```

## Usage

Type a message at the `You:` prompt. Commands:

| Command | What it does |
|---------|--------------|
| `reset` | Clear the conversation memory |
| `exit`  | Quit the agent |

### Example prompts

- `What is 15% of 2480?`
- `Save a note: submit report on Friday`
- `What notes do I have?`
- `Write a 5-day Python study plan into plan.txt`
- `Summarize https://example.com and save it as summary.txt`

## Configuration

Edit the `MODELS` list near the top of `Agent.py` to change which models are used. They are tried in order if one fails. Browse models at https://openrouter.ai/models and pick ones that support tools.

## Adding your own tool

1. Write a Python function.
2. Add it to `TOOL_FUNCTIONS`.
3. Describe it in `TOOLS` using `_tool(...)`.

## Troubleshooting

| Error | Meaning |
|-------|---------|
| `401` | API key is missing or wrong |
| `402` | No credits on your OpenRouter account |
| `404` / `400` | Model name unavailable (the agent tries the next one) |
| `429` | Rate limit reached, wait a minute |

## Security

- Do not commit your API key. Use the `OPENROUTER_API_KEY` environment variable.
- `.gitignore` excludes `workspace/` and `.env`.
- File tools can only access the `workspace/` folder.

## License

MIT
