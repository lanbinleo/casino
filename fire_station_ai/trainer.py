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
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .env import Action, ActionType, FireStationEnv, Observation, PlayerProfile, Seat
from .policies import DifficultyPolicy, HeuristicPolicy, RandomPolicy, normalize_distribution, sample_action
from .selfplay import run_match


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
    mutation_sigma: float = 0.12
    base_bet: int = 10
    starting_stack: int = 1000
    seed: int = 7
    output_dir: str = "fire_station_ai/runs"
    save_artifacts: bool = True


OPPONENT_POOL = (
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
    scores = []
    per_opponent = {}
    total_wins = 0
    total_losses = 0
    total_ties = 0

    for index, (label, opponent) in enumerate(OPPONENT_POOL):
        result = run_match(
            candidate_policy,
            opponent,
            hands=config.hands_per_eval,
            base_bet=config.base_bet,
            starting_stacks=(config.starting_stack, config.starting_stack),
            seed=config.seed + seed_offset * 97 + index * 17,
        )
        delta = result.bankroll_delta[0]
        score = delta / max(config.hands_per_eval, 1)
        scores.append(score)
        per_opponent[label] = {
            "score_per_scheduled_hand": score,
            "wins": result.seat0_wins,
            "losses": result.seat1_wins,
            "ties": result.ties,
            "hands_played": result.hands_played,
        }
        total_wins += result.seat0_wins
        total_losses += result.seat1_wins
        total_ties += result.ties

    avg_score = sum(scores) / max(len(scores), 1)
    total_hands = total_wins + total_losses + total_ties
    win_rate = total_wins / max(total_hands, 1)

    return {
        "genome": genome.to_dict(),
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
    result = run_match(
        candidate_policy,
        opponent,
        hands=config.validation_hands,
        base_bet=config.base_bet,
        starting_stacks=(config.starting_stack, config.starting_stack),
        seed=config.seed + 99991,
    )
    score = result.bankroll_delta[0] / max(config.validation_hands, 1)
    win_rate = result.seat0_wins / max(result.hands_played, 1)
    return {
        "score_per_scheduled_hand": score,
        "win_rate": win_rate,
        "wins": result.seat0_wins,
        "losses": result.seat1_wins,
        "ties": result.ties,
        "hands": result.hands_played,
        "bankroll_delta": result.bankroll_delta[0],
    }


class EvolutionTrainer:
    def __init__(self, config: TrainerConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)

    def train(self) -> Dict[str, Any]:
        center = PolicyGenome()
        best_result = evaluate_genome(center, self.config, seed_offset=-1)
        history: List[Dict[str, Any]] = []

        for generation in range(1, self.config.generations + 1):
            candidates: List[PolicyGenome] = [center, center.mutate(self.rng, self.config.mutation_sigma * 0.5)]
            while len(candidates) < self.config.population_size:
                parent = center if self.rng.random() < 0.65 else PolicyGenome(**best_result["genome"])
                candidates.append(parent.mutate(self.rng, self.config.mutation_sigma))

            evaluated = []
            for candidate_index, genome in enumerate(candidates):
                evaluated.append(evaluate_genome(genome, self.config, seed_offset=generation * 100 + candidate_index))

            evaluated.sort(key=lambda item: item["score"], reverse=True)
            elites = evaluated[: max(1, min(self.config.elite_count, len(evaluated)))]
            center = PolicyGenome.mean_of([PolicyGenome(**item["genome"]) for item in elites])

            generation_best = elites[0]
            if generation_best["score"] > best_result["score"]:
                best_result = generation_best

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
                    "champion_genome": best_result["genome"],
                }
            )

        summary = {
            "config": asdict(self.config),
            "best_genome": best_result["genome"],
            "best_training_score": best_result["score"],
            "best_training_win_rate": best_result["win_rate"],
            "validation": validate_genome(PolicyGenome(**best_result["genome"]), self.config),
            "history": history,
            "parameter_guide": PARAMETER_GUIDE,
            "opponent_pool": [name for name, _ in OPPONENT_POOL],
        }

        if self.config.save_artifacts:
            run_dir = self._write_artifacts(summary)
            summary["run_dir"] = str(run_dir)
        return summary

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
                    "genome": summary["best_genome"],
                    "parameter_guide": PARAMETER_GUIDE,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return run_dir
