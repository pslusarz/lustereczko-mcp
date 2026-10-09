---
description: Establish a fully bidirectional event channel between the agent and a UI panel using notify_ui, notify_agent, and per-channel file queues. Covers channel ID assignment, agent→UI push, UI→agent signalling, and how the agent wakes up for UI messages without the user typing in chat (background watcher, or polling inside the turn).
---

# Bidirectional events recipe

Lustereczko's `notify_ui` / `poll_ui_messages` / `notify_agent` / `poll_agent_messages` tools implement two independent FIFO queues, one in each direction, backed by files under `logs/channels/`. Each direction has its own file per channel so channels never interfere with each other and concurrent writes are safe under `fcntl` locking.

## 1. Generate and embed a channel ID

The agent owns the channel ID. Generate it before calling `display_ui_to_user`, then embed it as a literal constant in the HTML fragment. Both sides know the ID from the start — no handshake round-trip is needed.

```python
import time, json

channel_id = f"ch-{int(time.time() * 1000)}"   # e.g. "ch-1780883109443"

html = f"""
<script>
  const MY_CHANNEL = {json.dumps(channel_id)};
  // use MY_CHANNEL in every poll_ui_messages / notify_agent call
</script>
"""
display_ui_to_user(html_fragment=html)
```

Old UI instances that are still alive keep polling their own stale channel ID and receive nothing.

## 2. Agent → UI: push an event

Call `notify_ui` at any point after rendering. The event is enqueued immediately; the UI picks it up on its next poll cycle.

```python
notify_ui(
    event="state",
    channel_id=channel_id,
    data={"board": [...], "status": "your_turn"},
)
```

The UI drains the queue by calling `poll_ui_messages` on a timer (see the `ui-agent-communication` best-practice doc for the full polling loop template). Pass `channel_id: MY_CHANNEL` in the `arguments` object.

## 3. UI → Agent: receive an event

The UI enqueues an event with `notify_agent`:

```js
await window.app.callServerTool({
  name: 'notify_agent',
  arguments: { event: 'player_move', channel_id: MY_CHANNEL, data: { cell: 4 } }
});
```

The agent drains its queue with `poll_agent_messages`:

```python
messages = poll_agent_messages(channel_id=channel_id)
# → [{"event": "player_move", "data": {"cell": 4}}, ...]
```

The call returns all pending messages in FIFO order and atomically clears the queue.

## 4. Bootstrap the agent polling loop

**The critical difference from a normal program:** the agent cannot run a true background loop, and it only acts during a turn. Something has to give it a turn when the UI sends a message, without the user typing in the chat.

### Preferred: a watcher that wakes you

If your host notifies you when a background terminal command finishes (GitHub Copilot does), run a small watcher in the background. It blocks until the channel's agent queue has messages, then exits; the exit gives you a turn. Waiting costs no tokens and leaves the chat free.

```python
# watch.py <channel_id> [timeout_s] — read-only; exits 0 when messages are waiting
import json, sys, time
from pathlib import Path
q = Path("<lustereczko install dir>/logs/channels") / f"agent_{sys.argv[1]}.json"
end = time.monotonic() + float(sys.argv[2] if len(sys.argv) > 2 else 1800)
while time.monotonic() < end:
    try: items = json.loads(q.read_text() or "[]")
    except (FileNotFoundError, json.JSONDecodeError): items = []
    if items: print(len(items), "message(s)"); sys.exit(0)
    time.sleep(0.5)
sys.exit(2)
```

```
1. start watcher (background) → 2. display_ui_to_user
on watcher exit:
   poll_agent_messages(channel_id) → process each → notify_ui(...) → start watcher again
```

Start the watcher before rendering so the UI's first message is not missed. Background wake-ups can lag 10–30 s; for snappier replies (e.g. while the user is actively asking), stay in the turn and run the same watcher in the foreground with a short timeout, answer, and repeat.

### Fallback: poll inside the turn

Without background notifications, loop with explicit tool calls and `bash sleep` to avoid busy-waiting. The loop runs entirely within the current turn and is interrupted when the user sends a new message.

```
1. display_ui_to_user  (renders the UI, starts its poll timer)
2. notify_ui(event, channel_id, data)   ← push initial state if needed
3. loop:
     a. poll_agent_messages(channel_id) → messages
     b. if messages:
          process each message
          notify_ui(...)  ← push response
          if terminal condition: break
     c. else:
          bash sleep 1    ← yield before retrying
```

### Terminating the loop

Stop re-arming the watcher, or stop calling `poll_agent_messages`, when a terminal state is reached (game over, task complete, explicit `done` event from the UI).

### State persistence across polls

The agent has no in-memory state between tool calls. Persist game or task state to a file and read it back each iteration:

```bash
# write after processing
echo '{"board": [...]}' > /tmp/my_state.json

# read at next iteration
python3 -c "import json; print(json.load(open('/tmp/my_state.json'))['board'])"
```

Alternatively, have the UI send the full current state back with each event so the agent never needs to store it separately.

## Notes

- Each `display_ui_to_user` call **must** use a fresh `channel_id`. Reusing an old ID means any zombie instances of that UI will consume messages meant for the new one.
- `poll_agent_messages` is listed in `_SILENT_TOOLS` on the server and does not produce log noise — poll freely.
- If the agent needs to offload heavy computation (e.g. minimax, data transforms) between receiving an event and sending the response, use `bash` to run a helper script rather than inlining the logic. Keep the tool-call loop itself thin.
- The UI's `poll_ui_messages` call and the agent's `poll_agent_messages` call both clear the queue atomically. A single consumer per direction is assumed — do not run two agent polling loops on the same channel simultaneously.
