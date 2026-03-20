"""Round-robin arena for saved Fire Station models."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .runtime import discover_saved_policies, load_saved_policy
from .selfplay import run_match


@dataclass
class ArenaConfig:
    hands: int = 80
    repeats: int = 2
    bet_set: Tuple[int, ...] = (10, 25)
    stack_set: Tuple[int, ...] = (800, 1000, 1400)
    workers: int = 0
    seed: int = 7
    output_dir: str = "fire_station_ai/runs"
    top: int = 0
    models: Tuple[str, ...] = ()


def parse_int_tuple(text: str) -> Tuple[int, ...]:
    values = []
    for item in str(text).split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        raise ValueError("parameter set cannot be empty")
    return tuple(dict.fromkeys(values))


def _auto_worker_count(configured_workers: int, task_count: int) -> int:
    if task_count <= 1:
        return 1
    if configured_workers > 0:
        return min(configured_workers, task_count)
    cpu_count = os.cpu_count() or 1
    return max(1, min(task_count, cpu_count - 1 if cpu_count > 2 else cpu_count))


def _select_models(discovered: Sequence[Dict[str, Any]], filters: Sequence[str], top: int) -> List[Dict[str, Any]]:
    if filters:
        selected: List[Dict[str, Any]] = []
        seen_paths = set()
        for raw_filter in filters:
            token = raw_filter.strip().lower()
            if not token:
                continue
            for item in discovered:
                candidates = [
                    str(item.get("codename", "")).lower(),
                    os.path.basename(str(item.get("run_dir", ""))).lower(),
                    os.path.basename(str(item.get("path", ""))).lower(),
                    str(item.get("path", "")).lower(),
                ]
                if any(token in candidate for candidate in candidates):
                    normalized_path = os.path.normpath(str(item["path"]))
                    if normalized_path not in seen_paths:
                        selected.append(item)
                        seen_paths.add(normalized_path)
        return selected

    if top > 0:
        return list(discovered[:top])
    return list(discovered)


def _run_arena_matchup(task: Dict[str, Any]) -> Dict[str, Any]:
    model_a = load_saved_policy(task["model_a_path"])
    model_b = load_saved_policy(task["model_b_path"])
    hands = int(task["hands"])
    repeats = int(task["repeats"])
    bet_set = tuple(task["bet_set"])
    stack_set = tuple(task["stack_set"])
    seed_base = int(task["seed_base"])

    bankroll_delta_a = 0
    bankroll_delta_b = 0
    actual_hands_played = 0
    scheduled_hands = 0
    wins_a = 0
    losses_a = 0
    ties = 0
    seat_breakdown: List[Dict[str, Any]] = []

    for bet_index, base_bet in enumerate(bet_set):
        for stack_index, stack in enumerate(stack_set):
            for repeat in range(repeats):
                seed_anchor = seed_base + bet_index * 211 + stack_index * 59 + repeat * 23
                forward = run_match(
                    model_a["policy"],
                    model_b["policy"],
                    hands=hands,
                    base_bet=base_bet,
                    starting_stacks=(stack, stack),
                    seed=seed_anchor,
                )
                reverse = run_match(
                    model_b["policy"],
                    model_a["policy"],
                    hands=hands,
                    base_bet=base_bet,
                    starting_stacks=(stack, stack),
                    seed=seed_anchor + 11,
                )

                delta_a_forward = int(forward.bankroll_delta[0])
                delta_a_reverse = int(reverse.bankroll_delta[1])
                bankroll_delta_a += delta_a_forward + delta_a_reverse
                bankroll_delta_b -= delta_a_forward + delta_a_reverse
                actual_hands_played += int(forward.hands_played + reverse.hands_played)
                scheduled_hands += hands * 2
                wins_a += int(forward.seat0_wins + reverse.seat1_wins)
                losses_a += int(forward.seat1_wins + reverse.seat0_wins)
                ties += int(forward.ties + reverse.ties)

                seat_breakdown.append(
                    {
                        "base_bet": int(base_bet),
                        "stack": int(stack),
                        "repeat": int(repeat),
                        "a_as_player_delta": delta_a_forward,
                        "a_as_opponent_delta": delta_a_reverse,
                        "a_as_player_record": {
                            "wins": int(forward.seat0_wins),
                            "losses": int(forward.seat1_wins),
                            "ties": int(forward.ties),
                            "hands_played": int(forward.hands_played),
                        },
                        "a_as_opponent_record": {
                            "wins": int(reverse.seat1_wins),
                            "losses": int(reverse.seat0_wins),
                            "ties": int(reverse.ties),
                            "hands_played": int(reverse.hands_played),
                        },
                    }
                )

    score_a = bankroll_delta_a / max(scheduled_hands, 1)
    score_b = bankroll_delta_b / max(scheduled_hands, 1)
    if score_a > 1e-9:
        winner = "a"
    elif score_a < -1e-9:
        winner = "b"
    else:
        winner = "draw"

    return {
        "model_a_id": task["model_a_id"],
        "model_b_id": task["model_b_id"],
        "model_a_codename": task["model_a_codename"],
        "model_b_codename": task["model_b_codename"],
        "score_a": score_a,
        "score_b": score_b,
        "bankroll_delta_a": bankroll_delta_a,
        "bankroll_delta_b": bankroll_delta_b,
        "actual_hands_played": actual_hands_played,
        "scheduled_hands": scheduled_hands,
        "wins_a": wins_a,
        "losses_a": losses_a,
        "ties": ties,
        "winner": winner,
        "seat_breakdown": seat_breakdown,
    }


def _build_standings(models: Sequence[Dict[str, Any]], matches: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    standings: Dict[str, Dict[str, Any]] = {}
    for model in models:
        standings[model["id"]] = {
            "id": model["id"],
            "codename": model["codename"],
            "policy_type": model["policy_type"],
            "run_name": model.get("run_name", os.path.basename(str(model["run_dir"]))),
            "run_dir": model["run_dir"],
            "path": model["path"],
            "match_points": 0,
            "match_wins": 0,
            "match_losses": 0,
            "match_draws": 0,
            "bankroll_delta": 0,
            "scheduled_hands": 0,
            "actual_hands_played": 0,
            "hand_wins": 0,
            "hand_losses": 0,
            "hand_ties": 0,
        }

    for match in matches:
        a = standings[match["model_a_id"]]
        b = standings[match["model_b_id"]]

        a["bankroll_delta"] += match["bankroll_delta_a"]
        b["bankroll_delta"] += match["bankroll_delta_b"]
        a["scheduled_hands"] += match["scheduled_hands"]
        b["scheduled_hands"] += match["scheduled_hands"]
        a["actual_hands_played"] += match["actual_hands_played"]
        b["actual_hands_played"] += match["actual_hands_played"]
        a["hand_wins"] += match["wins_a"]
        a["hand_losses"] += match["losses_a"]
        a["hand_ties"] += match["ties"]
        b["hand_wins"] += match["losses_a"]
        b["hand_losses"] += match["wins_a"]
        b["hand_ties"] += match["ties"]

        if match["winner"] == "a":
            a["match_points"] += 3
            a["match_wins"] += 1
            b["match_losses"] += 1
        elif match["winner"] == "b":
            b["match_points"] += 3
            b["match_wins"] += 1
            a["match_losses"] += 1
        else:
            a["match_points"] += 1
            b["match_points"] += 1
            a["match_draws"] += 1
            b["match_draws"] += 1

    table = list(standings.values())
    for row in table:
        row["ev_per_hand"] = row["bankroll_delta"] / max(row["scheduled_hands"], 1)
        hand_total = row["hand_wins"] + row["hand_losses"] + row["hand_ties"]
        row["hand_win_rate"] = row["hand_wins"] / max(hand_total, 1)

    table.sort(
        key=lambda item: (
            item["match_points"],
            item["ev_per_hand"],
            item["hand_win_rate"],
            item["bankroll_delta"],
        ),
        reverse=True,
    )
    for index, row in enumerate(table, start=1):
        row["rank"] = index
    return table


def _write_arena_artifacts(summary: Dict[str, Any], output_dir: str, seed: int, model_count: int) -> Path:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"arena_seed{seed}_models{model_count}"
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = root / f"arena_seed{seed}_models{model_count}_{suffix}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "arena.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="让火烧洋油站训练模型两两对打并生成排行榜")
    parser.add_argument("--hands", type=int, default=80)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--bet-set", type=str, default="10,25")
    parser.add_argument("--stack-set", type=str, default="800,1000,1400")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--models", type=str, default="")
    parser.add_argument("--output-dir", type=str, default="fire_station_ai/runs")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = ArenaConfig(
        hands=args.hands,
        repeats=args.repeats,
        bet_set=parse_int_tuple(args.bet_set),
        stack_set=parse_int_tuple(args.stack_set),
        workers=args.workers,
        seed=args.seed,
        output_dir=args.output_dir,
        top=args.top,
        models=tuple(item.strip() for item in str(args.models).split(",") if item.strip()),
    )

    discovered = discover_saved_policies()
    selected = _select_models(discovered, config.models, config.top)
    if len(selected) < 2:
        raise SystemExit("至少需要 2 个可用模型才能开启 Arena。")

    selected_models: List[Dict[str, Any]] = []
    for index, item in enumerate(selected, start=1):
        selected_models.append(
            {
                "id": f"m{index}",
                "codename": item["codename"],
                "run_name": os.path.basename(str(item["run_dir"])),
                "policy_type": item["policy_type"],
                "run_dir": item["run_dir"],
                "path": item["path"],
                "best_training_score": item["best_training_score"],
                "validation_score": item["validation_score"],
                "validation_win_rate": item["validation_win_rate"],
            }
        )

    tasks = []
    pair_index = 0
    for left in range(len(selected_models)):
        for right in range(left + 1, len(selected_models)):
            pair_index += 1
            model_a = selected_models[left]
            model_b = selected_models[right]
            tasks.append(
                {
                    "model_a_id": model_a["id"],
                    "model_b_id": model_b["id"],
                    "model_a_codename": model_a["codename"],
                    "model_b_codename": model_b["codename"],
                    "model_a_path": model_a["path"],
                    "model_b_path": model_b["path"],
                    "hands": config.hands,
                    "repeats": config.repeats,
                    "bet_set": config.bet_set,
                    "stack_set": config.stack_set,
                    "seed_base": config.seed + pair_index * 1009,
                }
            )

    worker_count = _auto_worker_count(config.workers, len(tasks))
    if worker_count > 1:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            matches = list(executor.map(_run_arena_matchup, tasks))
    else:
        matches = [_run_arena_matchup(task) for task in tasks]

    standings = _build_standings(selected_models, matches)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": asdict(config),
        "model_count": len(selected_models),
        "match_count": len(matches),
        "models": selected_models,
        "standings": standings,
        "matches": matches,
    }
    run_dir = _write_arena_artifacts(summary, config.output_dir, config.seed, len(selected_models))

    print("Fire Station Arena")
    print("=" * 72)
    print(f"模型数量         : {len(selected_models)}")
    print(f"对打场次         : {len(matches)}")
    print(f"底注集合         : {list(config.bet_set)}")
    print(f"筹码集合         : {list(config.stack_set)}")
    print(f"每组计划手数     : {config.hands}")
    print(f"重复次数         : {config.repeats}")
    print(f"结果目录         : {run_dir}")
    print()
    print("排行榜")
    print("-" * 72)
    for row in standings:
        print(
            f"#{row['rank']:>2}  {row['codename']:<12}  "
            f"积分 {row['match_points']:<2}  "
            f"EV/手 {row['ev_per_hand']:>7.3f}  "
            f"手胜率 {row['hand_win_rate'] * 100:>5.1f}%  "
            f"{row['match_wins']}W {row['match_losses']}L {row['match_draws']}D  "
            f"{row['run_name']}"
        )


if __name__ == "__main__":
    main()
