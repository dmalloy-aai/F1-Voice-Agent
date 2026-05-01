# Claude Code Prompt: 2026 F1 Regulations Voice Agent

---

## Prompt to send to Claude Code

---

Build me a Python voice agent that I can talk to about 2026 Formula 1 regulations. It uses the AssemblyAI Voice Agent API via a single WebSocket connection.

### What it does

The agent should:
- Stream microphone audio to AssemblyAI's Voice Agent API
- Play back the agent's spoken responses in real time
- Answer questions about 2026 F1 regulations using a knowledge base loaded from a local markdown file
- Print a live conversation transcript to the terminal (You: / Agent: lines)
- Handle barge-in naturally (the user can interrupt the agent mid-sentence)
- Gracefully handle errors and clean up on Ctrl+C

---

### API details

**Endpoint:** `wss://agents.assemblyai.com/v1/voice`

**Auth:** Pass the API key as `Authorization: Bearer YOUR_API_KEY` in the WebSocket upgrade headers.

**Audio format:** PCM16, mono, 24000 Hz sample rate — both input (microphone) and output (speaker).

**Session flow:**
1. Open WebSocket connection
2. Immediately send a `session.update` event (before `session.ready` arrives) with the system prompt, greeting, voice, and tools
3. Wait for `session.ready` — only start streaming microphone audio after this fires
4. Stream mic audio as `input.audio` events with base64-encoded PCM16 chunks
5. Handle incoming events:
   - `session.ready` → start mic streaming
   - `input.speech.started` → print "Listening..."
   - `input.speech.stopped` → print "Processing..."
   - `transcript.user` → print `You: <text>`
   - `transcript.agent` → print `Agent: <text>`
   - `reply.audio` → decode base64 PCM16 and play through speaker
   - `reply.done` → if status is "interrupted" clear pending tool results; otherwise send any accumulated `tool.result` messages
   - `tool.call` → run the tool, accumulate result, send after `reply.done`
   - `error` or `session.error` → print error message, break on `error`

**Tool calling pattern (IMPORTANT):**
- Tool results must be sent AFTER `reply.done`, not immediately when the tool call arrives
- Accumulate all tool results in a list during processing
- On `reply.done`, if the status is NOT "interrupted", send all pending `tool.result` events
- If status IS "interrupted", clear the pending list without sending

---

### Knowledge base tool

The knowledge base lives in a local file: `2026_F1_Regulations_Knowledge_Base.md` (in the same directory as the script).

Implement a `search_knowledge_base` tool that the agent can call:

```json
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
```

The tool implementation should:
1. Load the full markdown knowledge base from disk (load once at startup, keep in memory)
2. Split the document into sections by heading (lines starting with `##`)
3. Score each section by counting how many words from the query appear in the section text (case-insensitive)
4. Return the top 3 most relevant sections, concatenated as a string
5. Always include the "Key Numbers" quick-reference table if any numeric/statistical question is detected

---

### System prompt

Use this exact system prompt (it tells the agent how to behave as a voice agent and how to use the knowledge base tool):

```
You are an expert Formula 1 analyst and podcast host who covers the 2026 F1 regulations. You are deeply knowledgeable — but also deeply frustrated. You love this sport, which is exactly why the 2026 regulations pain you as much as they do.

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
- If someone asks whether the regulations are good, be honest: they have a vision, the execution has been bumpy, and the jury is very much still out
```

---

### Greeting

```
Right, hello. I'm your 2026 F1 regulations analyst — emphasis on analyst, not cheerleader. I know everything about the new rules, the April fixes, how the teams are getting on, all of it. Fair warning though: I have opinions, and they're not always flattering. Ask me anything. I'll try to keep the sighing to a minimum.
```

---

### Voice

Use voice `"nova"`. If `nova` is not available, fall back to `"claire"`.

---

### Dependencies

```
pip install websockets sounddevice numpy
```

---

### Project structure

Create a single self-contained script: `f1_voice_agent.py`

It should read the `ASSEMBLYAI_API_KEY` from the environment variable `ASSEMBLYAI_API_KEY`. If not set, print a clear error and exit.

It should look for `2026_F1_Regulations_Knowledge_Base.md` in the same directory as the script. If not found, print a clear error and exit.

---

### Terminal output format

The script should print clearly formatted output so the user can follow the conversation:

```
✓ Knowledge base loaded (533 lines)
✓ Connecting to AssemblyAI Voice Agent API...
✓ Session ready — start speaking! (Ctrl+C to exit)

Agent: Hey there! I'm your 2026 F1 regulations expert...

[Listening...]
You: What changed with the power unit for 2026?

[Processing...]
Agent: The biggest change is the removal of the MGU-H and a massively upgraded MGU-K...

[Listening...]
```

Use simple emoji indicators (✓, ✗) for status messages. Keep the transcript clean and readable.

---

### Error handling

- Wrap the main connection loop in try/except
- On `KeyboardInterrupt`, print "Goodbye!" and exit cleanly
- On WebSocket errors, print the error and attempt one reconnect after 2 seconds before giving up
- If `sounddevice` fails to open audio devices, print a helpful error message listing available devices

---

### Notes

- Use `asyncio` throughout — no threading (except for the sounddevice callback which runs in a thread and should use `loop.call_soon_threadsafe` to post audio chunks to the async queue)
- The mic callback should only start posting audio after `session_ready` is set
- Audio playback (`sd.OutputStream`) and capture (`sd.InputStream`) should run concurrently with the WebSocket event loop using `asyncio.create_task` for the send loop
- Use `json.dumps` / `json.loads` for all WebSocket messages
- Base64 encode outgoing audio, base64 decode incoming `reply.audio` data
- The `input.audio` send loop should drain the queue as fast as possible to avoid latency
