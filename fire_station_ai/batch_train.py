"""Batch training runner for Fire Station AI models."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .cfr import CFRTrainer, CFRTrainerConfig
from .trainer import EvolutionTrainer, TrainerConfig


DEFAULT_SEEDS: Tuple[int, ...] = (108, 425, 18, 42, 1774421727)

def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _copy_with_seed(config: Dict[str, Any], seed: int, output_dir: str) -> Dict[str, Any]:
    payload = dict(config)
    payload["seed"] = int(seed)
    payload["output_dir"] = output_dir
    return payload


def build_batch_jobs(profile: str, seeds: Sequence[int], output_dir: str) -> List[Dict[str, Any]]:
    seeds = tuple(int(seed) for seed in seeds)
    if profile not in {"mini", "standard"}:
        raise ValueError(f"Unknown batch profile: {profile}")

    evolution_configs: List[Dict[str, Any]] = [
        {
            "algorithm": "evolution",
            "label": "evo_blend_standard",
            "config": {
                "generations": 8,
                "population_size": 8,
                "elite_count": 3,
                "hands_per_eval": 60,
                "validation_hands": 120,
                "eval_repeats": 1,
                "validation_repeats": 1,
                "mutation_sigma": 0.10,
                "random_injection": 0.20,
                "hall_of_fame_size": 3,
                "bet_set": (10, 25),
                "validation_bet_set": (10, 25),
                "init_mode": "blend",
                "base_bet": 10,
                "starting_stack": 1000,
                "save_artifacts": True,
                "show_progress": False,
            },
        },
        {
            "algorithm": "evolution",
            "label": "evo_random_wide",
            "config": {
                "generations": 10,
                "population_size": 10,
                "elite_count": 3,
                "hands_per_eval": 70,
                "validation_hands": 140,
                "eval_repeats": 1,
                "validation_repeats": 1,
                "mutation_sigma": 0.12,
                "random_injection": 0.28,
                "hall_of_fame_size": 4,
                "bet_set": (5, 10, 25),
                "validation_bet_set": (5, 10, 25, 50),
                "init_mode": "random",
                "base_bet": 10,
                "starting_stack": 1000,
                "save_artifacts": True,
                "show_progress": False,
            },
        },
    ]

    cfr_configs: List[Dict[str, Any]] = [
        {
            "algorithm": "cfr",
            "label": "cfr_balanced_core",
            "config": {
                "iterations": 24,
                "checkpoint_interval": 6,
                "hands_per_eval": 16,
                "validation_hands": 24,
                "eval_repeats": 1,
                "validation_repeats": 1,
                "bet_set": (10, 25),
                "validation_bet_set": (10, 25),
                "stack_set": (800, 1000, 1400),
                "max_round_depth": 8,
                "parallel_eval_workers": 0,
                "save_artifacts": True,
                "show_progress": False,
            },
        },
        {
            "algorithm": "cfr",
            "label": "cfr_wide_depth9",
            "config": {
                "iterations": 36,
                "checkpoint_interval": 6,
                "hands_per_eval": 20,
                "validation_hands": 30,
                "eval_repeats": 1,
                "validation_repeats": 1,
                "bet_set": (5, 10, 25),
                "validation_bet_set": (5, 10, 25, 50),
                "stack_set": (700, 1000, 1500),
                "max_round_depth": 9,
                "parallel_eval_workers": 0,
                "save_artifacts": True,
                "show_progress": False,
            },
        },
    ]

    if profile == "standard":
        evolution_configs.extend(
            [
                {
                    "algorithm": "evolution",
                    "label": "evo_blend_robustish",
                    "config": {
                        "generations": 12,
                        "population_size": 12,
                        "elite_count": 4,
                        "hands_per_eval": 90,
                        "validation_hands": 180,
                        "eval_repeats": 2,
                        "validation_repeats": 2,
                        "mutation_sigma": 0.10,
                        "random_injection": 0.22,
                        "hall_of_fame_size": 4,
                        "bet_set": (10, 25),
                        "validation_bet_set": (10, 25, 50),
                        "init_mode": "blend",
                        "base_bet": 10,
                        "starting_stack": 1000,
                        "save_artifacts": True,
                        "show_progress": False,
                    },
                }
            ]
        )
        cfr_configs.extend(
            [
                {
                    "algorithm": "cfr",
                    "label": "cfr_standard_robustish",
                    "config": {
                        "iterations": 60,
                        "checkpoint_interval": 10,
                        "hands_per_eval": 36,
                        "validation_hands": 60,
                        "eval_repeats": 2,
                        "validation_repeats": 2,
                        "bet_set": (10, 25),
                        "validation_bet_set": (10, 25),
                        "stack_set": (800, 1000, 1400),
                        "max_round_depth": 8,
                        "parallel_eval_workers": 0,
                        "save_artifacts": True,
                        "show_progress": False,
                    },
                }
            ]
        )

    jobs: List[Dict[str, Any]] = []
    for spec in evolution_configs + cfr_configs:
        for seed in seeds:
            jobs.append(
                {
                    "algorithm": spec["algorithm"],
                    "label": spec["label"],
                    "seed": int(seed),
                    "config": _copy_with_seed(spec["config"], seed, output_dir),
                }
            )
    return jobs


def archive_existing_runs(output_dir: str, archive_root: str | None = None) -> Path | None:
    runs_root = Path(output_dir)
    runs_root.mkdir(parents=True, exist_ok=True)
    existing_items = list(runs_root.iterdir())
    if not existing_items:
        return None

    archive_base = Path(archive_root) if archive_root else runs_root.parent / "run_archives"
    archive_base.mkdir(parents=True, exist_ok=True)
    archive_dir = archive_base / f"archive_{_timestamp()}"
    archive_dir.mkdir(parents=True, exist_ok=False)

    moved_items = []
    for item in existing_items:
        target = archive_dir / item.name
        shutil.move(str(item), str(target))
        moved_items.append(item.name)

    manifest = {
        "archived_at": datetime.now().isoformat(timespec="seconds"),
        "source_runs_dir": str(runs_root),
        "archive_dir": str(archive_dir),
        "item_count": len(moved_items),
        "items": moved_items,
    }
    (archive_dir / "archive_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return archive_dir


def run_batch_jobs(jobs: Sequence[Dict[str, Any]], manifest_dir: Path) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    total = len(jobs)
    for index, job in enumerate(jobs, start=1):
        algorithm = job["algorithm"]
        label = job["label"]
        seed = job["seed"]
        print(f"[{index}/{total}] {algorithm} · {label} · seed={seed}")

        if algorithm == "evolution":
            trainer = EvolutionTrainer(TrainerConfig(**job["config"]))
            summary = trainer.train()
        elif algorithm == "cfr":
            trainer = CFRTrainer(CFRTrainerConfig(**job["config"]))
            summary = trainer.train()
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        result = {
            "algorithm": algorithm,
            "label": label,
            "seed": seed,
            "model_name": summary.get("model_name", ""),
            "run_dir": summary.get("run_dir", ""),
            "best_training_score": float(summary.get("best_training_score", 0.0)),
            "validation_score": float(summary.get("validation", {}).get("score_per_scheduled_hand", 0.0)),
            "validation_win_rate": float(summary.get("validation", {}).get("win_rate", 0.0)),
        }
        print(
            f"      -> {result['model_name'] or '未命名'}"
            f" | train {result['best_training_score']:.3f}"
            f" | valid {result['validation_score']:.3f}"
            f" | win {result['validation_win_rate'] * 100:.1f}%"
        )
        results.append(result)

        (manifest_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量训练火烧洋油站模型")
    parser.add_argument("--profile", choices=["mini", "standard"], default="mini")
    parser.add_argument("--seeds", type=str, default="18,42")
    parser.add_argument("--output-dir", type=str, default="fire_station_ai/runs")
    parser.add_argument("--archive-existing", action="store_true")
    parser.add_argument("--archive-dir", type=str, default="")
    parser.add_argument("--limit", type=int, default=0)
    return parser


def parse_seeds(text: str) -> Tuple[int, ...]:
    values = []
    for item in str(text).split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        return DEFAULT_SEEDS
    return tuple(dict.fromkeys(values))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    seeds = parse_seeds(args.seeds)
    output_dir = args.output_dir

    archived_to = None
    if args.archive_existing:
        archived_to = archive_existing_runs(output_dir, args.archive_dir or None)

    jobs = build_batch_jobs(args.profile, seeds, output_dir)
    if args.limit > 0:
        jobs = jobs[: args.limit]

    manifest_dir = Path(output_dir) / f"batch_{_timestamp()}"
    manifest_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "profile": args.profile,
        "seeds": list(seeds),
        "output_dir": output_dir,
        "archive_existing": bool(args.archive_existing),
        "archived_to": None if archived_to is None else str(archived_to),
        "job_count": len(jobs),
        "jobs": jobs,
    }
    (manifest_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Fire Station Batch Trainer")
    print("=" * 72)
    print(f"批量配置         : {args.profile}")
    print(f"随机种子         : {list(seeds)}")
    print(f"任务数量         : {len(jobs)}")
    print(f"输出目录         : {output_dir}")
    if archived_to is not None:
        print(f"历史归档         : {archived_to}")
    print(f"批次清单         : {manifest_dir}")
    print()

    results = run_batch_jobs(jobs, manifest_dir)

    summary = {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "job_count": len(results),
        "results": results,
    }
    (manifest_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print("批量训练完成")
    print("-" * 72)
    for item in results:
        print(
            f"{item['algorithm']:<10} {item['label']:<22} seed={item['seed']:<2}  "
            f"{item['model_name'] or '未命名'}  "
            f"train {item['best_training_score']:.3f}  "
            f"valid {item['validation_score']:.3f}"
        )


if __name__ == "__main__":
    main()
