"""CLI entrypoint for terminal training."""

from __future__ import annotations

import argparse
from typing import Dict, List, Tuple

from .trainer import EvolutionTrainer, PARAMETER_GUIDE, PolicyGenome, TrainerConfig


PRESET_DEFAULTS: Dict[str, Dict[str, object]] = {
    "quick": {
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
        "bet_set": "10",
        "validation_bet_set": "10",
        "init_mode": "default",
    },
    "balanced": {
        "generations": 16,
        "population_size": 12,
        "elite_count": 4,
        "hands_per_eval": 90,
        "validation_hands": 220,
        "eval_repeats": 2,
        "validation_repeats": 2,
        "mutation_sigma": 0.10,
        "random_injection": 0.20,
        "hall_of_fame_size": 4,
        "bet_set": "10,25",
        "validation_bet_set": "10,25",
        "init_mode": "blend",
    },
    "robust": {
        "generations": 24,
        "population_size": 18,
        "elite_count": 5,
        "hands_per_eval": 140,
        "validation_hands": 260,
        "eval_repeats": 3,
        "validation_repeats": 3,
        "mutation_sigma": 0.12,
        "random_injection": 0.25,
        "hall_of_fame_size": 6,
        "bet_set": "5,10,25",
        "validation_bet_set": "5,10,25,50",
        "init_mode": "blend",
    },
}


def ascii_bar(value: float, low: float, high: float, width: int = 28) -> str:
    if high <= low:
        return "#" * (width // 2)
    ratio = (value - low) / (high - low)
    ratio = min(1.0, max(0.0, ratio))
    filled = int(round(ratio * width))
    return "#" * filled + "-" * (width - filled)


def parse_int_tuple(text: str) -> Tuple[int, ...]:
    values = []
    for item in str(text).split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item))
    if not values:
        raise ValueError("bet set cannot be empty")
    return tuple(dict.fromkeys(values))


