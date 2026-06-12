---
description: Establish a fully bidirectional event channel between the agent and a UI panel using notify_ui, notify_agent, and per-channel file queues. Covers channel ID assignment, agent→UI push, UI→agent signalling, and how to bootstrap an agent-side polling loop across conversation turns.
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

**The critical difference from a normal program:** the agent cannot run a true background loop. Its "loop" is a sequence of explicit tool calls interleaved with `bash sleep` calls to avoid busy-waiting. The loop runs entirely within the agent's current conversation turn and is interrupted when the user sends a new message (which starts a fresh turn).

Pattern:

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

Concretely, in tool calls:

```
call: poll_agent_messages(channel_id)   → []
call: bash sleep 1
call: poll_agent_messages(channel_id)   → []
call: bash sleep 1
call: poll_agent_messages(channel_id)   → [{"event": "player_move", ...}]
call: bash ...process logic...
call: notify_ui(event="state", channel_id, data=new_state)
call: poll_agent_messages(channel_id)   → []   ← back to waiting
...
```

### Terminating the loop

Stop calling `poll_agent_messages` when a terminal state is reached (game over, task complete, explicit `done` event from the UI). There is no automatic timeout — the loop runs until you break or the user sends a new message.

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
