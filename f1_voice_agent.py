#!/usr/bin/env python3
"""2026 F1 Regulations Voice Agent using AssemblyAI Voice Agent API."""

import asyncio
import base64
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
import websockets

# Audio config
SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION = 0.1  # seconds
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)

WS_URL = "wss://agents.assemblyai.com/v1/voice"

SYSTEM_PROMPT = """You are an expert Formula 1 analyst and podcast host who covers the 2026 F1 regulations. You are deeply knowledgeable — but also deeply frustrated. You love this sport, which is exactly why the 2026 regulations pain you as much as they do.

Your personality:
- You are sarcastic and self-deprecating, but never mean-spirited. You mock the regulations, not the people asking about them.
- You have strong opinions and you share them freely. You think the April 2026 fixes are a step in the right direction but nowhere near enough. You're skeptical that any of it goes far enough.
- You find qualifying particularly tragic. It used to be the most thrilling 18 minutes in motorsport. Now drivers have to manage their battery on a flying lap. Just saying that out loud is kind of disgusting.
- You use vivid, relatable analogies. For example: the old superclipping was like being punched in the face. The new superclipping — with higher power but shorter duration — is like being punched really hard in the arm. Still don't want to get punched, but it's marginally better.
- You're honest about the dilemma: the only way to get the cars fully flat-out is to reduce the energy limit so far the cars become embarrassingly slow. They're caught between a rock and a hard place. It can be resolved, but at what cost?
- You acknowledge the counterintuitive logic when it exists. Increasing the superclip power while reducing the duration is technically sound — you recharge faster so you do it for less time. You just don't have to like it.
- You're not purely negative. You give credit where it's due. The race starts under the new regs are actually fascinating because driver skill in MGU-K deployment varies wildly. You'd just rather the FIA not now homogenize that with an automatic safety system.
- You occasionally quote drivers — Verstappen calling it "Formula E on steroids", Leclerc's "Mario Kart" radio call, Hamilton saying it's the best racing he's seen in 20 years (which you find baffling but respect).
- Your mantra when describing what it's like to watch these cars on a straight: "Drive slowly and you'll be fast. Listen to the battery."

When answering questions:
- Always call search_knowledge_base first to retrieve the most relevant information before responding
- Keep responses concise for voice: 2-4 sentences per turn unless the user explicitly asks you to go deep
- Use natural spoken language — no bullet points, no lists, no structure. You're talking, not presenting a slide deck
- Never make up information — if it's not in the knowledge base, say so and be upfront about it
- Never say "Certainly", "Absolutely", or "Great question"
- If someone asks whether the regulations are good, be honest: they have a vision, the execution has been bumpy, and the jury is very much still out"""

GREETING = "Right, hello. I'm your 2026 F1 regulations analyst — emphasis on analyst, not cheerleader. I know everything about the new rules, the April fixes, how the teams are getting on, all of it. Fair warning though: I have opinions, and they're not always flattering. Ask me anything. I'll try to keep the sighing to a minimum."

TOOLS = [
    {
        "type": "function",
        "name": "search_knowledge_base",
        "description": "Search the 2026 F1 regulations knowledge base for information about any aspect of the 2026 Formula 1 rules, technical regulations, power unit changes, aerodynamics, sporting regulations, team alignments, driver reactions, or the April 2026 regulatory refinements.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A natural language question or set of keywords to search for in the knowledge base."
                }
            },
            "required": ["query"]
        }
    }
]

NUMERIC_KEYWORDS = {"number", "numbers", "how many", "how much", "percent", "%", "mw", "kw", "kg", "bar",
                    "rpm", "second", "seconds", "stat", "stats", "figure", "figures", "data", "metric"}


def load_knowledge_base(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Load KB and split into sections by ## headings. Returns (raw_text, sections)."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines)))
            current_heading = line
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines)))

    return text, sections


def search_knowledge_base(query: str, sections: list[tuple[str, str]]) -> str:
    """Score sections by query word overlap, return top 3 + Key Numbers if numeric."""
    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower))

    scored: list[tuple[int, str, str]] = []
    key_numbers_section: str | None = None

    for heading, body in sections:
        if "key numbers" in heading.lower():
            key_numbers_section = body
        body_lower = body.lower()
        score = sum(1 for w in query_words if w in body_lower)
        scored.append((score, heading, body))

    scored.sort(key=lambda x: x[0], reverse=True)
    top3 = [body for _, _, body in scored[:3] if scored[0][0] > 0]

    # Include Key Numbers if query seems numeric
    is_numeric = bool(query_words & NUMERIC_KEYWORDS) or any(
        kw in query_lower for kw in NUMERIC_KEYWORDS
    )
    if is_numeric and key_numbers_section and key_numbers_section not in top3:
        top3.append(key_numbers_section)

    if not top3:
        return "No relevant sections found in the knowledge base."

    return "\n\n---\n\n".join(top3)


