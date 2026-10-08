---
description: Pitfalls when using graph_query (Grafeo). Read before large or bulk queries — oversized statements crash the whole server, and indexes do not persist between calls.
---

# graph_query pitfalls

**Oversized statements crash the server.** Long `OR`/`AND` chains (thousands of terms) overflow the stack and kill the server process — no error is returned, every lustereczko tool stops responding. Pass data as lists instead:

```
MATCH (p:Person) WHERE p.id IN [1, 2, 3, ...] RETURN p          -- not p.id = 1 OR p.id = 2 OR ...
UNWIND [{id: 1, name: "A"}, ...] AS r INSERT (:Person {id: r.id, name: r.name})
```

Keep any single statement under ~50 KB; split bigger loads into several calls.

**Indexes do not survive between calls.** Each call reopens the database, and vector/text/property indexes are lost on reopen. Don't rely on an index created in an earlier call.
