# Playground

Interactive ChatGPT API experiments for long-conversation memory tests.

## Script

- `chatgpt_memory_chat.py`: interactive chat loop with retrieval and memory saving

## Usage

```powershell
python playground/chatgpt_memory_chat.py
```

## Notes

- Uses `OPENAI_API_KEY`
- Stores the local session in `playground/session.db`
- Reuses the keyword/topic memory pipeline from the main prototype
