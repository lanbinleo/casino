"""Baseline policies for the Fire Station environment."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, Mapping, Sequence

from .env import Action, ActionType, Observation


def normalize_distribution(weights: Mapping[Action, float]) -> Dict[Action, float]:
    positive = {action: max(float(weight), 0.0) for action, weight in weights.items()}
    total = sum(positive.values())
    if total <= 0:
        uniform = 1.0 / max(len(positive), 1)
        return {action: uniform for action in positive}
    return {action: value / total for action, value in positive.items()}


def sample_action(weights: Mapping[Action, float], rng: random.Random) -> Action:
    normalized = normalize_distribution(weights)
    roll = rng.random()
    running = 0.0
    last_action = next(iter(normalized))
    for action, probability in normalized.items():
        running += probability
        last_action = action
        if roll <= running:
            return action
    return last_action


class RandomPolicy:
    name = "random"

    def action_distribution(self, observation: Observation, legal_actions: Sequence[Action]) -> Dict[Action, float]:
        if not legal_actions:
            return {}
        return {action: 1.0 for action in legal_actions}

    def act(self, observation: Observation, legal_actions: Sequence[Action], rng: random.Random) -> Action:
        return sample_action(self.action_distribution(observation, legal_actions), rng)


@dataclass
class HeuristicPolicy:
    """A stronger non-neural baseline."""

    personality: str = "tight"
    mood: float = 0.5
    boss: bool = False
    cycle: int = 0
    name: str = "heuristic"

    def _base_action_weights(self, strength: float) -> Dict[str, float]:
        if strength >= 0.75:
            return {"raise": 0.80, "call": 0.18, "fold": 0.02}
        if strength >= 0.50:
            return {"raise": 0.35, "call": 0.45, "fold": 0.20}
        if strength >= 0.25:
            return {"raise": 0.15, "call": 0.30, "fold": 0.55}
        return {"raise": 0.08, "call": 0.15, "fold": 0.77}

    def action_distribution(self, observation: Observation, legal_actions: Sequence[Action]) -> Dict[Action, float]:
        if not legal_actions:
            return {}

        strength = observation.private_strength
        aggression = observation.opponent_profile.get("aggression", 0.5)
        weights = self._base_action_weights(strength)

        if observation.opponent_raises >= 2 and strength < 0.5:
            weights["fold"] += 0.20
            weights["raise"] -= 0.10

        if aggression > 0.7 and strength >= 0.3:
            weights["call"] += 0.15
            weights["fold"] -= 0.15

        if self.personality == "tricky":
            bluff_chance = 0.18
        elif self.personality == "loose":
            bluff_chance = 0.12
        else:
            bluff_chance = 0.06

        if aggression < 0.35:
            bluff_chance *= 1.8

        if strength < 0.4:
            weights["raise"] += bluff_chance * 0.8
            weights["fold"] -= bluff_chance * 0.6

        if self.personality == "tight":
            weights["fold"] += 0.08
            weights["raise"] -= 0.05
        elif self.personality == "loose":
            weights["raise"] += 0.10
            weights["fold"] -= 0.08

        weights["raise"] += (self.mood - 0.5) * 0.15
        weights["fold"] -= (self.mood - 0.5) * 0.10

        if observation.my_chips < observation.current_bet * 3 and strength < 0.6:
            weights["fold"] += 0.25
            weights["raise"] -= 0.20

        if observation.pot > observation.my_chips * 0.3 and observation.round_num >= 2:
            weights["fold"] *= 0.5
            weights["call"] += 0.15

        if observation.round_num >= 3:
            weights["call"] += 0.15
            weights["raise"] -= 0.10

        if self.boss:
            weights["raise"] += 0.08
            weights["fold"] -= 0.06
        if self.cycle > 0:
            weights["raise"] += min(0.04 * self.cycle, 0.16)
            weights["fold"] -= min(0.03 * self.cycle, 0.12)

        for key in weights:
            weights[key] = max(weights[key], 0.01)

        distribution: Dict[Action, float] = {}
        raise_actions = [action for action in legal_actions if action.kind not in {ActionType.CALL, ActionType.FOLD}]
        call_action = next((action for action in legal_actions if action.kind == ActionType.CALL), None)
        fold_action = next((action for action in legal_actions if action.kind == ActionType.FOLD), None)

        if call_action is not None:
            distribution[call_action] = weights["call"]
        if fold_action is not None:
            distribution[fold_action] = weights["fold"]

        if raise_actions:
            raise_bucket = self._raise_bucket_weights(strength, raise_actions)
            for action, value in raise_bucket.items():
                distribution[action] = weights["raise"] * value

        return normalize_distribution(distribution)

    def _raise_bucket_weights(
        self,
        strength: float,
        raise_actions: Sequence[Action],
    ) -> Dict[Action, float]:
        kind_bias = {}
        for action in raise_actions:
            if action.kind == ActionType.MIN_RAISE:
                base = 1.2 if strength >= 0.75 else 1.0
            elif action.kind == ActionType.DOUBLE_RAISE:
                base = 1.0 if strength >= 0.5 else 0.7
            elif action.kind == ActionType.PRESSURE_RAISE:
                base = 0.8 if strength >= 0.65 else 1.0
            elif action.kind == ActionType.ALL_IN:
                base = 0.2 if strength < 0.8 else 0.8
            else:
                base = 1.0
            kind_bias[action] = base
        return normalize_distribution(kind_bias)

    def act(self, observation: Observation, legal_actions: Sequence[Action], rng: random.Random) -> Action:
        return sample_action(self.action_distribution(observation, legal_actions), rng)


@dataclass
class DifficultyPolicy:
    """Wrap a stronger policy and degrade it in controlled ways."""

    base_policy: HeuristicPolicy
    temperature: float = 1.0
    random_mix: float = 0.0
    mistake_mix: float = 0.0
    name: str = "difficulty_wrapper"

    @classmethod
    def for_level(cls, base_policy: HeuristicPolicy, level: str) -> "DifficultyPolicy":
        level = level.lower().strip()
        if level == "easy":
            return cls(base_policy=base_policy, temperature=1.45, random_mix=0.30, mistake_mix=0.25, name="easy")
        if level == "normal":
            return cls(base_policy=base_policy, temperature=1.10, random_mix=0.12, mistake_mix=0.08, name="normal")
        if level == "hard":
            return cls(base_policy=base_policy, temperature=0.90, random_mix=0.03, mistake_mix=0.02, name="hard")
        raise ValueError(f"Unknown difficulty level: {level}")

    def action_distribution(self, observation: Observation, legal_actions: Sequence[Action]) -> Dict[Action, float]:
        base_distribution = self.base_policy.action_distribution(observation, legal_actions)
        if not base_distribution:
            return {}

        uniform = {action: 1.0 for action in legal_actions}
        inverse = {}
        for action, probability in base_distribution.items():
            inverse[action] = 1.0 / max(probability, 1e-6)

        base_distribution = normalize_distribution(base_distribution)
        uniform = normalize_distribution(uniform)
        inverse = normalize_distribution(inverse)

        mixed: Dict[Action, float] = {}
        stable_weight = max(0.0, 1.0 - self.random_mix - self.mistake_mix)
        for action in legal_actions:
            mixed[action] = (
                stable_weight * base_distribution.get(action, 0.0)
                + self.random_mix * uniform.get(action, 0.0)
                + self.mistake_mix * inverse.get(action, 0.0)
            )

        if math.isclose(self.temperature, 1.0, rel_tol=1e-6):
            return normalize_distribution(mixed)

        adjusted = {}
        exponent = 1.0 / max(self.temperature, 1e-6)
        for action, probability in mixed.items():
            adjusted[action] = max(probability, 1e-6) ** exponent
        return normalize_distribution(adjusted)

    def act(self, observation: Observation, legal_actions: Sequence[Action], rng: random.Random) -> Action:
        return sample_action(self.action_distribution(observation, legal_actions), rng)
