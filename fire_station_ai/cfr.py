"""Chance-sampled CFR trainer and runtime policy for Fire Station."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .env import Action, ActionType, FireStationEnv, Observation, Seat
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


def cards_to_key(cards: Sequence[int]) -> str:
    return f"{int(cards[0])}-{int(cards[1])}"


def abstraction_key(observation: Observation) -> str:
    stack_pressure = observation.current_bet / max(observation.my_chips + observation.current_bet, 1)
    pot_pressure = observation.pot / max(observation.my_chips + observation.opponent_chips + observation.pot, 1)
    stack_ratio = observation.my_chips / max(observation.current_bet, 1)
    opp_stack_ratio = observation.opponent_chips / max(observation.current_bet, 1)
    aggression_delta = max(-2, min(2, observation.opponent_raises - observation.my_raises))
    last_raiser = "none"
    if observation.last_raiser == observation.seat:
        last_raiser = "self"
    elif observation.last_raiser == observation.seat.other:
        last_raiser = "opp"

    return "|".join(
        [
            f"seat{int(observation.seat)}",
            f"rank{int(observation.private_rank)}",
            f"round{_clamp_index(int(observation.round_num), 6)}",
            f"spr{bucketize(stack_pressure, (0.08, 0.16, 0.28, 0.45, 0.70))}",
            f"pot{bucketize(pot_pressure, (0.10, 0.20, 0.35, 0.50, 0.70))}",
            f"stk{bucketize(stack_ratio, (1.2, 2.0, 4.0, 8.0, 16.0))}",
            f"opp{bucketize(opp_stack_ratio, (1.2, 2.0, 4.0, 8.0, 16.0))}",
            f"agg{aggression_delta + 2}",
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
            mixed[action] = blended.get(action, 0.0) * 0.90 + prior.get(action, 0.0) * 0.10
        return normalize_distribution(mixed)

    def act(self, observation: Observation, legal_actions: Sequence[Action], rng: random.Random) -> Action:
        return sample_action(self.action_distribution(observation, legal_actions), rng)


@dataclass
class CFRTrainerConfig:
    iterations: int = 60
    checkpoint_interval: int = 10
    hands_per_eval: int = 24
    validation_hands: int = 40
    eval_repeats: int = 1
    validation_repeats: int = 1
    bet_set: Tuple[int, ...] = (10, 25)
    validation_bet_set: Tuple[int, ...] = (10, 25)
    stack_set: Tuple[int, ...] = (800, 1000, 1400)
    max_round_depth: int = 8
    seed: int = 7
    output_dir: str = "fire_station_ai/runs"
    save_artifacts: bool = True
    show_progress: bool = True


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
                training = self._evaluate_policy(policy, self.config.hands_per_eval, self.config.bet_set, self.config.eval_repeats)
                validation = self._validate_policy(policy)
                improved = False
                if self.best_checkpoint is None or validation["score_per_scheduled_hand"] > self.best_checkpoint["validation"]["score_per_scheduled_hand"]:
                    improved = True
                    model_name = generate_codename(self.rng, used=used_codenames)
                    used_codenames.add(model_name)
                    self.best_checkpoint = {
                        "iteration": iteration,
                        "model_name": model_name,
                        "policy": policy,
                        "training": training,
                        "validation": validation,
                    }
                history.append(
                    {
                        "iteration": iteration,
                        "info_set_count": len(self.nodes),
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
            "best_training_score": best_training["score"],
            "best_training_win_rate": best_training["win_rate"],
            "best_training_breakdown": best_training["per_opponent"],
            "validation": best_validation,
            "history": history,
            "info_set_count": len(self.nodes),
            "average_strategy_table_size": len(best_policy.strategy_table),
            "action_guide": ACTION_GUIDE,
            "abstraction_notes_zh": [
                "CFR 按抽样发牌进行自博弈，每次只训练一手牌的博弈树。",
                "信息集使用手牌、回合、下注压力、底池压力和加注差做离散抽象。",
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
            next_env = deepcopy(env)
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

    def _showdown_utility(self, state) -> float:
        player_rank = state.cards[Seat.PLAYER]
        opponent_rank = state.cards[Seat.OPPONENT]
        if player_rank > opponent_rank:
            return float(state.pot)
        if player_rank < opponent_rank:
            return float(-state.pot)
        return 0.0

    def _evaluate_policy(
        self,
        policy: CFRPolicy,
        hands: int,
        bet_set: Sequence[int],
        repeats: int,
    ) -> Dict[str, Any]:
        scores = []
        per_opponent = {}
        total_wins = 0
        total_losses = 0
        total_ties = 0

        for opponent_index, (label, opponent) in enumerate(BASE_OPPONENT_POOL):
            opponent_scores = []
            opponent_wins = 0
            opponent_losses = 0
            opponent_ties = 0
            opponent_hands = 0

            for bet_index, base_bet in enumerate(bet_set):
                for repeat in range(repeats):
                    stack = self.rng.choice(self.config.stack_set)
                    result = run_match(
                        policy,
                        opponent,
                        hands=hands,
                        base_bet=base_bet,
                        starting_stacks=(stack, stack),
                        seed=self.config.seed + 7001 + opponent_index * 89 + bet_index * 211 + repeat * 23,
                    )
                    score = result.bankroll_delta[0] / max(hands, 1)
                    opponent_scores.append(score)
                    opponent_wins += result.seat0_wins
                    opponent_losses += result.seat1_wins
                    opponent_ties += result.ties
                    opponent_hands += result.hands_played

            mean_score = sum(opponent_scores) / max(len(opponent_scores), 1)
            per_opponent[label] = {
                "score_per_scheduled_hand": mean_score,
                "wins": opponent_wins,
                "losses": opponent_losses,
                "ties": opponent_ties,
                "hands_played": opponent_hands,
                "repeats": repeats,
                "bet_set": list(bet_set),
            }
            scores.append(mean_score)
            total_wins += opponent_wins
            total_losses += opponent_losses
            total_ties += opponent_ties

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
        scores = []
        wins = 0
        losses = 0
        ties = 0
        hands_played = 0
        bankroll_delta = 0

        for bet_index, base_bet in enumerate(self.config.validation_bet_set):
            for repeat in range(self.config.validation_repeats):
                stack = self.rng.choice(self.config.stack_set)
                result = run_match(
                    policy,
                    opponent,
                    hands=self.config.validation_hands,
                    base_bet=base_bet,
                    starting_stacks=(stack, stack),
                    seed=self.config.seed + 17001 + bet_index * 313 + repeat * 29,
                )
                scores.append(result.bankroll_delta[0] / max(self.config.validation_hands, 1))
                wins += result.seat0_wins
                losses += result.seat1_wins
                ties += result.ties
                hands_played += result.hands_played
                bankroll_delta += result.bankroll_delta[0]

        return {
            "score_per_scheduled_hand": sum(scores) / max(len(scores), 1),
            "win_rate": wins / max(hands_played, 1),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "hands": hands_played,
            "bankroll_delta": bankroll_delta,
            "bet_set": list(self.config.validation_bet_set),
            "stack_set": list(self.config.stack_set),
            "repeats": self.config.validation_repeats,
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
            lines.append("当前平均策略还没有在训练池建立优势，通常说明迭代轮数还不够。")

        if summary["info_set_count"] < 300:
            lines.append("当前信息集数量还比较少，抽象比较粗，训练会快但上限也更容易提前碰到。")
        elif summary["info_set_count"] > 1200:
            lines.append("这次信息集已经比较丰富，说明模型开始覆盖更多下注压力和筹码场景。")
        else:
            lines.append("信息集规模适中，属于兼顾速度和泛化的表格策略。")

        weakest_name = min(best_breakdown, key=lambda name: best_breakdown[name]["score_per_scheduled_hand"])
        strongest_name = max(best_breakdown, key=lambda name: best_breakdown[name]["score_per_scheduled_hand"])
        lines.append(
            f"训练池里它最怕的是 {weakest_name}，最能压制的是 {strongest_name}。"
        )
        lines.append("如果你想继续拔高，优先加大 `--iterations`，其次增加 `--stack-set` 和 `--validation-bet-set` 的覆盖范围。")
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
            "info_set_count": summary["info_set_count"],
            "action_guide": ACTION_GUIDE,
            "strategy_table": policy.strategy_table,
        }

        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "best_policy.json").write_text(json.dumps(best_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "insight_zh.txt").write_text("\n".join(summary["auto_commentary_zh"]), encoding="utf-8")
        return run_dir
