# ai_watcher

YAML-defined **DAG workflows** for orchestrating shell commands, Python scripts, the **GitHub Copilot SDK** (`github-copilot-sdk`), and **external agent CLIs** (for example `gh` subcommands, Codex, Claude Code). The MVP expects repositories to be **already cloned** in the directory where you run the tool, and takes a **prompt string** and/or **markdown file** as task context.

## Install

From this directory:

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

The console entry point is `ai-watcher`.

## Quick start

```bash
ai-watcher run \
  --workflow examples/sample_workflow.yaml \
  --prompt-file examples/prompt.md \
  --dry-run
```

Remove `--dry-run` to execute. You must pass a non-empty prompt (via `--prompt` and/or `--prompt-file`) unless you only use `--dry-run`.

### Example: Python file tree + Copilot summaries

[`examples/python_inventory_workflow.yaml`](examples/python_inventory_workflow.yaml) scans for `*.py` files (excluding `.venv/` and `.git/`), runs **Copilot SDK** only when the count is greater than zero, asks for tab-separated one-line summaries written to `artifacts/file_summaries.txt`, then runs [`examples/scripts/build_python_report.py`](examples/scripts/build_python_report.py) to produce `artifacts/REPORT.md`. Run from the `ai_watcher/` directory (or adjust the `script` `path:`) so the helper script resolves.

### CLI overview

| Option | Meaning |
|--------|---------|
| `--workflow` / `-w` | Path to workflow YAML (required) |
| `--prompt` / `-p` | Inline prompt text |
| `--prompt-file` / `-f` | File whose contents are appended to the prompt |
| `--cwd` | Override working directory (default: current directory) |
| `--dry-run` | Validate the graph and print execution order only |
| `-v` / `--verbose` | Log each step name and exit code to stderr (executor log) |
| `--debug` | Like `--verbose`, and print **full** captured stdout/stderr for every step to stderr |
| `--stream-copilot` | Capture streaming Copilot SDK deltas into step stdout |
| `--model` / `-m` | Override the Copilot model for every `copilot_sdk` step (e.g. `claude-haiku-4.5`) |

After a normal run, the CLI prints a short **summary on stdout** (workflow name, exit code, cwd, each step’s status, and a **preview** of captured stdout up to ~4KB per step). Large outputs point you at `--debug`.

## Workflow YAML (version 1)

- Top-level keys: `version: 1` and `workflow` with `name` and `steps`.
- Each **step** has `id`, `type`, optional `depends_on`, `retries`, `retry_backoff_seconds`, `continue_on_error`, `only_if`, `output`, `timeout_seconds`.
- **Types**: `command`, `script`, `copilot_sdk`, `external_cli`, `repeat`.

### Templates

Strings support `{{ variable }}` with dotted paths, for example:

- `{{ cwd }}`, `{{ prompt }}`, `{{ prompt_path }}`
- `{{ steps.some_step_id.stdout }}` — nested keys for repeat inner steps, e.g. `{{ steps.my_repeat.inner_id.stdout }}`

### `repeat`

A `repeat` step runs its **inner** DAG up to `max_iterations` times until `until` is satisfied:

| `until` | Stops successfully when |
|---------|-------------------------|
| `all_success` | Every non-skipped inner step in the iteration exited with code 0 |
| `any_success` | At least one non-skipped inner step exited with 0 |
| `last_exit_success` | The last inner step in topological order that ran exited with 0 |

Nested `repeat` blocks are **not** supported in v1.

### `only_if`

```yaml
only_if:
  file_exists: "{{ cwd }}/pyproject.toml"
```

If the path does not exist after template expansion, the step is **skipped** (exit code 0, marked skipped).

### `copilot_sdk`

Requires a working Copilot CLI / SDK environment (see GitHub Copilot SDK docs). Sessions use `PermissionHandler.approve_all` so file tools can run without blocking.

The **`model`** field defaults to **`claude-haiku-4.5`** (fast/cheap). Use ids such as `claude-sonnet-4.5` that match `copilot help` / your CLI. Override for the whole run with **`ai-watcher run ... -m claude-sonnet-4.5`**.

Example fields:

```yaml
- id: ask
  type: copilot_sdk
  prompt: "Summarize the repo at {{ cwd }}"
  model: claude-haiku-4.5
  skill_directories: ["./skills"]
  tools_module: mypackage.copilot_tools
  tools_export: TOOLS
```

The Python module `tools_module` must expose a list attribute `tools_export` (default name `TOOLS`) of `@define_tool` functions.

### `external_cli`

Runs a single executable name resolvable on `PATH` plus arguments (no shell):

```yaml
- id: codex
  type: external_cli
  command: codex
  args: ["--help"]
```

## Documentation

- [Architecture and extension points](docs/ARCHITECTURE.md)

## Tests

```bash
pytest
```

## License

Add your license here.
