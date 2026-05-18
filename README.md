# ✈️ flight-search-agent

A ReAct (Reason + Act) agent that searches live flight prices using an LLM loop and the SkyScanner API via RapidAPI.

## How it works

The agent prompts an LLM with a scratchpad of `Thought → Action → Observation` steps until it writes a `Final Answer`. Each step can call the `searchflights` tool, which hits the `flights-sky.p.rapidapi.com` endpoint and returns real prices.

## Requirements

- Python 3.10+ (or Docker with a `python` image — no local install needed)
- An [OpenAI API key](https://platform.openai.com/account/api-keys)
- A [RapidAPI key](https://rapidapi.com/apiheya/api/flights-sky) subscribed to the **Flights Sky** API

## Quickstart (Docker)

```bash
docker run --rm -it \
  -e OPENAI_API_KEY=sk-... \
  -e RAPIDAPI_KEY=... \
  python:3.12-slim bash -c \
  "pip install -q openai requests python-dateutil python-dotenv \
   && python flight_search3.py"
```

Copy `flight_search3.py` into the container (or mount it with `-v $(pwd):/app -w /app`).

## Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI key (uses `gpt-3.5-turbo` by default) |
| `RAPIDAPI_KEY` | Your RapidAPI key for `flights-sky.p.rapidapi.com` |

Both can also live in a `.env` file in the same directory — `python-dotenv` loads it automatically.

## Project structure

```
flight_search3.py   # All logic in one file: tools, ReAct loop, parser, entry point
.env                # Optional: store API keys here (never commit this)
```

## Configuration

- **Model**: swap `gpt-3.5-turbo` for `gpt-4o` in `run_agent()` for better tool-call accuracy
- **Max steps**: change `max_steps=5` to allow more reasoning hops
- **Scratchpad limit**: `truncate_scratchpad` keeps the prompt under ~24 000 chars to control cost
- **Retries**: the API call retries up to 3 times with exponential backoff on connection errors

## Limitations

The parser expects the LLM to output well-formed `Action Input` as JSON or `key=value` pairs; weaker models occasionally deviate. The `get_date_range` helper is implemented but not yet used — it's ready for a ±2-day flexible search feature.
