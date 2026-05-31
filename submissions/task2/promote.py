"""scripts/promote.py — promote MLflow Registry aliases with an audit log.

YOUR TASK (see tasks/task2.md): implement the four subcommand functions.
The argparse scaffolding below is wired so each cmd_* receives an `args`
namespace already parsed. See `_build_parser` for what's on `args` per
subcommand, and tasks/task2.md "Behavioral specs" for what each function
must do.

Versions are identified by their `config_id` tag (e.g., "v6"), NOT by
MLflow's integer version numbers. If the config_id matches multiple
registered versions, the CLI warns and uses the highest MLflow version.

Successful `set` and `rollback` operations append a JSON event to
LOG_FILE (promotion-log.jsonl at repo root). `rollback` consults the
log to find the previous alias target.

Subcommands:
  set <alias> <config_id>   move alias, append `set` event to the log
  show <alias>              print current target + tags + key metrics
  list                      print all aliases on the registered model
  rollback <alias>          move alias back per the audit log, append
                            `rollback` event
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from src.config import get_settings

REGISTERED_MODEL_NAME = "travel-assistant"
LOG_FILE = Path(__file__).resolve().parent.parent / "promotion-log.jsonl"


def _client() -> MlflowClient:
    # ANSWER Task 2 - configures the CLI to talk to the same MLflow server as the app.
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient()


def _tag(mv, key: str, default: str = "") -> str:
    # ANSWER Task 2 - reads ModelVersion tags defensively across MLflow object shapes.
    return str((getattr(mv, "tags", None) or {}).get(key, default))


def _resolve_config_version(client: MlflowClient, name: str, config_id: str):
    # ANSWER Task 2 - finds the latest registered model version tagged with config_id.
    filter_strings = (
        f"name = '{name}' AND tags.config_id = '{config_id}'",
        f"name = '{name}' AND tag.config_id = '{config_id}'",
    )
    matches = []
    last_error: MlflowException | None = None
    for filter_string in filter_strings:
        try:
            matches = list(client.search_model_versions(filter_string))
            break
        except MlflowException as exc:
            last_error = exc
    else:
        if last_error is not None:
            print(f"error: failed to search model versions: {last_error}", file=sys.stderr)
            sys.exit(1)
    if not matches:
        print(f"error: no version found with config_id={config_id}", file=sys.stderr)
        sys.exit(1)

    matches.sort(key=lambda mv: int(mv.version))
    if len(matches) > 1:
        versions = [int(mv.version) for mv in matches]
        print(
            f"warning: multiple versions match config_id={config_id} "
            f"(MLflow versions {versions}); using latest ({versions[-1]})"
        )
    return matches[-1]


def _alias_target(client: MlflowClient, name: str, alias: str):
    # ANSWER Task 2 - resolves an alias and treats missing aliases as unset.
    try:
        return client.get_model_version_by_alias(name=name, alias=alias)
    except MlflowException:
        return None


def _config_id(mv) -> str:
    # ANSWER Task 2 - normalizes missing config_id tags to the empty string.
    return _tag(mv, "config_id", "")


def _append_log(alias: str, from_config: str, to_config: str, op: str) -> None:
    # ANSWER Task 2 - persists a line-delimited JSON audit event for promotion history.
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "alias": alias,
        "from": from_config,
        "to": to_config,
        "op": op,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def _read_log() -> list[dict]:
    # ANSWER Task 2 - handles the first-run case where the audit log does not exist yet.
    if not LOG_FILE.exists():
        return []
    events: list[dict] = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def cmd_set(args: argparse.Namespace) -> None:
    """args.alias: str, args.config_id: str. See tasks/task2.md → cmd_set."""
    # ANSWER Task 2 - moves an alias to a config_id-resolved version and logs the change.
    client = _client()
    target = _resolve_config_version(client, args.name, args.config_id)
    current = _alias_target(client, args.name, args.alias)
    current_config = _config_id(current) if current is not None else ""

    client.set_registered_model_alias(
        name=args.name,
        alias=args.alias,
        version=target.version,
    )
    _append_log(args.alias, current_config, args.config_id, "set")

    shown_current = current_config or "(unset)"
    print(f"{args.alias}: {shown_current} -> {args.config_id}")


def cmd_show(args: argparse.Namespace) -> None:
    """args.alias: str. See tasks/task2.md → cmd_show."""
    # ANSWER Task 2 - prints the current alias target, its registry tags, and run metrics.
    client = _client()
    mv = _alias_target(client, args.name, args.alias)
    if mv is None:
        print(f"error: alias {args.alias} is unset", file=sys.stderr)
        sys.exit(1)

    tags = getattr(mv, "tags", None) or {}
    metrics = client.get_run(mv.run_id).data.metrics if mv.run_id else {}

    print(f"{args.name} @ {args.alias}")
    print(f"  mlflow_version: {mv.version}")
    print(f"  config_id: {_config_id(mv)}")
    for key in sorted(k for k in tags if k != "config_id"):
        print(f"  {key}: {tags[key]}")

    for key in ("accuracy_overall", "verdict_rate_leaked", "total_cost_usd"):
        if key in metrics:
            value = metrics[key]
            if key == "total_cost_usd":
                print(f"  {key}: ${value:.4f}")
            else:
                print(f"  {key}: {value:.4f}")


def cmd_list(args: argparse.Namespace) -> None:
    """No args. See tasks/task2.md → cmd_list."""
    # ANSWER Task 2 - lists every model alias and the config_id it currently points to.
    client = _client()
    try:
        model = client.get_registered_model(args.name)
    except MlflowException:
        print("no aliases set")
        return

    aliases = getattr(model, "aliases", None) or {}
    if not aliases:
        print("no aliases set")
        return

    for alias in sorted(aliases):
        mv = client.get_model_version(name=args.name, version=aliases[alias])
        print(f"{alias} -> {_config_id(mv)}")


def cmd_rollback(args: argparse.Namespace) -> None:
    """args.alias: str. See tasks/task2.md → cmd_rollback."""
    # ANSWER Task 2 - rolls an alias back one step using the promotion audit log.
    client = _client()
    current = _alias_target(client, args.name, args.alias)
    if current is None:
        print("error: nothing to roll back", file=sys.stderr)
        sys.exit(1)
    current_config = _config_id(current)

    last_event = next(
        (event for event in reversed(_read_log()) if event.get("alias") == args.alias),
        None,
    )
    if last_event is None:
        print(f"error: no promotion history for alias {args.alias}", file=sys.stderr)
        sys.exit(1)
    if last_event.get("op") == "rollback":
        print(
            f"error: {args.alias} was just rolled back; no further history to walk back to",
            file=sys.stderr,
        )
        sys.exit(1)

    previous_config = str(last_event.get("from") or "")
    if not previous_config:
        print(
            f"error: {args.alias} has no previous target (first promotion ever)",
            file=sys.stderr,
        )
        sys.exit(1)

    target = _resolve_config_version(client, args.name, previous_config)
    client.set_registered_model_alias(
        name=args.name,
        alias=args.alias,
        version=target.version,
    )
    _append_log(args.alias, current_config, previous_config, "rollback")
    print(f"{args.alias}: {current_config} -> {previous_config} (rolled back)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--name",
        default=REGISTERED_MODEL_NAME,
        help=f"Registered model name (default: {REGISTERED_MODEL_NAME})",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser(
        "set", help="Move an alias to a version (by config_id), append a set event"
    )
    p_set.add_argument("alias", help="Alias to assign (e.g., 'production')")
    p_set.add_argument(
        "config_id",
        help="Config identifier (e.g., 'v6') — resolved via the config_id tag on registered versions",
    )
    p_set.set_defaults(func=cmd_set)

    p_show = sub.add_parser("show", help="Show which version an alias points at")
    p_show.add_argument("alias")
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser("list", help="List all aliases on the registered model")
    p_list.set_defaults(func=cmd_list)

    p_rollback = sub.add_parser(
        "rollback",
        help="Move an alias back to its previous target per the audit log",
    )
    p_rollback.add_argument("alias")
    p_rollback.set_defaults(func=cmd_rollback)

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    try:
        args.func(args)
    except NotImplementedError as exc:
        print(f"NOT IMPLEMENTED: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
