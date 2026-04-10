# CLI

`coco` is the command-line tool for CoCo. This page is organized from
"get-up-and-running" to "advanced management" — read from top to bottom if
you're new, or jump to the section you need.

> Not sure what "channels", "heartbeat", or "cron" mean? See
> [Introduction](./intro) first.

---

## Getting started

These are the commands you'll use on day one.

### coco init

First-time setup. Walks you through configuration interactively.

```bash
coco init              # Interactive setup (recommended for first time)
coco init --defaults   # Non-interactive, use all defaults (good for scripts)
coco init --force      # Overwrite existing config files
```

**What the interactive flow covers (in order):**

1. **Default Workspace Initialization** — automatically create default workspace and configuration files.
2. **LLM provider** — select provider, enter API key, choose model
   (**required**).
3. **Environment variables** — optionally add key-value pairs for tools.
4. **HEARTBEAT.md** — edit the heartbeat checklist in your default editor.

### coco app

Start the CoCo server. Everything else — channels, cron jobs, the Console
UI — depends on this.

```bash
coco app                             # Start on 127.0.0.1:8088
coco app --reload                    # Auto-reload on code change (dev)
coco app --log-level debug           # Verbose logging
```

| Option        | Default     | Description                                                   |
| ------------- | ----------- | ------------------------------------------------------------- |
| `--host`      | `127.0.0.1` | Bind host                                                     |
| `--port`      | `8088`      | Bind port                                                     |
| `--reload`    | off         | Auto-reload on file changes (dev only)                        |
| `--log-level` | `info`      | `critical` / `error` / `warning` / `info` / `debug` / `trace` |
| `--workers`   | —           | **[DEPRECATED]** Ignored. CoCo always uses 1 worker          |

> **Note:** The `--workers` option is deprecated for stability reasons. CoCo is designed to run with a single worker process. Multi-worker mode can cause issues with in-memory state management and WebSocket connections. This option will be removed in a future version.

### Console

Once `coco app` is running, open `http://127.0.0.1:8088/` in your browser to
access the **Console** — a web UI for chat, channels, cron, skills, models,
and more. See [Console](./console) for a full walkthrough.

If the frontend was not built, the root URL returns a JSON message like `{"message": "CoCo Web Console is not available."}` but the API still works.

**To build the frontend:** in the project's `console/` directory run
`npm ci && npm run build`, then copy the output to the package directory:
`mkdir -p src/coco/console && cp -R console/dist/. src/coco/console/`.
Docker images and pip packages already include the Console.

### coco daemon

Inspect status, version, and recent logs without starting a conversation. Same
behavior as sending `/daemon status` etc. in chat (CLI can show local info when
the app is not running).

| Command                      | Description                                                                               |
| ---------------------------- | ----------------------------------------------------------------------------------------- |
| `coco daemon status`        | Status (config, working dir, memory manager)                                              |
| `coco daemon restart`       | Print instructions (in-chat /daemon restart does in-process reload)                       |
| `coco daemon reload-config` | Re-read and validate config (channel/MCP changes need /daemon restart or process restart) |
| `coco daemon version`       | Version and paths                                                                         |
| `coco daemon logs [-n N]`   | Last N lines of log (default 100; from `coco.log` in working dir)                        |

**Multi-Agent Support:** All commands support the `--agent-id` parameter (defaults to `default`).

```bash
coco daemon status                     # Default agent status
coco daemon status --agent-id abc123   # Specific agent status
coco daemon version
coco daemon logs -n 50
```

---

## Models & environment variables

Before using CoCo you need at least one LLM provider configured. Environment
variables power many built-in tools (e.g. web search).

### coco models

Manage LLM providers and the active model.

| Command                                | What it does                                         |
| -------------------------------------- | ---------------------------------------------------- |
| `coco models list`                    | Show all providers, API key status, and active model |
| `coco models config`                  | Full interactive setup: API keys → active model      |
| `coco models config-key [provider]`   | Configure a single provider's API key                |
| `coco models set-llm`                 | Switch the active model (API keys unchanged)         |
| `coco models download <repo_id>`      | Download a local model (llama.cpp)                   |
| `coco models local`                   | List downloaded local models                         |
| `coco models remove-local <model_id>` | Delete a downloaded local model                      |

```bash
coco models list                    # See what's configured
coco models config                  # Full interactive setup
coco models config-key modelscope   # Just set ModelScope's API key
coco models config-key dashscope    # Just set DashScope's API key
coco models config-key custom       # Set custom provider (Base URL + key)
coco models set-llm                 # Change active model only
```

