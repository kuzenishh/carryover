# carryover

Your coding agent forgets everything the second the session ends.

Every correction. Every dead end you already hit. Every "no, not like that."
Gone. Tomorrow you teach it all over again.

`carryover` keeps that stuff. One file, no dependencies.

```
$ carryover brief

# Project memory

## Rules (learned the hard way)
- never use flask here, the project is FastAPI
- don't touch the migrations folder
- the VPS only has 1GB ram, no docker builds on it

## Dead ends (already tried, did not work)
- we already tried polling the websocket, it drops every 40 minutes

## Decisions (settled, do not relitigate)
- we're going with redis pubsub for this
```

That block goes into your next session. The agent starts where you left off
instead of at zero.

## Install

```bash
curl -O https://raw.githubusercontent.com/kuzenishh/carryover/mainddd/carryover.py
chmod +x carryover.py
```

Python 3.8+. No packages to install, nothing to configure.

## Use

```bash
python3 carryover.py init                  # set up in the current project
python3 carryover.py learn session.jsonl   # pull lessons out of a past session
python3 carryover.py add "never run migrations by hand"
python3 carryover.py brief                 # print the memory block
python3 carryover.py list                  # numbered list
python3 carryover.py forget 3              # drop one
```

`init` also drops a pointer into `CLAUDE.md`, so the agent reads the memory
itself at the start of a session.

## How learn works

It reads the human turns of a session and keeps the ones that sound like you
correcting the agent:

| you typed | kept as |
|---|---|
| "no, not like that" / "never use X" / "don't touch Y" | rule |
| "we already tried that" / "that didn't work" | dead end |
| "we're going with X" / "use Y instead" | decision |

Takes `.jsonl` session logs, or a plain text file you pasted the session into.
Every candidate is shown before it's kept, unless you pass `-y`.

Duplicates aren't stored twice. A lesson you hit repeatedly gets a hit counter,
and the ones you keep hitting float to the top of the brief.

## What it doesn't do

No daemon. No API keys. No cloud. No vector database. It's a JSON file in
`.carryover/` that you can read, edit and commit.

This is deliberately small. If it needs a config file, it's failed.

## Why

I build with AI and I'm not a strong programmer. Which means I hit the same
wall constantly: teaching an agent a project rule on Monday and teaching it
again on Tuesday. The fix turned out to be 250 lines.

## License

MIT
