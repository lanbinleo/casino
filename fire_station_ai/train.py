"""CLI entrypoint for terminal training."""

from __future__ import annotations

import argparse
from typing import Iterable, List

from .trainer import EvolutionTrainer, PARAMETER_GUIDE, PolicyGenome, TrainerConfig


def ascii_bar(value: float, low: float, high: float, width: int = 28) -> str:
    if high <= low:
        return "#" * (width // 2)
    ratio = (value - low) / (high - low)
    ratio = min(1.0, max(0.0, ratio))
    filled = int(round(ratio * width))
    return "#" * filled + "-" * (width - filled)


def print_header(config: TrainerConfig) -> None:
    print("Fire Station Trainer")
    print("=" * 72)
    print(f"generations      : {config.generations}")
    print(f"population_size  : {config.population_size}")
    print(f"elite_count      : {config.elite_count}")
    print(f"hands_per_eval   : {config.hands_per_eval}")
    print(f"validation_hands : {config.validation_hands}")
    print(f"mutation_sigma   : {config.mutation_sigma}")
    print(f"base_bet         : {config.base_bet}")
    print(f"starting_stack   : {config.starting_stack}")
    print(f"seed             : {config.seed}")
    print()
    print("How to read the score:")
    print("- score > 0 means the policy is winning chips on average")
    print("- the score is normalized by the planned number of hands")
    print("- validation_win_rate is the easier beginner metric to watch")
    print("- parameters at the end describe the champion's playing style")
    print()


def print_history(history: List[dict]) -> None:
    print("Generation Curve")
    print("-" * 72)
    if not history:
        print("No history")
        return

    score_values = [item["champion_score"] for item in history]
    validation_values = [item["validation_win_rate"] for item in history]
    score_low = min(score_values)
    score_high = max(score_values)

    for item in history:
        gen = item["generation"]
        score = item["champion_score"]
        win_rate = item["validation_win_rate"]
        score_bar = ascii_bar(score, score_low, score_high if score_high > score_low else score_low + 1e-6)
        win_bar = ascii_bar(win_rate, 0.0, 1.0)
        print(
            f"G{gen:02d}  champion {score:>7.3f} |{score_bar}|  "
            f"valid {win_rate * 100:>5.1f}% |{win_bar}|"
        )
    print()


def print_parameter_summary(best_genome: dict) -> None:
    print("Champion Parameters")
    print("-" * 72)
    for name, value in best_genome.items():
        guide = PARAMETER_GUIDE.get(name, "")
        low, high = PolicyGenome.BOUNDS.get(name, (0.0, 1.0))
        bar = ascii_bar(float(value), float(low), float(high))
        print(f"{name:22} {value:>6.3f}  |{bar}|  {guide}")
    print()


def print_takeaways(summary: dict) -> None:
    validation = summary["validation"]
    print("Beginner Summary")
    print("-" * 72)
    print(f"Best training score : {summary['best_training_score']:.3f} chips/hand")
    print(f"Training win rate   : {summary['best_training_win_rate'] * 100:.1f}%")
    print(f"Validation score    : {validation['score_per_scheduled_hand']:.3f} chips/hand")
    print(f"Validation win rate : {validation['win_rate'] * 100:.1f}%")
    print(f"Validation record   : {validation['wins']}W {validation['losses']}L {validation['ties']}T")
    if "run_dir" in summary:
        print(f"Artifacts saved to  : {summary['run_dir']}")
    print()
    print("What the trainer is doing:")
    print("- Every generation it mutates a batch of candidate play styles")
    print("- Candidates self-play against a small fixed opponent pool")
    print("- The best candidates become the center for the next generation")
    print("- The final champion is tested again on a tougher validation match")
    print()


def parse_args() -> TrainerConfig:
    parser = argparse.ArgumentParser(description="Train a terminal policy for Fire Station")
    parser.add_argument("--generations", type=int, default=16)
    parser.add_argument("--population-size", type=int, default=12)
    parser.add_argument("--elite-count", type=int, default=4)
    parser.add_argument("--hands-per-eval", type=int, default=90)
    parser.add_argument("--validation-hands", type=int, default=220)
    parser.add_argument("--mutation-sigma", type=float, default=0.10)
    parser.add_argument("--base-bet", type=int, default=10)
    parser.add_argument("--starting-stack", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", type=str, default="fire_station_ai/runs")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    return TrainerConfig(
        generations=args.generations,
        population_size=args.population_size,
        elite_count=args.elite_count,
        hands_per_eval=args.hands_per_eval,
        validation_hands=args.validation_hands,
        mutation_sigma=args.mutation_sigma,
        base_bet=args.base_bet,
        starting_stack=args.starting_stack,
        seed=args.seed,
        output_dir=args.output_dir,
        save_artifacts=not args.no_save,
    )


def main() -> None:
    config = parse_args()
    print_header(config)
    trainer = EvolutionTrainer(config)
    summary = trainer.train()
    print_history(summary["history"])
    print_takeaways(summary)
    print_parameter_summary(summary["best_genome"])


if __name__ == "__main__":
    main()
