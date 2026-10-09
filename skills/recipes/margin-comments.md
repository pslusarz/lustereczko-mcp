---
description: Let the user ask the agent about a selected passage of a long text and get the answer in a margin comment next to it, like comments on a document. Threads stay attached to their passage, so follow-ups keep their context. Builds on recipes:bidirectional-events.
---

# Margin comments recipe

The user highlights a passage, clicks **Ask about this**, and types a question. The question goes to the agent over a channel; the answer appears in a comment card beside the passage, and replies stay in that card. Good for long texts (documents, the agent's own long answers) where a question about something far up the page would get lost in chat.

Read `recipes:bidirectional-events` first for channel ids and how the agent wakes up.

## Protocol

| direction | event | data |
|---|---|---|
| UI → agent | `ready` | `{}` on load |
| agent → UI | `hello` | `{}`: UI shows "Agent is listening" |
| UI → agent | `ask` | `{thread_id, quote, paragraph, question, history: [{role, text}]}` |
| agent → UI | `answer` | `{thread_id, text}` |

Send the whole paragraph and the thread's history with every `ask`, so the agent needs no state between turns.

## UI skeleton

Layout: a two-column grid, text on the left, a `position: relative` margin on the right. Cards are absolutely positioned level with their highlight. Give the outer div an explicit pixel height and let the text column scroll.

```js
// Selection → floating button. Keep the selection inside one <p>.
text.addEventListener("mouseup", () => setTimeout(() => {
  const sel = getSelection();
  if (sel.isCollapsed || !sel.toString().trim()) return (askbtn.style.display = "none");
  const range = sel.getRangeAt(0), p = range.startContainer.parentElement.closest("p");
  pending = { range: range.cloneRange(), p };
  // position askbtn just above range.getBoundingClientRect(), then show it
}));
askbtn.addEventListener("mousedown", (e) => e.preventDefault()); // keep the selection

function openThread({ range, p }) {
  const mark = document.createElement("mark");
  mark.appendChild(range.extractContents()); range.insertNode(mark);
  // create a card in the margin: quote, messages, textarea + Ask button
  // threads.set(id, { id, quote: mark.textContent, paragraph: p.textContent, mark, card, history: [] })
}

function ask(t, question) {
  // append the question and a "Thinking…" line to the card
  window.app.callServerTool({ name: "notify_agent", arguments: { event: "ask", channel_id: CH,
    data: { thread_id: t.id, quote: t.quote, paragraph: t.paragraph, question, history: t.history.slice() } } });
  t.history.push({ role: "user", text: question });
}

// Lay out cards top to bottom: each at max(mark.offsetTop, previous card's bottom + 10).
// Poll poll_ui_messages every ~1.2 s; on "answer", replace "Thinking…" in that thread and push to history.
```

Escape everything you put into `innerHTML`; questions and answers are user and model text.

## Agent side

Arm the watcher from `recipes:bidirectional-events`, then render. On each wake-up: `poll_agent_messages`, answer every `ask` with `notify_ui("answer", {thread_id, text})`, reply `hello` to `ready`, and arm the watcher again. Answer the question about the quoted passage in 2–4 sentences; the card is narrow.
