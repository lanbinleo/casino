"""Chance-sampled CFR trainer and runtime policy for Fire Station."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .env import (
    Action,
    ActionType,
    FireStationEnv,
    FireStationState,
    Observation,
    PlayerProfile,
    Seat,
)
from .naming import generate_codename
from .policies import HeuristicPolicy, normalize_distribution, sample_action
from .selfplay import run_match
from .trainer import BASE_OPPONENT_POOL

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - fallback when tqdm is unavailable
    tqdm = None


ACTION_ORDER = (
    ActionType.CALL.value,
    ActionType.MIN_RAISE.value,
    ActionType.DOUBLE_RAISE.value,
    ActionType.PRESSURE_RAISE.value,
    ActionType.ALL_IN.value,
    ActionType.FOLD.value,
)

ACTION_GUIDE = {
    ActionType.CALL.value: "跟注或摊牌",
    ActionType.MIN_RAISE.value: "最小加注",
    ActionType.DOUBLE_RAISE.value: "双倍加注",
    ActionType.PRESSURE_RAISE.value: "压力加注",
    ActionType.ALL_IN.value: "直接压满",
    ActionType.FOLD.value: "弃牌止损",
}


def _clamp_index(index: int, upper: int) -> int:
    return max(0, min(index, upper))


def bucketize(value: float, boundaries: Sequence[float]) -> int:
    for index, boundary in enumerate(boundaries):
        if value <= boundary:
            return index
    return len(boundaries)


def abstraction_key(observation: Observation) -> str:
    stack_pressure = observation.current_bet / max(observation.my_chips + observation.current_bet, 1)
    pot_pressure = observation.pot / max(observation.my_chips + observation.opponent_chips + observation.pot, 1)
    stack_ratio = observation.my_chips / max(observation.current_bet, 1)
    opp_stack_ratio = observation.opponent_chips / max(observation.current_bet, 1)
    aggression_delta = max(-1, min(1, observation.opponent_raises - observation.my_raises))
    last_raiser = "none"
    if observation.last_raiser == observation.seat:
        last_raiser = "self"
    elif observation.last_raiser == observation.seat.other:
        last_raiser = "opp"

    return "|".join(
        [
            f"seat{int(observation.seat)}",
            f"rank{int(observation.private_rank)}",
            f"round{_clamp_index(int(observation.round_num), 5)}",
            f"spr{bucketize(stack_pressure, (0.10, 0.22, 0.40, 0.65))}",
            f"pot{bucketize(pot_pressure, (0.12, 0.25, 0.45, 0.70))}",
            f"stk{bucketize(stack_ratio, (1.5, 3.0, 6.0, 12.0))}",
            f"opp{bucketize(opp_stack_ratio, (1.5, 3.0, 6.0, 12.0))}",
            f"agg{aggression_delta + 1}",
            f"lr{last_raiser}",
        ]
    )


def action_to_key(action: Action) -> str:
    return action.kind.value


def legal_action_keys(legal_actions: Sequence[Action]) -> List[str]:
    return [action_to_key(action) for action in legal_actions]


def default_action_prior(observation: Observation, legal_actions: Sequence[Action]) -> Dict[Action, float]:
    strength = observation.private_strength
    weights: Dict[Action, float] = {}
    for action in legal_actions:
        if action.kind == ActionType.CALL:
            weight = 0.55 if strength >= 0.45 else 0.22
        elif action.kind == ActionType.FOLD:
            weight = 0.06 if strength >= 0.60 else 0.65 if strength < 0.30 else 0.28
        elif action.kind == ActionType.MIN_RAISE:
            weight = 0.55 if strength >= 0.72 else 0.18
        elif action.kind == ActionType.DOUBLE_RAISE:
            weight = 0.42 if strength >= 0.78 else 0.10
        elif action.kind == ActionType.PRESSURE_RAISE:
            weight = 0.20 if strength >= 0.62 else 0.08
        elif action.kind == ActionType.ALL_IN:
            weight = 0.25 if strength >= 0.88 else 0.03
        else:
            weight = 0.10
        weights[action] = max(weight, 0.01)
    return normalize_distribution(weights)


def _clone_profile(profile: PlayerProfile) -> PlayerProfile:
    return PlayerProfile(
        total_hands=int(profile.total_hands),
        fold_count=int(profile.fold_count),
        bluff_caught=int(profile.bluff_caught),
        raise_freq=list(profile.raise_freq),
        showdown_cards=list(profile.showdown_cards),
    )


def clone_env(env: FireStationEnv) -> FireStationEnv:
    cloned = FireStationEnv(allow_credit_call_for=tuple(env.allow_credit_call_for))
    state = env.state
    if state is None:
        cloned.state = None
        return cloned
    cloned.state = FireStationState(
        base_bet=int(state.base_bet),
        pot=int(state.pot),
        current_bet=int(state.current_bet),
        stacks=list(state.stacks),
        initial_stacks=tuple(state.initial_stacks),
        cards=tuple(state.cards),
        to_act=None if state.to_act is None else Seat(state.to_act),
        last_raiser=None if state.last_raiser is None else Seat(state.last_raiser),
        round_num=int(state.round_num),
        raises=list(state.raises),
        terminal=bool(state.terminal),
        winner=None if state.winner is None else Seat(state.winner),
        win_reason=state.win_reason,
        profiles=[_clone_profile(profile) for profile in state.profiles],
        action_history=[dict(item) for item in state.action_history],
    )
    return cloned


@dataclass
class CFRNode:
    regret_sum: Dict[str, float] = field(default_factory=dict)
    strategy_sum: Dict[str, float] = field(default_factory=dict)
    visit_count: int = 0

    def current_strategy(self, legal_keys: Sequence[str]) -> Dict[str, float]:
        strategy: Dict[str, float] = {}
        normalizing = 0.0
        for key in legal_keys:
            value = max(0.0, self.regret_sum.get(key, 0.0))
            strategy[key] = value
            normalizing += value
        if normalizing <= 1e-9:
            uniform = 1.0 / max(len(legal_keys), 1)
            return {key: uniform for key in legal_keys}
        return {key: strategy[key] / normalizing for key in legal_keys}

    def average_strategy(self, legal_keys: Sequence[str]) -> Dict[str, float]:
        total = sum(max(0.0, self.strategy_sum.get(key, 0.0)) for key in legal_keys)
        if total <= 1e-9:
            return self.current_strategy(legal_keys)
        return {key: max(0.0, self.strategy_sum.get(key, 0.0)) / total for key in legal_keys}


class CFRPolicy:
    """Runtime policy backed by an average-strategy table."""

    def __init__(
        self,
        strategy_table: Mapping[str, Mapping[str, float]],
        *,
        name: str = "cfr_policy",
        fallback: Optional[HeuristicPolicy] = None,
    ) -> None:
        self.strategy_table = {
            str(info_key): {str(action_key): float(probability) for action_key, probability in action_probs.items()}
            for info_key, action_probs in strategy_table.items()
        }
        self.name = name
        self.fallback = fallback or HeuristicPolicy(personality="tricky", mood=0.58, boss=True)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CFRPolicy":
        strategy_table = payload.get("strategy_table", {}) or {}
        codename = payload.get("model_name") or payload.get("model_codename") or "cfr_policy"
        return cls(strategy_table, name=str(codename))

    def action_distribution(self, observation: Observation, legal_actions: Sequence[Action]) -> Dict[Action, float]:
        if not legal_actions:
            return {}

        info_key = abstraction_key(observation)
        stored = self.strategy_table.get(info_key)
        if not stored:
            return default_action_prior(observation, legal_actions)

        weights: Dict[Action, float] = {}
        for action in legal_actions:
            weights[action] = max(0.0, float(stored.get(action_to_key(action), 0.0)))

        if sum(weights.values()) <= 1e-9:
            return default_action_prior(observation, legal_actions)

        blended = normalize_distribution(weights)
        prior = default_action_prior(observation, legal_actions)
        mixed: Dict[Action, float] = {}
        for action in legal_actions:
            mixed[action] = blended.get(action, 0.0) * 0.92 + prior.get(action, 0.0) * 0.08
        return normalize_distribution(mixed)

    def act(self, observation: Observation, legal_actions: Sequence[Action], rng: random.Random) -> Action:
        return sample_action(self.action_distribution(observation, legal_actions), rng)


@dataclass
class CFRTrainerConfig:
    iterations: int = 60
    checkpoint_interval: int = 10
    hands_per_eval: int = 36
    validation_hands: int = 60
    eval_repeats: int = 2
    validation_repeats: int = 2
    bet_set: Tuple[int, ...] = (10, 25)
    validation_bet_set: Tuple[int, ...] = (10, 25)
    stack_set: Tuple[int, ...] = (800, 1000, 1400)
    max_round_depth: int = 8
    parallel_eval_workers: int = 0
    seed: int = 7
    output_dir: str = "fire_station_ai/runs"
    save_artifacts: bool = True
    show_progress: bool = True


@dataclass(frozen=True)
class _OpponentEvalResult:
    label: str
    scores: Tuple[float, ...]
    wins: int
    losses: int
    ties: int
    hands_played: int


def _auto_worker_count(configured_workers: int, task_count: int) -> int:
    if task_count <= 1:
        return 1
    if configured_workers > 0:
        return min(configured_workers, task_count)
    cpu_count = os.cpu_count() or 1
    return max(1, min(task_count, cpu_count - 1 if cpu_count > 2 else cpu_count))


def _evaluate_single_opponent(
    *,
    label: str,
    policy: CFRPolicy,
    opponent: object,
    hands: int,
    bet_set: Sequence[int],
    stack_set: Sequence[int],
    repeats: int,
    seed_base: int,
) -> _OpponentEvalResult:
    scores: List[float] = []
    wins = 0
    losses = 0
    ties = 0
    hands_played = 0

    for bet_index, base_bet in enumerate(bet_set):
        for stack_index, stack in enumerate(stack_set):
            for repeat in range(repeats):
                seed = seed_base + bet_index * 211 + stack_index * 59 + repeat * 23
                result = run_match(
                    policy,
                    opponent,
                    hands=hands,
                    base_bet=base_bet,
                    starting_stacks=(stack, stack),
                    seed=seed,
                )
                scores.append(result.bankroll_delta[0] / max(hands, 1))
                wins += result.seat0_wins
                losses += result.seat1_wins
                ties += result.ties
                hands_played += result.hands_played

    return _OpponentEvalResult(
        label=label,
        scores=tuple(scores),
        wins=wins,
        losses=losses,
        ties=ties,
        hands_played=hands_played,
    )


def _evaluate_single_opponent_worker(payload: Dict[str, Any]) -> _OpponentEvalResult:
    return _evaluate_single_opponent(**payload)


class CFRTrainer:
    def __init__(self, config: CFRTrainerConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self.nodes: Dict[str, CFRNode] = {}
        self.best_checkpoint: Optional[Dict[str, Any]] = None

    def train(self) -> Dict[str, Any]:
        history: List[Dict[str, Any]] = []
        checkpoint_every = max(1, int(self.config.checkpoint_interval))
        used_codenames = set()
        model_name = generate_codename(self.rng, used=used_codenames)
        used_codenames.add(model_name)

        iteration_bar = self._maybe_tqdm(
            range(1, self.config.iterations + 1),
            total=self.config.iterations,
            desc="CFR 训练进度",
            unit="轮",
        )

        for iteration in iteration_bar:
            base_bet = self.rng.choice(self.config.bet_set)
            stack = self.rng.choice(self.config.stack_set)
            first_actor = Seat.PLAYER if self.rng.random() < 0.5 else Seat.OPPONENT
            cards = self._sample_cards()
            env = FireStationEnv(seed=self.config.seed + iteration, allow_credit_call_for=())
            env.reset(
                base_bet=base_bet,
                stacks=(stack, stack),
                first_actor=first_actor,
                forced_cards=cards,
            )
            self._cfr(env, 1.0, 1.0)

            if iteration % checkpoint_every == 0 or iteration == 1 or iteration == self.config.iterations:
                policy = self.build_average_policy()
                training = self._evaluate_policy(
                    policy,
                    self.config.hands_per_eval,
                    self.config.bet_set,
                    self.config.eval_repeats,
                )
                validation = self._validate_policy(policy)
                checkpoint_rank = self._checkpoint_rank(training, validation)
                improved = False

                if self.best_checkpoint is None or checkpoint_rank > self.best_checkpoint["rank"]:
                    improved = True
                    model_name = generate_codename(self.rng, used=used_codenames)
                    used_codenames.add(model_name)
                    self.best_checkpoint = {
                        "iteration": iteration,
                        "model_name": model_name,
                        "policy": policy,
                        "training": training,
                        "validation": validation,
                        "rank": checkpoint_rank,
                        "info_set_count": len(self.nodes),
                        "strategy_table_size": len(policy.strategy_table),
                    }

                history.append(
                    {
                        "iteration": iteration,
                        "info_set_count": len(self.nodes),
                        "strategy_table_size": len(policy.strategy_table),
                        "training_score": training["score"],
                        "training_win_rate": training["win_rate"],
                        "validation_score": validation["score_per_scheduled_hand"],
                        "validation_win_rate": validation["win_rate"],
                        "champion_changed": improved,
                        "model_name": model_name,
                    }
                )
                if hasattr(iteration_bar, "set_postfix"):
                    iteration_bar.set_postfix(
                        {
                            "训练": f"{training['score']:.3f}",
                            "验证": f"{validation['score_per_scheduled_hand']:.3f}",
                            "信息集": len(self.nodes),
                        }
                    )

        if self.best_checkpoint is None:
            policy = self.build_average_policy()
            training = self._evaluate_policy(policy, self.config.hands_per_eval, self.config.bet_set, self.config.eval_repeats)
            validation = self._validate_policy(policy)
            self.best_checkpoint = {
                "iteration": self.config.iterations,
                "model_name": model_name,
                "policy": policy,
                "training": training,
                "validation": validation,
                "rank": self._checkpoint_rank(training, validation),
                "info_set_count": len(self.nodes),
                "strategy_table_size": len(policy.strategy_table),
            }

        best_policy = self.best_checkpoint["policy"]
        best_training = self.best_checkpoint["training"]
        best_validation = self.best_checkpoint["validation"]

        summary = {
            "policy_type": "cfr_policy",
            "algorithm": "chance_sampled_cfr_regret_matching",
            "config": asdict(self.config),
            "model_name": self.best_checkpoint["model_name"],
            "best_checkpoint_iteration": self.best_checkpoint["iteration"],
            "best_checkpoint_rank": list(self.best_checkpoint["rank"]),
            "best_training_score": best_training["score"],
            "best_training_win_rate": best_training["win_rate"],
            "best_training_breakdown": best_training["per_opponent"],
            "validation": best_validation,
            "history": history,
            "final_info_set_count": len(self.nodes),
            "best_checkpoint_info_set_count": self.best_checkpoint["info_set_count"],
            "average_strategy_table_size": self.best_checkpoint["strategy_table_size"],
            "action_guide": ACTION_GUIDE,
            "abstraction_notes_zh": [
                "CFR 按抽样发牌进行自博弈，每次只训练一手牌的博弈树。",
                "信息集使用手牌、回合、下注压力、底池压力和加注差做离散抽象。",
                "最佳检查点优先比较验证分，再比较验证胜率和训练分，减少被偶然波动误导。",
                "运行时会使用平均策略表，并混入少量先验，避免遇到冷门状态完全失真。",
            ],
        }
        summary["auto_commentary_zh"] = self._build_auto_commentary(summary)

        if self.config.save_artifacts:
            run_dir = self._write_artifacts(summary, best_policy)
            summary["run_dir"] = str(run_dir)
        return summary

    def build_average_policy(self) -> CFRPolicy:
        table: Dict[str, Dict[str, float]] = {}
        for info_key, node in self.nodes.items():
            known_actions = [action_key for action_key in ACTION_ORDER if action_key in node.strategy_sum or action_key in node.regret_sum]
            if not known_actions:
                continue
            table[info_key] = node.average_strategy(known_actions)
        return CFRPolicy(table, name="cfr_average_policy")

    def _sample_cards(self) -> Tuple[int, int]:
        deck = [rank for rank in range(2, 15) for _ in range(4)]
        self.rng.shuffle(deck)
        return deck.pop(), deck.pop()

    def _maybe_tqdm(self, iterable, **kwargs):
        if not self.config.show_progress or tqdm is None:
            return iterable
        kwargs.setdefault("file", sys.stdout)
        kwargs.setdefault("dynamic_ncols", True)
        kwargs.setdefault("mininterval", 0.1)
        return tqdm(iterable, **kwargs)

    def _node_for(self, info_key: str) -> CFRNode:
        node = self.nodes.get(info_key)
        if node is None:
            node = CFRNode()
            self.nodes[info_key] = node
        return node

    def _cfr(self, env: FireStationEnv, reach0: float, reach1: float) -> float:
        state = env.state
        if state is None:
            raise RuntimeError("Environment must be reset before CFR traversal")
        if state.terminal:
            return float(state.stacks[Seat.PLAYER] - state.initial_stacks[Seat.PLAYER])
        if state.round_num >= self.config.max_round_depth:
            return self._showdown_utility(state)

        acting = state.to_act
        observation = env.observation(acting)
        legal_actions = env.legal_actions(acting)
        legal_keys = legal_action_keys(legal_actions)
        info_key = abstraction_key(observation)
        node = self._node_for(info_key)
        node.visit_count += 1
        strategy = node.current_strategy(legal_keys)

        action_utilities: Dict[str, float] = {}
        node_utility = 0.0

        for action in legal_actions:
            action_key = action_to_key(action)
            next_env = clone_env(env)
            next_env.step(action, acting)
            if acting == Seat.PLAYER:
                utility = self._cfr(next_env, reach0 * strategy[action_key], reach1)
            else:
                utility = self._cfr(next_env, reach0, reach1 * strategy[action_key])
            action_utilities[action_key] = utility
            node_utility += strategy[action_key] * utility

        if acting == Seat.PLAYER:
            opponent_reach = reach1
            own_reach = reach0
            for action_key in legal_keys:
                node.regret_sum[action_key] = node.regret_sum.get(action_key, 0.0) + opponent_reach * (action_utilities[action_key] - node_utility)
                node.strategy_sum[action_key] = node.strategy_sum.get(action_key, 0.0) + own_reach * strategy[action_key]
        else:
            opponent_reach = reach0
            own_reach = reach1
            for action_key in legal_keys:
                node.regret_sum[action_key] = node.regret_sum.get(action_key, 0.0) + opponent_reach * (node_utility - action_utilities[action_key])
                node.strategy_sum[action_key] = node.strategy_sum.get(action_key, 0.0) + own_reach * strategy[action_key]

        return node_utility

    def _showdown_utility(self, state: FireStationState) -> float:
        player_rank = state.cards[Seat.PLAYER]
        opponent_rank = state.cards[Seat.OPPONENT]
        if player_rank > opponent_rank:
            return float(state.pot)
        if player_rank < opponent_rank:
            return float(-state.pot)
        return 0.0

    def _checkpoint_rank(self, training: Dict[str, Any], validation: Dict[str, Any]) -> Tuple[float, float, float, float]:
        return (
            round(float(validation["score_per_scheduled_hand"]), 6),
            round(float(validation["win_rate"]), 6),
            round(float(training["score"]), 6),
            round(float(training["win_rate"]), 6),
        )

    def _evaluate_policy(
        self,
        policy: CFRPolicy,
        hands: int,
        bet_set: Sequence[int],
        repeats: int,
    ) -> Dict[str, Any]:
        payloads = []
        for opponent_index, (label, opponent) in enumerate(BASE_OPPONENT_POOL):
            payloads.append(
                {
                    "label": label,
                    "policy": policy,
                    "opponent": opponent,
                    "hands": hands,
                    "bet_set": tuple(bet_set),
                    "stack_set": tuple(self.config.stack_set),
                    "repeats": repeats,
                    "seed_base": self.config.seed + 7001 + opponent_index * 89,
                }
            )

        worker_count = _auto_worker_count(self.config.parallel_eval_workers, len(payloads))
        if worker_count > 1:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                opponent_results = list(executor.map(_evaluate_single_opponent_worker, payloads))
        else:
            opponent_results = [_evaluate_single_opponent_worker(payload) for payload in payloads]

        scores = []
        per_opponent: Dict[str, Dict[str, Any]] = {}
        total_wins = 0
        total_losses = 0
        total_ties = 0

        for result in opponent_results:
            mean_score = sum(result.scores) / max(len(result.scores), 1)
            per_opponent[result.label] = {
                "score_per_scheduled_hand": mean_score,
                "wins": result.wins,
                "losses": result.losses,
                "ties": result.ties,
                "hands_played": result.hands_played,
                "repeats": repeats,
                "bet_set": list(bet_set),
                "stack_set": list(self.config.stack_set),
                "samples": len(result.scores),
            }
            scores.append(mean_score)
            total_wins += result.wins
            total_losses += result.losses
            total_ties += result.ties

        total_hands = total_wins + total_losses + total_ties
        return {
            "score": sum(scores) / max(len(scores), 1),
            "win_rate": total_wins / max(total_hands, 1),
            "wins": total_wins,
            "losses": total_losses,
            "ties": total_ties,
            "per_opponent": per_opponent,
        }

    def _validate_policy(self, policy: CFRPolicy) -> Dict[str, Any]:
        opponent = HeuristicPolicy(personality="tricky", mood=0.62, boss=True, cycle=1)
        result = _evaluate_single_opponent(
            label="validation_boss",
            policy=policy,
            opponent=opponent,
            hands=self.config.validation_hands,
            bet_set=self.config.validation_bet_set,
            stack_set=self.config.stack_set,
            repeats=self.config.validation_repeats,
            seed_base=self.config.seed + 17001,
        )
        score = sum(result.scores) / max(len(result.scores), 1)
        total_hands = result.wins + result.losses + result.ties
        bankroll_delta = int(round(sum(result.scores) * self.config.validation_hands))
        return {
            "score_per_scheduled_hand": score,
            "win_rate": result.wins / max(total_hands, 1),
            "wins": result.wins,
            "losses": result.losses,
            "ties": result.ties,
            "hands": result.hands_played,
            "bankroll_delta": bankroll_delta,
            "bet_set": list(self.config.validation_bet_set),
            "stack_set": list(self.config.stack_set),
            "repeats": self.config.validation_repeats,
            "samples": len(result.scores),
        }

    def _build_auto_commentary(self, summary: Dict[str, Any]) -> List[str]:
        validation = summary["validation"]
        best_breakdown = summary["best_training_breakdown"]
        lines: List[str] = []

        if summary["best_training_score"] > 0 and validation["score_per_scheduled_hand"] > 0:
            lines.append("这版 CFR 平均策略在训练对手和验证对手上都保持正收益，已经有实战价值。")
        elif summary["best_training_score"] > 0:
            lines.append("它已经能针对训练池稳定赚钱，但验证还偏弱，说明策略表还不够成熟。")
        else:
            lines.append("当前平均策略还没有在训练池建立稳定优势，建议继续增加迭代并扩大评估样本。")

        if summary["average_strategy_table_size"] < 300:
            lines.append("当前策略表还比较小，说明模型刚起步，速度快但泛化能力还有限。")
        elif summary["average_strategy_table_size"] > 1800:
            lines.append("这次策略表已经覆盖了不少局面，说明模型开始学到更细的下注压力差异。")
        else:
            lines.append("策略表规模适中，属于兼顾速度和泛化的表格策略。")

        weakest_name = min(best_breakdown, key=lambda name: best_breakdown[name]["score_per_scheduled_hand"])
        strongest_name = max(best_breakdown, key=lambda name: best_breakdown[name]["score_per_scheduled_hand"])
        lines.append(f"训练池里它最怕的是 {weakest_name}，最能压制的是 {strongest_name}。")
        lines.append("这版评估已经覆盖全部 stack_set，而不是每次随机抽一个筹码档位，所以曲线会更稳一些。")
        return lines

    def _write_artifacts(self, summary: Dict[str, Any], policy: CFRPolicy) -> Path:
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / f"cfr_seed{self.config.seed}_iter{self.config.iterations}"
        suffix = 1
        while run_dir.exists():
            suffix += 1
            run_dir = output_dir / f"cfr_seed{self.config.seed}_iter{self.config.iterations}_{suffix}"
        run_dir.mkdir(parents=True, exist_ok=False)

        best_payload = {
            "policy_type": "cfr_policy",
            "algorithm": summary["algorithm"],
            "model_name": summary["model_name"],
            "best_checkpoint_iteration": summary["best_checkpoint_iteration"],
            "best_checkpoint_info_set_count": summary["best_checkpoint_info_set_count"],
            "average_strategy_table_size": summary["average_strategy_table_size"],
            "action_guide": ACTION_GUIDE,
            "strategy_table": policy.strategy_table,
        }

        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "best_policy.json").write_text(json.dumps(best_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "insight_zh.txt").write_text("\n".join(summary["auto_commentary_zh"]), encoding="utf-8")
        return run_dir