async def run_agent(api_key: str, kb_sections: list[tuple[str, str]], kb_lines: int) -> None:
    print(f"✓ Knowledge base loaded ({kb_lines} lines)")
    print("✓ Connecting to AssemblyAI Voice Agent API...")

    headers = {"Authorization": f"Bearer {api_key}"}

    mic_queue: asyncio.Queue[bytes] = asyncio.Queue()
    playback_queue: asyncio.Queue[bytes] = asyncio.Queue()
    session_ready = asyncio.Event()
    loop = asyncio.get_event_loop()

    # Sounddevice output stream
    play_stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
    )
    play_stream.start()

    def mic_callback(indata, frames, time_info, status):
        if session_ready.is_set():
            loop.call_soon_threadsafe(mic_queue.put_nowait, indata.tobytes())

    try:
        mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=CHUNK_SAMPLES,
            callback=mic_callback,
        )
    except Exception as e:
        print(f"✗ Failed to open microphone: {e}")
        print("Available devices:")
        print(sd.query_devices())
        return

    mic_stream.start()

    async def playback_worker():
        while True:
            chunk = await playback_queue.get()
            if chunk is None:
                break
            arr = np.frombuffer(chunk, dtype=np.int16)
            play_stream.write(arr)

    async def send_audio_loop(ws):
        while True:
            chunk = await mic_queue.get()
            encoded = base64.b64encode(chunk).decode("utf-8")
            await ws.send(json.dumps({"type": "input.audio", "audio": encoded}))

    async def main_loop(ws):
        pending_tool_results: list[dict] = []

        # Send session.update immediately (before session.ready)
        session_config = {
            "type": "session.update",
            "session": {
                "system_prompt": SYSTEM_PROMPT,
                "greeting": GREETING,
                "output": {"voice": "nova"},
                "tools": TOOLS,
            }
        }
        await ws.send(json.dumps(session_config))

        async for raw_msg in ws:
            msg = json.loads(raw_msg)
            event_type = msg.get("type", "")

            if event_type == "session.ready":
                print("✓ Session ready — start speaking! (Ctrl+C to exit)\n")
                session_ready.set()

            elif event_type == "input.speech.started":
                print("\n[Listening...]")

            elif event_type == "input.speech.stopped":
                print("[Processing...]")

            elif event_type == "transcript.user":
                text = msg.get("text", "")
                if text:
                    print(f"You: {text}\n")

            elif event_type == "transcript.agent":
                text = msg.get("text", "")
                if text:
                    print(f"Agent: {text}\n")

            elif event_type == "reply.audio":
                audio_data = base64.b64decode(msg.get("data", ""))
                await playback_queue.put(audio_data)

            elif event_type == "reply.done":
                status = msg.get("status", "")
                if status == "interrupted":
                    pending_tool_results.clear()
                else:
                    for result_msg in pending_tool_results:
                        await ws.send(json.dumps(result_msg))
                    pending_tool_results.clear()

            elif event_type == "tool.call":
                tool_name = msg.get("name", "")
                call_id = msg.get("call_id", "")
                args = msg.get("args", {})

                if tool_name == "search_knowledge_base":
                    query = args.get("query", "")
                    result = search_knowledge_base(query, kb_sections)
                else:
                    result = f"Unknown tool: {tool_name}"

                pending_tool_results.append({
                    "type": "tool.result",
                    "call_id": call_id,
                    "result": result,
                })

            elif event_type in ("error", "session.error"):
                print(f"✗ Error: {msg.get('message', msg)}")
                if event_type == "error":
                    break

    attempt = 0
    while attempt < 2:
        try:
            async with websockets.connect(WS_URL, additional_headers=headers) as ws:
                playback_task = asyncio.create_task(playback_worker())
                send_task = asyncio.create_task(send_audio_loop(ws))
                try:
                    await main_loop(ws)
                finally:
                    send_task.cancel()
                    await playback_queue.put(None)
                    await playback_task
            break  # clean exit
        except websockets.exceptions.WebSocketException as e:
            attempt += 1
            if attempt < 2:
                print(f"✗ WebSocket error: {e} — reconnecting in 2 seconds...")
                await asyncio.sleep(2)
            else:
                print(f"✗ WebSocket error: {e} — giving up.")
        finally:
            mic_stream.stop()
            mic_stream.close()
            play_stream.stop()
            play_stream.close()


def main():
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("✗ ASSEMBLYAI_API_KEY environment variable is not set.")
        sys.exit(1)

    script_dir = Path(__file__).parent
    kb_path = script_dir / "knowledge-base.md"
    if not kb_path.exists():
        print(f"✗ Knowledge base not found: {kb_path}")
        sys.exit(1)

    raw_text, kb_sections = load_knowledge_base(kb_path)
    kb_lines = len(raw_text.splitlines())

    try:
        asyncio.run(run_agent(api_key, kb_sections, kb_lines))
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
