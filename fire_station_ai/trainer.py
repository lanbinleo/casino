"""Terminal-friendly trainer for Fire Station policies.

This trainer uses an evolutionary self-play loop instead of neural networks.
The upside is that every parameter remains interpretable for beginners.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
from statistics import mean
import sys
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .env import Action, ActionType, FireStationEnv, Observation, PlayerProfile, Seat
from .naming import generate_codename
from .policies import DifficultyPolicy, HeuristicPolicy, RandomPolicy, normalize_distribution, sample_action
from .selfplay import run_match

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - fallback when tqdm is unavailable
    tqdm = None


@dataclass
class PolicyGenome:
    strong_raise_bias: float = 0.22
    medium_raise_bias: float = 0.06
    weak_fold_bias: float = 0.28
    bluff_bonus: float = 0.15
    anti_aggression_call: float = 0.16
    short_stack_caution: float = 0.22
    pot_commitment_call: float = 0.15
    pressure_raise_bias: float = 0.95
    all_in_bias: float = 0.18
    randomness: float = 0.06

    BOUNDS = {
        "strong_raise_bias": (0.00, 0.60),
        "medium_raise_bias": (0.00, 0.40),
        "weak_fold_bias": (0.05, 0.90),
        "bluff_bonus": (0.00, 0.50),
        "anti_aggression_call": (0.00, 0.45),
        "short_stack_caution": (0.00, 0.60),
        "pot_commitment_call": (0.00, 0.45),
        "pressure_raise_bias": (0.20, 1.80),
        "all_in_bias": (0.00, 0.90),
        "randomness": (0.00, 0.30),
    }

    @classmethod
    def field_names(cls) -> List[str]:
        return list(cls.BOUNDS.keys())

    def clamp(self) -> "PolicyGenome":
        values = {}
        for name in self.field_names():
            low, high = self.BOUNDS[name]
            values[name] = min(high, max(low, float(getattr(self, name))))
        return PolicyGenome(**values)

    def mutate(self, rng: random.Random, sigma: float) -> "PolicyGenome":
        values = {}
        for name in self.field_names():
            low, high = self.BOUNDS[name]
            span = high - low
            current = float(getattr(self, name))
            mutated = current + rng.gauss(0.0, sigma * span)
            values[name] = min(high, max(low, mutated))
        return PolicyGenome(**values)

    def blend(self, other: "PolicyGenome", ratio_other: float = 0.35) -> "PolicyGenome":
        ratio_other = min(1.0, max(0.0, float(ratio_other)))
        ratio_self = 1.0 - ratio_other
        values = {}
        for name in self.field_names():
            values[name] = ratio_self * getattr(self, name) + ratio_other * getattr(other, name)
        return PolicyGenome(**values).clamp()

    @classmethod
    def random(cls, rng: random.Random) -> "PolicyGenome":
        values = {}
        for name in cls.field_names():
            low, high = cls.BOUNDS[name]
            values[name] = rng.uniform(low, high)
        return PolicyGenome(**values)

    @classmethod
    def mean_of(cls, genomes: Sequence["PolicyGenome"]) -> "PolicyGenome":
        if not genomes:
            return cls()
        values = {}
        for name in cls.field_names():
            values[name] = mean(getattr(genome, name) for genome in genomes)
        return PolicyGenome(**values).clamp()

    def to_dict(self) -> Dict[str, float]:
        return {key: float(value) for key, value in asdict(self).items()}


class GenomePolicy:
    """Interpretable policy parameterized by a small set of style weights."""

    def __init__(self, genome: PolicyGenome, name: str = "genome_policy") -> None:
        self.genome = genome.clamp()
        self.name = name

    def action_distribution(self, observation: Observation, legal_actions: Sequence[Action]) -> Dict[Action, float]:
        if not legal_actions:
            return {}

        strength = observation.private_strength
        opp_aggression = observation.opponent_profile.get("aggression", 0.5)
        opp_fold_rate = observation.opponent_profile.get("fold_rate", 0.5)
        weights = self._base_weights(strength)

        if strength >= 0.75:
            weights["raise"] += self.genome.strong_raise_bias
        elif strength >= 0.50:
            weights["raise"] += self.genome.medium_raise_bias
        else:
            weights["fold"] += self.genome.weak_fold_bias * (1.0 - strength)

        weights["call"] += self.genome.anti_aggression_call * max(0.0, opp_aggression - 0.5) * 2.0
        weights["raise"] += self.genome.bluff_bonus * max(0.0, opp_fold_rate - 0.45) * max(0.0, 0.55 - strength)

        if observation.my_chips < observation.current_bet * 3:
            weights["fold"] += self.genome.short_stack_caution
            weights["raise"] -= self.genome.short_stack_caution * 0.7

        if observation.pot > observation.my_chips * 0.3 and observation.round_num >= 2:
            weights["call"] += self.genome.pot_commitment_call
            weights["fold"] -= self.genome.pot_commitment_call * 0.5

        if observation.opponent_raises >= 2 and strength < 0.55:
            weights["fold"] += self.genome.short_stack_caution * 0.5

        for key in weights:
            weights[key] = max(0.01, weights[key])

        distribution: Dict[Action, float] = {}
        raise_actions = [action for action in legal_actions if action.kind not in {ActionType.CALL, ActionType.FOLD}]
        call_action = next((action for action in legal_actions if action.kind == ActionType.CALL), None)
        fold_action = next((action for action in legal_actions if action.kind == ActionType.FOLD), None)

        if call_action is not None:
            distribution[call_action] = weights["call"]
        if fold_action is not None:
            distribution[fold_action] = weights["fold"]
        if raise_actions:
            raise_bucket = self._raise_bucket(strength, raise_actions)
            for action, bucket_weight in raise_bucket.items():
                distribution[action] = weights["raise"] * bucket_weight

        base_distribution = normalize_distribution(distribution)
        if self.genome.randomness <= 0:
            return base_distribution

        uniform = normalize_distribution({action: 1.0 for action in legal_actions})
        mixed = {}
        keep = 1.0 - self.genome.randomness
        for action in legal_actions:
            mixed[action] = keep * base_distribution.get(action, 0.0) + self.genome.randomness * uniform.get(action, 0.0)
        return normalize_distribution(mixed)

    def _base_weights(self, strength: float) -> Dict[str, float]:
        if strength >= 0.75:
            return {"raise": 0.70, "call": 0.26, "fold": 0.04}
        if strength >= 0.50:
            return {"raise": 0.34, "call": 0.44, "fold": 0.22}
        if strength >= 0.25:
            return {"raise": 0.14, "call": 0.28, "fold": 0.58}
        return {"raise": 0.05, "call": 0.14, "fold": 0.81}

    def _raise_bucket(self, strength: float, raise_actions: Sequence[Action]) -> Dict[Action, float]:
        weights = {}
        for action in raise_actions:
            if action.kind == ActionType.MIN_RAISE:
                base = 1.0 if strength < 0.8 else 1.25
            elif action.kind == ActionType.DOUBLE_RAISE:
                base = 0.9 if strength < 0.6 else 1.1
            elif action.kind == ActionType.PRESSURE_RAISE:
                base = self.genome.pressure_raise_bias if strength >= 0.35 else self.genome.pressure_raise_bias * 1.15
            elif action.kind == ActionType.ALL_IN:
                base = self.genome.all_in_bias if strength >= 0.8 else self.genome.all_in_bias * 0.35
            else:
                base = 1.0
            weights[action] = max(0.01, base)
        return normalize_distribution(weights)

    def act(self, observation: Observation, legal_actions: Sequence[Action], rng: random.Random) -> Action:
        return sample_action(self.action_distribution(observation, legal_actions), rng)


@dataclass
class TrainerConfig:
    generations: int = 20
    population_size: int = 14
    elite_count: int = 4
    hands_per_eval: int = 120
    validation_hands: int = 240
    eval_repeats: int = 2
    validation_repeats: int = 2
    mutation_sigma: float = 0.12
    random_injection: float = 0.20
    hall_of_fame_size: int = 4
    bet_set: Tuple[int, ...] = (10,)
    validation_bet_set: Tuple[int, ...] = (10,)
    init_mode: str = "default"
    base_bet: int = 10
    starting_stack: int = 1000
    seed: int = 7
    output_dir: str = "fire_station_ai/runs"
    save_artifacts: bool = True
    show_progress: bool = True


BASE_OPPONENT_POOL = (
    ("random", RandomPolicy()),
    ("tight_normal", DifficultyPolicy.for_level(HeuristicPolicy(personality="tight", mood=0.45), "normal")),
    ("tricky_hard", DifficultyPolicy.for_level(HeuristicPolicy(personality="tricky", mood=0.58, boss=True), "hard")),
)


PARAMETER_GUIDE = {
    "strong_raise_bias": "强牌时更愿意主动加注",
    "medium_raise_bias": "中牌时更愿意争取主动",
    "weak_fold_bias": "弱牌时更倾向保守弃牌",
    "bluff_bonus": "对手偏保守时更愿意偷鸡",
    "anti_aggression_call": "对手激进时更敢跟注",
    "short_stack_caution": "短码时更谨慎",
    "pot_commitment_call": "底池大时更不愿意轻易放弃",
    "pressure_raise_bias": "偏爱用压力加注逼迫对手",
    "all_in_bias": "强牌时更愿意直接压满",
    "randomness": "故意保留一点随机性，避免完全机械",
}


def evaluate_genome(genome: PolicyGenome, config: TrainerConfig, seed_offset: int = 0) -> Dict[str, Any]:
    candidate_policy = GenomePolicy(genome, name="candidate")
    opponent_pool = build_opponent_pool(config, champion_genome=None, hall_of_fame=())
    return evaluate_against_pool(candidate_policy, opponent_pool, config, seed_offset=seed_offset, genome=genome)


def build_opponent_pool(
    config: TrainerConfig,
    champion_genome: PolicyGenome | None,
    hall_of_fame: Sequence[PolicyGenome],
) -> List[Tuple[str, object]]:
    pool: List[Tuple[str, object]] = list(BASE_OPPONENT_POOL)
    if champion_genome is not None:
        pool.append(("current_champion", GenomePolicy(champion_genome, name="current_champion")))
    for index, genome in enumerate(hall_of_fame[: config.hall_of_fame_size], start=1):
        pool.append((f"hall_of_fame_{index}", GenomePolicy(genome, name=f"hall_of_fame_{index}")))
    return pool


def evaluate_against_pool(
    candidate_policy,
    opponent_pool: Sequence[Tuple[str, object]],
    config: TrainerConfig,
    *,
    seed_offset: int,
    genome: PolicyGenome | None = None,
) -> Dict[str, Any]:
    scores = []
    per_opponent = {}
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for index, (label, opponent) in enumerate(opponent_pool):
        opponent_scores = []
        opponent_wins = 0
        opponent_losses = 0
        opponent_ties = 0
        opponent_hands = 0

        for bet_index, base_bet in enumerate(config.bet_set):
            for repeat in range(config.eval_repeats):
                result = run_match(
                    candidate_policy,
                    opponent,
                    hands=config.hands_per_eval,
                    base_bet=base_bet,
                    starting_stacks=(config.starting_stack, config.starting_stack),
                    seed=config.seed + seed_offset * 193 + index * 31 + bet_index * 101 + repeat * 7,
                )
                delta = result.bankroll_delta[0]
                score = delta / max(config.hands_per_eval, 1)
                opponent_scores.append(score)
                opponent_wins += result.seat0_wins
                opponent_losses += result.seat1_wins
                opponent_ties += result.ties
                opponent_hands += result.hands_played

        mean_score = sum(opponent_scores) / max(len(opponent_scores), 1)
        scores.append(mean_score)
        per_opponent[label] = {
            "score_per_scheduled_hand": mean_score,
            "wins": opponent_wins,
            "losses": opponent_losses,
            "ties": opponent_ties,
            "hands_played": opponent_hands,
            "repeats": config.eval_repeats,
            "bet_set": list(config.bet_set),
        }
        total_wins += opponent_wins
        total_losses += opponent_losses
        total_ties += opponent_ties

    avg_score = sum(scores) / max(len(scores), 1)
    total_hands = total_wins + total_losses + total_ties
    win_rate = total_wins / max(total_hands, 1)

    return {
        "genome": None if genome is None else genome.to_dict(),
        "score": avg_score,
        "win_rate": win_rate,
        "wins": total_wins,
        "losses": total_losses,
        "ties": total_ties,
        "per_opponent": per_opponent,
    }


def validate_genome(genome: PolicyGenome, config: TrainerConfig) -> Dict[str, Any]:
    candidate_policy = GenomePolicy(genome, name="validated_champion")
    opponent = DifficultyPolicy.for_level(HeuristicPolicy(personality="tricky", mood=0.60, boss=True, cycle=1), "hard")
    scores = []
    wins = 0
    losses = 0
    ties = 0
    hands = 0
    bankroll_delta = 0

    for bet_index, base_bet in enumerate(config.validation_bet_set):
        for repeat in range(config.validation_repeats):
            result = run_match(
                candidate_policy,
                opponent,
                hands=config.validation_hands,
                base_bet=base_bet,
                starting_stacks=(config.starting_stack, config.starting_stack),
                seed=config.seed + 99991 + bet_index * 211 + repeat * 13,
            )
            scores.append(result.bankroll_delta[0] / max(config.validation_hands, 1))
            wins += result.seat0_wins
            losses += result.seat1_wins
            ties += result.ties
            hands += result.hands_played
            bankroll_delta += result.bankroll_delta[0]

    score = sum(scores) / max(len(scores), 1)
    win_rate = wins / max(hands, 1)
    return {
        "score_per_scheduled_hand": score,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "hands": hands,
        "bankroll_delta": bankroll_delta,
        "bet_set": list(config.validation_bet_set),
        "repeats": config.validation_repeats,
    }


class EvolutionTrainer:
    def __init__(self, config: TrainerConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)

    def train(self) -> Dict[str, Any]:
        center = self._initial_center()
        best_result = evaluate_genome(center, self.config, seed_offset=-1)
        hall_of_fame: List[PolicyGenome] = []
        history: List[Dict[str, Any]] = []
        used_codenames = set()
        champion_codename = generate_codename(self.rng, used=used_codenames)
        used_codenames.add(champion_codename)

        generation_iter = range(1, self.config.generations + 1)
        generation_bar = self._maybe_tqdm(
            generation_iter,
            total=self.config.generations,
            desc="训练进度",
            unit="代",
        )

        for generation in generation_bar:
            opponent_pool = build_opponent_pool(
                self.config,
                champion_genome=PolicyGenome(**best_result["genome"]),
                hall_of_fame=hall_of_fame,
            )

            candidates: List[PolicyGenome] = [
                center,
                PolicyGenome(**best_result["genome"]),
                center.mutate(self.rng, self.config.mutation_sigma * 0.5),
                PolicyGenome(**best_result["genome"]).mutate(self.rng, self.config.mutation_sigma * 0.5),
            ]
            random_injection_count = max(1, int(round(self.config.population_size * self.config.random_injection)))
            while len(candidates) < min(self.config.population_size, 4 + random_injection_count):
                candidates.append(PolicyGenome.random(self.rng))
            while len(candidates) < self.config.population_size:
                parent_candidates = [center, PolicyGenome(**best_result["genome"]), PolicyGenome.mean_of(hall_of_fame)] if hall_of_fame else [center, PolicyGenome(**best_result["genome"])]
                parent = self.rng.choice(parent_candidates)
                candidates.append(parent.mutate(self.rng, self.config.mutation_sigma))

            evaluated = []
            candidate_bar = self._maybe_tqdm(
                list(enumerate(candidates)),
                total=len(candidates),
                desc=f"第 {generation:02d} 代评估",
                unit="个",
                leave=False,
            )
            for candidate_index, genome in candidate_bar:
                result = evaluate_against_pool(
                    GenomePolicy(genome, name="candidate"),
                    opponent_pool,
                    self.config,
                    seed_offset=generation * 100 + candidate_index,
                    genome=genome,
                )
                evaluated.append(result)
                if hasattr(candidate_bar, "set_postfix"):
                    candidate_bar.set_postfix({"当前分数": f"{result['score']:.3f}"})

            evaluated.sort(key=lambda item: item["score"], reverse=True)
            elites = evaluated[: max(1, min(self.config.elite_count, len(evaluated)))]
            center = PolicyGenome.mean_of([PolicyGenome(**item["genome"]) for item in elites])

            generation_best = elites[0]
            champion_changed = False
            if generation_best["score"] > best_result["score"]:
                best_result = generation_best
                champion_changed = True
                champion_codename = generate_codename(self.rng, used=used_codenames)
                used_codenames.add(champion_codename)

            hall_of_fame = self._update_hall_of_fame(hall_of_fame, [PolicyGenome(**item["genome"]) for item in elites], best_result)

            validation = validate_genome(PolicyGenome(**best_result["genome"]), self.config)
            history.append(
                {
                    "generation": generation,
                    "avg_score": sum(item["score"] for item in evaluated) / len(evaluated),
                    "best_score": generation_best["score"],
                    "champion_score": best_result["score"],
                    "generation_win_rate": generation_best["win_rate"],
                    "validation_score": validation["score_per_scheduled_hand"],
                    "validation_win_rate": validation["win_rate"],
                    "champion_changed": champion_changed,
                    "champion_codename": champion_codename,
                    "champion_genome": best_result["genome"],
                }
            )
            if hasattr(generation_bar, "set_postfix"):
                generation_bar.set_postfix(
                    {
                        "冠军": f"{best_result['score']:.3f}",
                        "验证": f"{validation['score_per_scheduled_hand']:.3f}",
                    }
                )

        summary = {
            "config": asdict(self.config),
            "model_name": champion_codename,
            "best_genome": best_result["genome"],
            "best_training_score": best_result["score"],
            "best_training_win_rate": best_result["win_rate"],
            "best_training_breakdown": best_result["per_opponent"],
            "validation": validate_genome(PolicyGenome(**best_result["genome"]), self.config),
            "history": history,
            "parameter_guide": PARAMETER_GUIDE,
            "opponent_pool": [name for name, _ in BASE_OPPONENT_POOL],
            "training_mode": "fixed_pool_plus_champion_plus_hall_of_fame",
        }
        summary["auto_commentary_zh"] = self._build_auto_commentary(summary)

        if self.config.save_artifacts:
            run_dir = self._write_artifacts(summary)
            summary["run_dir"] = str(run_dir)
        return summary

    def _initial_center(self) -> PolicyGenome:
        default = PolicyGenome()
        if self.config.init_mode == "default":
            return default
        if self.config.init_mode == "random":
            return PolicyGenome.random(self.rng)
        if self.config.init_mode == "blend":
            return default.blend(PolicyGenome.random(self.rng), ratio_other=0.35)
        return default

    def _maybe_tqdm(self, iterable, **kwargs):
        if not self.config.show_progress or tqdm is None:
            return iterable
        kwargs.setdefault("file", sys.stdout)
        kwargs.setdefault("dynamic_ncols", True)
        kwargs.setdefault("mininterval", 0.1)
        return tqdm(iterable, **kwargs)

    def _update_hall_of_fame(
        self,
        hall_of_fame: List[PolicyGenome],
        elite_genomes: Sequence[PolicyGenome],
        best_result: Dict[str, Any],
    ) -> List[PolicyGenome]:
        combined = list(hall_of_fame) + list(elite_genomes) + [PolicyGenome(**best_result["genome"])]
        unique: List[PolicyGenome] = []
        seen = set()
        for genome in combined:
            key = tuple(round(getattr(genome, name), 6) for name in PolicyGenome.field_names())
            if key in seen:
                continue
            seen.add(key)
            unique.append(genome)
        return unique[: self.config.hall_of_fame_size]

    def _build_auto_commentary(self, summary: Dict[str, Any]) -> List[str]:
        best = summary["best_genome"]
        validation = summary["validation"]
        lines: List[str] = []

        training_score = float(summary["best_training_score"])
        validation_score = float(validation["score_per_scheduled_hand"])
        if training_score > 0 and validation_score > 0:
            lines.append("这次冠军在训练对手和验证对手上都保持正收益，泛化表现不错。")
        elif training_score > 0 and validation_score <= 0:
            lines.append("这次冠军能打赢训练池，但在验证对手上亏损，说明还存在明显过拟合。")
        else:
            lines.append("这次冠军在训练阶段都没有建立稳定优势，建议先提高评估手数或增大种群。")

        if best["pressure_raise_bias"] >= 1.05:
            lines.append("它的核心风格偏向高压加注，会更主动地用下注压力逼迫对手弃牌。")
        elif best["pressure_raise_bias"] <= 0.75:
            lines.append("它对压力加注相对克制，更依赖中小尺度的稳定决策。")
        else:
            lines.append("它保留了中等强度的压力加注，但不是无脑猛压的类型。")

        if best["bluff_bonus"] >= 0.20:
            lines.append("它对保守型对手的偷鸡意愿较强，容易打出带攻击性的诈唬线。")
        elif best["bluff_bonus"] <= 0.10:
            lines.append("它的诈唬权重不高，更偏向让价值牌和局面压力来赢底池。")

        if best["short_stack_caution"] >= 0.24:
            lines.append("短码时它会明显收紧，倾向减少高风险对抗。")
        elif best["short_stack_caution"] <= 0.12:
            lines.append("短码时它仍然愿意继续对抗，不会轻易因为筹码少就全面收缩。")

        if best["pot_commitment_call"] >= 0.22:
            lines.append("底池一旦变大，它会更有粘性，不愿意轻易放弃已经投入的筹码。")
        elif best["pot_commitment_call"] <= 0.10:
            lines.append("即使底池变大，它也比较愿意及时止损，整体更克制。")

        breakdown = summary.get("best_training_breakdown", {})
        if breakdown:
            weakest_name = min(breakdown, key=lambda name: breakdown[name]["score_per_scheduled_hand"])
            weakest_score = breakdown[weakest_name]["score_per_scheduled_hand"]
            strongest_name = max(breakdown, key=lambda name: breakdown[name]["score_per_scheduled_hand"])
            strongest_score = breakdown[strongest_name]["score_per_scheduled_hand"]
            if abs(strongest_score - weakest_score) < 1e-6:
                lines.append("它对当前训练对手池的表现比较接近，还没有出现特别明显的短板或统治点。")
            else:
                lines.append(f"它当前最吃力的训练对手是 {weakest_name}（{weakest_score:.3f}），最擅长压制的是 {strongest_name}（{strongest_score:.3f}）。")

        lines.append("如果你想优先追求泛化，建议先增加 bet_set、多跑几个验证重复次数，再观察验证分数是否回正。")
        return lines

    def _write_artifacts(self, summary: Dict[str, Any]) -> Path:
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / f"run_seed{self.config.seed}_gen{self.config.generations}"
        suffix = 1
        while run_dir.exists():
            suffix += 1
            run_dir = output_dir / f"run_seed{self.config.seed}_gen{self.config.generations}_{suffix}"
        run_dir.mkdir(parents=True, exist_ok=False)

        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "best_policy.json").write_text(
            json.dumps(
                {
                    "policy_type": "genome_policy",
                    "model_name": summary.get("model_name"),
                    "genome": summary["best_genome"],
                    "parameter_guide": PARAMETER_GUIDE,
                },
                indent=2,
                ensure_ascii=False,
                ),
                encoding="utf-8",
        )
        (run_dir / "insight_zh.txt").write_text("\n".join(summary.get("auto_commentary_zh", [])), encoding="utf-8")
        return run_dir