#### Local models

CoCo can also run models locally via llama.cpp, Ollama, or LM Studio — no API key needed.
But you need to download the corresponding application first, such as [Ollama](https://ollama.com/download) or [LM Studio](https://lmstudio.ai/download).

```bash
# Download a model (auto-selects Q4_K_M GGUF)
coco models download Qwen/Qwen3-4B-GGUF

# Download from ModelScope
coco models download Qwen/Qwen2-0.5B-Instruct-GGUF --source modelscope

# List downloaded models
coco models local

# Delete a downloaded model
coco models remove-local <model_id>
coco models remove-local <model_id> --yes   # skip confirmation
```

| Option     | Short | Default       | Description                                                           |
| ---------- | ----- | ------------- | --------------------------------------------------------------------- |
| `--source` | `-s`  | `huggingface` | Download source (`huggingface` or `modelscope`)                       |
| `--file`   | `-f`  | _(auto)_      | Specific filename. If omitted, auto-selects (prefers Q4_K_M for GGUF) |

#### Ollama models

CoCo integrates with Ollama to run models locally. Models are dynamically loaded from your Ollama daemon — install Ollama first from [ollama.com](https://ollama.com).

Install the Ollama SDK: `pip install 'coco[ollama]'` (or re-run the installer with `--extras ollama`)

```bash
# Download an Ollama model
ollama pull mistral:7b
ollama pull qwen3:8b

# List Ollama models
ollama list

# Remove an Ollama model
ollama rm mistral:7b

# Use in config flow (auto-detects Ollama models)
coco models config           # Select Ollama → Choose from model list
coco models set-llm          # Switch to a different Ollama model
```

**Key differences from local models:**

- Models come from Ollama daemon (not downloaded by CoCo)
- Use `ollama` CLI to manage models (not `coco models download/remove-local`)
- Model list updates dynamically when you add/remove via Ollama CLI or CoCo

> **Note:** You are responsible for ensuring the API key is valid. CoCo does
> not verify key correctness. See [Config — LLM Providers](./config#llm-providers).

### coco env

Manage environment variables used by tools and skills at runtime.

| Command                   | What it does                  |
| ------------------------- | ----------------------------- |
| `coco env list`          | List all configured variables |
| `coco env set KEY VALUE` | Set or update a variable      |
| `coco env delete KEY`    | Delete a variable             |

```bash
coco env list
coco env set TAVILY_API_KEY "tvly-xxxxxxxx"
coco env set GITHUB_TOKEN "ghp_xxxxxxxx"
coco env delete TAVILY_API_KEY
```

> **Note:** CoCo only stores and loads these values; you are responsible for
> ensuring they are correct. See
> [Config — Environment Variables](./config#environment-variables).

---

## Channels

Connect CoCo to messaging platforms.

### coco channels

Manage channel configuration (iMessage, Discord, DingTalk, Feishu, QQ,
Console, etc.) and send messages to channels. **Note:** Use `config` for interactive setup (no `configure`
subcommand); use `remove` to uninstall custom channels (no `uninstall`).

**Alias:** You can use `coco channel` (singular) as a shorthand for `coco channels`.

| Command                        | What it does                                                                                                      |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `coco channels list`          | Show all channels and their status (secrets masked)                                                               |
| `coco channels send`          | Send a one-way message to a user/session via a channel (requires all 5 parameters)                                |
| `coco channels install <key>` | Install a channel into `custom_channels/`: create stub or use `--path`/`--url`                                    |
| `coco channels add <key>`     | Install and add to config; built-in channels only get config entry; supports `--path`/`--url`                     |
| `coco channels remove <key>`  | Remove a custom channel from `custom_channels/` (built-ins cannot be removed); `--keep-config` keeps config entry |
| `coco channels config`        | Interactively enable/disable channels and fill in credentials                                                     |

**Multi-Agent Support:** All commands support the `--agent-id` parameter (defaults to `default`).

```bash
coco channels list                    # See default agent's channels
coco channels list --agent-id abc123  # See specific agent's channels
coco channels install my_channel      # Create custom channel stub
coco channels install my_channel --path ./my_channel.py
coco channels add dingtalk            # Add DingTalk to config
coco channels remove my_channel       # Remove custom channel (and from config by default)
coco channels remove my_channel --keep-config   # Remove module only, keep config entry
coco channels config                  # Configure default agent
coco channels config --agent-id abc123 # Configure specific agent
```

The interactive `config` flow lets you pick a channel, enable/disable it, and enter credentials. It loops until you choose "Save and exit".

| Channel      | Fields to fill in                                                                    |
| ------------ | ------------------------------------------------------------------------------------ |
| **iMessage** | Bot prefix, database path, poll interval                                             |
| **Discord**  | Bot prefix, Bot Token, HTTP proxy, proxy auth                                        |
| **DingTalk** | Bot prefix, Client ID, Client Secret, Message Type, Card Template ID/Key, Robot Code |
| **Feishu**   | Bot prefix, App ID, App Secret                                                       |
| **QQ**       | Bot prefix, App ID, Client Secret                                                    |
| **Console**  | Bot prefix                                                                           |

> For platform-specific credential setup, see [Channels](./channels).

#### Sending messages to channels (Proactive Notifications)

> Corresponding skill: **Channel Message**

Use `coco channels send` to proactively push messages to users/sessions via any configured channel. This is a **one-way send** — no response expected.

When agents have the **channel_message** skill enabled, they can automatically use this command to send proactive notifications when needed.

**Typical use cases:**

- Notify user after task completion
- Scheduled reminders, alerts, status updates
- Push async processing results back to original session
- User explicitly requested "notify me when done"

```bash
# Step 1: Query available sessions
coco chats list --agent-id my_bot --channel feishu

# Step 2: Send message using queried parameters
coco channels send \
  --agent-id my_bot \
  --channel feishu \
  --target-user ou_xxxx \
  --target-session session_id_xxxx \
  --text "Task completed!"
```

**Required parameters (all 5):**

- `--agent-id`: Sending agent ID
- `--channel`: Target channel (console/dingtalk/feishu/discord/imessage/qq)
- `--target-user`: User ID (get from `coco chats list`)
- `--target-session`: Session ID (get from `coco chats list`)
- `--text`: Message content

**Important:**

- Always query sessions with `coco chats list` first — do NOT guess `target-user` or `target-session`
- If multiple sessions exist, prefer the most recently updated one
- This is for proactive notifications only; for agent-to-agent communication, use `coco agents chat` (see "Agents" section below)

**Key differences from `coco agents chat`:**

- `coco channels send`: Agent-to-user/channel, one-way, no response
- `coco agents chat`: Agent-to-agent, bidirectional, with response

---

## Agents

Manage agents and enable inter-agent communication.

### coco agents

> Corresponding skill: **Multi-Agent Collaboration**

When agents have the **multi_agent_collaboration** skill enabled, they can automatically use `coco agents chat` to collaborate with other agents as needed.

**Alias:** You can use `coco agent` (singular) as a shorthand for `coco agents`.

| Command             | What it does                                                                 |
| ------------------- | ---------------------------------------------------------------------------- |
| `coco agents list` | List all configured agents with their IDs, names, descriptions, workspaces   |
| `coco agents chat` | Communicate with another agent (bidirectional, supports multi-turn dialogue) |

```bash
# List all agents
coco agents list
coco agent list  # Same with singular alias

# Chat with another agent (real-time mode, one-shot)
coco agents chat \
  --agent-id my_bot \
  --to-agent helper_bot \
  --text "Please analyze this data"

# Multi-turn conversation (session reuse)
coco agents chat \
  --agent-id my_bot \
  --to-agent helper_bot \
  --session-id collab_session_001 \
  --text "Follow-up question"

# Complex task (background mode)
coco agents chat --background \
  --agent-id my_bot \
  --to-agent data_analyst \
  --text "Analyze /data/logs/2026-03-26.log and generate detailed report"
# Returns [TASK_ID: xxx] [SESSION: xxx]

# Check background task status (--to-agent is optional when querying)
coco agents chat --background \
  --task-id <task_id>
# Status flow: submitted → pending → running → finished
# When finished, result shows: completed (✅) or failed (❌)

# Stream mode (incremental response, real-time mode only)
coco agents chat \
  --agent-id my_bot \
  --to-agent helper_bot \
  --text "Long analysis task" \
  --mode stream
```

**Required parameters (real-time mode):**

- `--from-agent` (alias: `--agent-id`): Your agent ID (sender)
- `--to-agent`: Target agent ID (recipient)
- `--text`: Message content

**Background task parameters (new):**

- `--background`: Background task mode
- `--task-id`: Check background task status (use with `--background`)

**Optional parameters:**

- `--session-id`: Session ID for multi-turn conversations (auto-generated if omitted)
- `--mode`: Response mode — `final` (default, complete response) or `stream` (incremental)
  - **Note**: `--background` and `--mode stream` are mutually exclusive
- `--base-url`: Override API base URL
- `--timeout`: Timeout in seconds (default: 300)
- `--json-output`: Output full JSON instead of text

**Background mode explanation:**

When tasks are complex (e.g., data analysis, batch processing, report generation), use `--background` to avoid blocking the current agent. After submission, it returns a `task_id` that can be used later to query the task status and result.

**Use cases for background mode**:

- Data analysis and statistics
- Batch file processing
- Generating detailed reports
- Calling slow external APIs
- Complex tasks with uncertain execution time

**Task Status Flow**:

- `submitted`: Task accepted, waiting to start
- `pending`: Queued for execution
- `running`: Currently executing
- `finished`: Completed (result shows `completed` for success or `failed` for error)

**Note:** You can use either `--from-agent` or `--agent-id` — they are equivalent. When checking task status, only `--task-id` is required (`--to-agent` is optional).

**Key differences from `coco channels send`:**

- `coco agents chat`: Agent-to-agent, bidirectional, returns response
- `coco channels send`: Agent-to-user/channel, one-way, no response

---

## Cron (scheduled tasks)

Create jobs that run on a timed schedule — "every day at 9am", "every 2 hours
ask CoCo and send the reply". **Requires `coco app` to be running.**

### coco cron

| Command                      | What it does                                  |
| ---------------------------- | --------------------------------------------- |
| `coco cron list`            | List all jobs                                 |
| `coco cron get <job_id>`    | Show a job's spec                             |
| `coco cron state <job_id>`  | Show runtime state (next run, last run, etc.) |
| `coco cron create ...`      | Create a job                                  |
| `coco cron delete <job_id>` | Delete a job                                  |
| `coco cron pause <job_id>`  | Pause a job                                   |
| `coco cron resume <job_id>` | Resume a paused job                           |
| `coco cron run <job_id>`    | Run once immediately                          |

**Multi-Agent Support:** All commands support the `--agent-id` parameter (defaults to `default`).

### Creating jobs

**Option 1 — CLI arguments (simple jobs)**

Two task types:

- **text** — send a fixed message to a channel on schedule.
- **agent** — ask CoCo a question on schedule and deliver the reply.

```bash
# Text: send "Good morning!" to DingTalk every day at 9:00 (default agent)
coco cron create \
  --type text \
  --name "Daily 9am" \
  --cron "0 9 * * *" \
  --channel dingtalk \
  --target-user "your_user_id" \
  --target-session "session_id" \
  --text "Good morning!"

# Agent: create task for specific agent
coco cron create \
  --agent-id abc123 \
  --type agent \
  --name "Check todos" \
  --cron "0 */2 * * *" \
  --channel dingtalk \
  --target-user "your_user_id" \
  --target-session "session_id" \
  --text "What are my todo items?"
```

Required: `--type`, `--name`, `--cron`, `--channel`, `--target-user`,
`--target-session`, `--text`.

**Option 2 — JSON file (complex or batch)**

```bash
coco cron create -f job_spec.json
```

JSON structure matches the output of `coco cron get <job_id>`.

### Additional options

| Option                       | Default       | Description                                                              |
| ---------------------------- | ------------- | ------------------------------------------------------------------------ |
| `--timezone`                 | user timezone | Timezone for the cron schedule (defaults to `user_timezone` from config) |
| `--enabled` / `--no-enabled` | enabled       | Create enabled or disabled                                               |
| `--mode`                     | `final`       | `stream` (incremental) or `final` (complete response)                    |
| `--base-url`                 | auto          | Override the API base URL                                                |

### Cron expression cheat sheet

Five fields: **minute hour day month weekday** (no seconds).

| Expression     | Meaning                   |
| -------------- | ------------------------- |
| `0 9 * * *`    | Every day at 9:00         |
| `0 */2 * * *`  | Every 2 hours on the hour |
| `30 8 * * 1-5` | Weekdays at 8:30          |
| `0 0 * * 0`    | Sunday at midnight        |
| `*/15 * * * *` | Every 15 minutes          |

---

## Chats (sessions)

Manage chat sessions via the API. **Requires `coco app` to be running.**

### coco chats

**Alias:** You can use `coco chat` (singular) as a shorthand for `coco chats`.

| Command                                | What it does                                                  |
| -------------------------------------- | ------------------------------------------------------------- |
| `coco chats list`                     | List all sessions (supports `--user-id`, `--channel` filters) |
| `coco chats get <id>`                 | View a session's details and message history                  |
| `coco chats create ...`               | Create a new session                                          |
| `coco chats update <id> --name "..."` | Rename a session                                              |
| `coco chats delete <id>`              | Delete a session                                              |

**Multi-Agent Support:** All commands support the `--agent-id` parameter (defaults to `default`).

```bash
coco chats list                        # Default agent's chats
coco chats list --agent-id abc123      # Specific agent's chats
coco chats list --user-id alice --channel dingtalk
coco chats get 823845fe-dd13-43c2-ab8b-d05870602fd8
coco chats create --session-id "discord:alice" --user-id alice --name "My Chat"
coco chats create --agent-id abc123 -f chat.json
coco chats update <chat_id> --name "Renamed"
coco chats delete <chat_id>
```

---

## Skills

Extend CoCo's capabilities with skills (PDF reading, web search, etc.).

### coco skills

| Command               | What it does                                      |
| --------------------- | ------------------------------------------------- |
| `coco skills list`   | Show all skills and their enabled/disabled status |
| `coco skills config` | Interactively enable/disable skills (checkbox UI) |

**Multi-Agent Support:** All commands support the `--agent-id` parameter (defaults to `default`).

```bash
coco skills list                   # See default agent's skills
coco skills list --agent-id abc123 # See specific agent's skills
coco skills config                 # Configure default agent
coco skills config --agent-id abc123 # Configure specific agent
```

In the interactive UI: ↑/↓ to navigate, Space to toggle, Enter to confirm.
A preview of changes is shown before applying.

> For built-in skill details and custom skill authoring, see [Skills](./skills).

---

## Maintenance

### coco clean

Remove everything under the working directory (default `~/.coco`).

```bash
coco clean             # Interactive confirmation
coco clean --yes       # No confirmation
coco clean --dry-run   # Only list what would be removed
```

---

## Global options

Every `coco` subcommand inherits:

| Option          | Default     | Description                                    |
| --------------- | ----------- | ---------------------------------------------- |
| `--host`        | `127.0.0.1` | API host (auto-detected from last `coco app`) |
| `--port`        | `8088`      | API port (auto-detected from last `coco app`) |
| `-h` / `--help` |             | Show help message                              |

If the server runs on a non-default address, pass these globally:

```bash
coco --host 0.0.0.0 --port 9090 cron list
```

## Working directory

All config and data live in `~/.coco` by default:

- **Global config**: `config.json` (providers, environment variables, agent list)
- **Agent workspaces**: `workspaces/{agent_id}/` (each agent's independent config and data)

```
~/.coco/
├── config.json              # Global config
└── workspaces/
    ├── default/             # Default agent workspace
    │   ├── agent.json       # Agent config
    │   ├── chats.json       # Conversation history
    │   ├── jobs.json        # Cron jobs
    │   ├── AGENTS.md        # Persona files
    │   └── memory/          # Memory files
    └── abc123/              # Other agent workspace
        └── ...
```

| Variable            | Description                         |
| ------------------- | ----------------------------------- |
| `COCO_WORKING_DIR` | Override the working directory path |
| `COCO_CONFIG_FILE` | Override the config file path       |

See [Config & Working Directory](./config) and [Multi-Agent](./multi-agent) for full details.

---

## Command overview

| Command          | Subcommands                                                                          | Requires server? |
| ---------------- | ------------------------------------------------------------------------------------ | :--------------: |
| `coco init`     | —                                                                                    |        No        |
| `coco app`      | —                                                                                    |  — (starts it)   |
| `coco models`   | `list` · `config` · `config-key` · `set-llm` · `download` · `local` · `remove-local` |        No        |
| `coco env`      | `list` · `set` · `delete`                                                            |        No        |
| `coco channels` | `list` · `send` · `install` · `add` · `remove` · `config`                            |     **Yes**      |
| `coco agents`   | `list` · `chat`                                                                      |     **Yes**      |
| `coco cron`     | `list` · `get` · `state` · `create` · `delete` · `pause` · `resume` · `run`          |     **Yes**      |
| `coco chats`    | `list` · `get` · `create` · `update` · `delete`                                      |     **Yes**      |
| `coco skills`   | `list` · `config`                                                                    |        No        |
| `coco clean`    | —                                                                                    |        No        |

---

## Related pages

- [Introduction](./intro) — What CoCo can do
- [Console](./console) — Web-based management UI
- [Channels](./channels) — DingTalk, Feishu, iMessage, Discord, QQ setup
- [Heartbeat](./heartbeat) — Scheduled check-in / digest
- [Skills](./skills) — Built-in and custom skills
- [Config & Working Directory](./config) — Working directory and config.json
- [Multi-Agent](./multi-agent) — Multi-agent setup, management, and collaboration