def build_parser() -> argparse.ArgumentParser:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--preset", choices=sorted(PRESET_DEFAULTS), default="balanced")
    known, _ = pre_parser.parse_known_args()
    defaults = PRESET_DEFAULTS.get(known.preset, PRESET_DEFAULTS["balanced"])

    parser = argparse.ArgumentParser(description="训练火烧洋油站终端 AI")
    parser.set_defaults(**defaults)
    parser.add_argument("--preset", choices=sorted(PRESET_DEFAULTS), default=known.preset)
    parser.add_argument("--generations", type=int)
    parser.add_argument("--population-size", type=int)
    parser.add_argument("--elite-count", type=int)
    parser.add_argument("--hands-per-eval", type=int)
    parser.add_argument("--validation-hands", type=int)
    parser.add_argument("--eval-repeats", type=int)
    parser.add_argument("--validation-repeats", type=int)
    parser.add_argument("--mutation-sigma", type=float)
    parser.add_argument("--random-injection", type=float)
    parser.add_argument("--hall-of-fame-size", type=int)
    parser.add_argument("--bet-set", type=str)
    parser.add_argument("--validation-bet-set", type=str)
    parser.add_argument("--init-mode", choices=["default", "random", "blend"])
    parser.add_argument("--base-bet", type=int, default=10)
    parser.add_argument("--starting-stack", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-dir", type=str, default="fire_station_ai/runs")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    return parser


def print_header(config: TrainerConfig, preset: str) -> None:
    print("火烧洋油站 AI 训练器")
    print("=" * 72)
    print(f"预设模式         : {preset}")
    print(f"训练代数         : {config.generations}")
    print(f"每代候选数       : {config.population_size}")
    print(f"保留精英数       : {config.elite_count}")
    print(f"每次评估手数     : {config.hands_per_eval}")
    print(f"验证手数         : {config.validation_hands}")
    print(f"训练重复次数     : {config.eval_repeats}")
    print(f"验证重复次数     : {config.validation_repeats}")
    print(f"变异强度         : {config.mutation_sigma}")
    print(f"随机新血比例     : {config.random_injection}")
    print(f"名人堂容量       : {config.hall_of_fame_size}")
    print(f"训练底注集合     : {list(config.bet_set)}")
    print(f"验证底注集合     : {list(config.validation_bet_set)}")
    print(f"初始中心策略     : {config.init_mode}")
    print(f"随机种子         : {config.seed}")
    print()
    print("怎么读这些数字：")
    print("- `score > 0` 代表平均下来能赚筹码。")
    print("- `validation_win_rate` 更适合快速看强弱。")
    print("- 参数条形图描述的是冠军策略的性格。")
    print()


def print_history(history: List[dict]) -> None:
    print("训练曲线")
    print("-" * 72)
    if not history:
        print("没有历史记录")
        return

    score_values = [item["champion_score"] for item in history]
    score_low = min(score_values)
    score_high = max(score_values)

    for item in history:
        gen = item["generation"]
        score = item["champion_score"]
        win_rate = item["validation_win_rate"]
        score_bar = ascii_bar(score, score_low, score_high if score_high > score_low else score_low + 1e-6)
        win_bar = ascii_bar(win_rate, 0.0, 1.0)
        marker = "*" if item.get("champion_changed") else " "
        print(
            f"第 {gen:02d} 代{marker}  冠军分 {score:>7.3f} |{score_bar}|  "
            f"验证胜率 {win_rate * 100:>5.1f}% |{win_bar}|"
        )
    print()
    print("* 代表这一代刷新了全局冠军")
    print()


def print_breakdown(breakdown: dict) -> None:
    print("冠军对各类训练对手的表现")
    print("-" * 72)
    for name, stats in breakdown.items():
        score = stats["score_per_scheduled_hand"]
        hands = stats["hands_played"]
        wins = stats["wins"]
        losses = stats["losses"]
        ties = stats["ties"]
        bar = ascii_bar(score, -20.0, 20.0)
        print(
            f"{name:18} 分数 {score:>7.3f} |{bar}|  "
            f"战绩 {wins}W {losses}L {ties}T / {hands} 手"
        )
    print()


def print_parameter_summary(best_genome: dict) -> None:
    print("冠军参数画像")
    print("-" * 72)
    for name, value in best_genome.items():
        guide = PARAMETER_GUIDE.get(name, "")
        low, high = PolicyGenome.BOUNDS.get(name, (0.0, 1.0))
        bar = ascii_bar(float(value), float(low), float(high))
        print(f"{name:22} {value:>6.3f}  |{bar}|  {guide}")
    print()


def print_takeaways(summary: dict) -> None:
    validation = summary["validation"]
    print("结果摘要")
    print("-" * 72)
    print(f"冠军代号         : {summary.get('model_name', '未命名模型')}")
    print(f"最佳训练分数     : {summary['best_training_score']:.3f} 筹码/手")
    print(f"训练胜率         : {summary['best_training_win_rate'] * 100:.1f}%")
    print(f"验证分数         : {validation['score_per_scheduled_hand']:.3f} 筹码/手")
    print(f"验证胜率         : {validation['win_rate'] * 100:.1f}%")
    print(f"验证战绩         : {validation['wins']}W {validation['losses']}L {validation['ties']}T")
    print(f"验证底注         : {validation['bet_set']}")
    if "run_dir" in summary:
        print(f"结果目录         : {summary['run_dir']}")
    print()
    print("训练机制说明：")
    print("- 每一代会生成一批不同性格的候选策略。")
    print("- 候选会去打固定陪练、当前冠军和历史强者。")
    print("- 还会额外加入一部分随机新候选，避免太早卡死。")
    print("- 最终冠军会在更严格的验证环境里再打一轮。")
    print()


def print_auto_commentary(summary: dict) -> None:
    print("自动中文解读")
    print("-" * 72)
    for line in summary.get("auto_commentary_zh", []):
        print(f"- {line}")
    print()


def print_tuning_tips() -> None:
    print("怎么调参数更容易出效果")
    print("-" * 72)
    print("- 想更快看到结果：用 `--preset quick`。")
    print("- 想更稳一点：用 `--preset balanced`。")
    print("- 想优先追求泛化：用 `--preset robust`。")
    print("- 如果冠军一直不变：增大 `--random-injection` 或 `--mutation-sigma`。")
    print("- 如果分数波动太大：增大 `--eval-repeats` 和 `--validation-repeats`。")
    print("- 如果训练强、验证差：把 `--bet-set` 和 `--validation-bet-set` 设得更丰富。")
    print("- 如果你怀疑初始模板太强：把 `--init-mode` 改成 `blend` 或 `random`。")
    print()


def parse_args() -> tuple[TrainerConfig, str]:
    parser = build_parser()
    args = parser.parse_args()
    bet_set = parse_int_tuple(args.bet_set)
    validation_bet_set = parse_int_tuple(args.validation_bet_set)
    config = TrainerConfig(
        generations=args.generations,
        population_size=args.population_size,
        elite_count=args.elite_count,
        hands_per_eval=args.hands_per_eval,
        validation_hands=args.validation_hands,
        eval_repeats=args.eval_repeats,
        validation_repeats=args.validation_repeats,
        mutation_sigma=args.mutation_sigma,
        random_injection=args.random_injection,
        hall_of_fame_size=args.hall_of_fame_size,
        bet_set=bet_set,
        validation_bet_set=validation_bet_set,
        init_mode=args.init_mode,
        base_bet=args.base_bet,
        starting_stack=args.starting_stack,
        seed=args.seed,
        output_dir=args.output_dir,
        save_artifacts=not args.no_save,
        show_progress=not args.no_progress,
    )
    return config, args.preset


def main() -> None:
    config, preset = parse_args()
    print_header(config, preset)
    trainer = EvolutionTrainer(config)
    summary = trainer.train()
    print_history(summary["history"])
    print_takeaways(summary)
    print_auto_commentary(summary)
    print_breakdown(summary["best_training_breakdown"])
    print_parameter_summary(summary["best_genome"])
    print_tuning_tips()


if __name__ == "__main__":
    main()
