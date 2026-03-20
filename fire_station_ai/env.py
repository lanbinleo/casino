"""Pure game environment for the Fire Station mini-game.

This module extracts the hand-level rules from ``casino.py`` so we can:

1. run self-play without terminal IO
2. plug in rule agents, search agents, or neural models later
3. bridge the trained policy back into the main game with a thin adapter
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


RANK_LABELS = {
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
    9: "9",
    10: "10",
    11: "J",
    12: "Q",
    13: "K",
    14: "A",
}


class Seat(IntEnum):
    PLAYER = 0
    OPPONENT = 1

    @property
    def other(self) -> "Seat":
        return Seat.OPPONENT if self == Seat.PLAYER else Seat.PLAYER


class ActionType(str, Enum):
    FOLD = "fold"
    CALL = "call"
    MIN_RAISE = "min_raise"
    DOUBLE_RAISE = "double_raise"
    PRESSURE_RAISE = "pressure_raise"
    ALL_IN = "all_in"
    RAISE_AMOUNT = "raise_amount"


@dataclass(frozen=True)
class Action:
    kind: ActionType
    amount: Optional[int] = None

    def label(self) -> str:
        if self.amount is None:
            return self.kind.value
        return f"{self.kind.value}:{self.amount}"


@dataclass
class PlayerProfile:
    total_hands: int = 0
    fold_count: int = 0
    bluff_caught: int = 0
    raise_freq: List[int] = field(default_factory=list)
    showdown_cards: List[float] = field(default_factory=list)

    def strength_from_rank(self, rank: int) -> float:
        return (rank - 2) / 12

    def record_hand(
        self,
        folded: bool,
        raises: int,
        showdown_rank: Optional[int] = None,
        weak_bluff_punished: bool = False,
    ) -> None:
        self.total_hands += 1
        if folded:
            self.fold_count += 1
        self.raise_freq.append(int(raises))
        self.raise_freq = self.raise_freq[-20:]
        if showdown_rank is not None:
            self.showdown_cards.append(self.strength_from_rank(showdown_rank))
            self.showdown_cards = self.showdown_cards[-20:]
        if weak_bluff_punished:
            self.bluff_caught += 1

    def summary(self) -> Dict[str, float]:
        if self.total_hands <= 0:
            return {
                "hands_seen": 0.0,
                "fold_rate": 0.5,
                "avg_raises_last10": 0.0,
                "avg_showdown_strength": 0.5,
                "aggression": 0.5,
                "bluff_caught_rate": 0.0,
            }

        fold_rate = self.fold_count / max(self.total_hands, 1)
        recent_raises = self.raise_freq[-10:]
        avg_raises = sum(recent_raises) / max(len(recent_raises), 1)
        avg_showdown_strength = sum(self.showdown_cards[-10:]) / max(len(self.showdown_cards[-10:]), 1)
        aggression = (1.0 - fold_rate) * 0.4 + min(avg_raises / 4.0, 1.0) * 0.6
        bluff_caught_rate = self.bluff_caught / max(self.total_hands, 1)
        return {
            "hands_seen": float(self.total_hands),
            "fold_rate": float(fold_rate),
            "avg_raises_last10": float(avg_raises),
            "avg_showdown_strength": float(avg_showdown_strength),
            "aggression": float(aggression),
            "bluff_caught_rate": float(bluff_caught_rate),
        }

    @classmethod
    def from_casino_dict(cls, data: Optional[Dict[str, Any]]) -> "PlayerProfile":
        if not isinstance(data, dict):
            return cls()
        return cls(
            total_hands=int(data.get("total_hands", 0)),
            fold_count=int(data.get("fold_count", 0)),
            bluff_caught=int(data.get("bluff_caught", 0)),
            raise_freq=[int(v) for v in data.get("raise_freq", [])][-20:],
            showdown_cards=[float(v) for v in data.get("showdown_cards", [])][-20:],
        )

    def to_casino_dict(self) -> Dict[str, Any]:
        return {
            "total_hands": int(self.total_hands),
            "fold_count": int(self.fold_count),
            "bluff_caught": int(self.bluff_caught),
            "raise_freq": list(self.raise_freq[-20:]),
            "showdown_cards": list(self.showdown_cards[-20:]),
        }


@dataclass
class Observation:
    seat: Seat
    private_rank: int
    private_strength: float
    my_chips: int
    opponent_chips: int
    pot: int
    current_bet: int
    round_num: int
    my_raises: int
    opponent_raises: int
    last_raiser: Optional[Seat]
    can_raise: bool
    call_uses_credit: bool
    my_profile: Dict[str, float]
    opponent_profile: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seat": self.seat.value,
            "private_rank": self.private_rank,
            "private_strength": self.private_strength,
            "my_chips": self.my_chips,
            "opponent_chips": self.opponent_chips,
            "pot": self.pot,
            "current_bet": self.current_bet,
            "round_num": self.round_num,
            "my_raises": self.my_raises,
            "opponent_raises": self.opponent_raises,
            "last_raiser": None if self.last_raiser is None else self.last_raiser.value,
            "can_raise": self.can_raise,
            "call_uses_credit": self.call_uses_credit,
            "my_profile": dict(self.my_profile),
            "opponent_profile": dict(self.opponent_profile),
        }


@dataclass
class FireStationState:
    base_bet: int
    pot: int
    current_bet: int
    stacks: List[int]
    initial_stacks: Tuple[int, int]
    cards: Tuple[int, int]
    to_act: Optional[Seat]
    last_raiser: Optional[Seat]
    round_num: int
    raises: List[int]
    terminal: bool = False
    winner: Optional[Seat] = None
    win_reason: Optional[str] = None
    profiles: List[PlayerProfile] = field(default_factory=lambda: [PlayerProfile(), PlayerProfile()])
    action_history: List[Dict[str, Any]] = field(default_factory=list)

    def visible_cards(self, reveal_all: bool = False) -> Dict[str, Optional[str]]:
        if reveal_all:
            return {
                "player": RANK_LABELS[self.cards[Seat.PLAYER]],
                "opponent": RANK_LABELS[self.cards[Seat.OPPONENT]],
            }
        return {
            "player": RANK_LABELS[self.cards[Seat.PLAYER]],
            "opponent": None,
        }


@dataclass
class StepResult:
    state: FireStationState
    legal_actions: List[Action]
    next_actor: Optional[Seat]
    terminal: bool
    rewards: Tuple[int, int]
    info: Dict[str, Any] = field(default_factory=dict)


class FireStationEnv:
    """Pure hand simulator.

    The environment is faithful to the current mini-game with one deliberate
    extension: we can decide which seats are allowed to "call on credit".
    The terminal version currently allows the human player to do that.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        allow_credit_call_for: Iterable[Seat] = (Seat.PLAYER,),
    ) -> None:
        self.rng = random.Random(seed)
        self.allow_credit_call_for = set(allow_credit_call_for)
        self.state: Optional[FireStationState] = None

    @staticmethod
    def rank_strength(rank: int) -> float:
        return (rank - 2) / 12

    @staticmethod
    def normalize_rank(value: Any) -> int:
        if isinstance(value, int):
            if value < 2 or value > 14:
                raise ValueError(f"Rank out of range: {value}")
            return value
        text = str(value).strip().upper()
        mapping = {
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "7": 7,
            "8": 8,
            "9": 9,
            "10": 10,
            "J": 11,
            "Q": 12,
            "K": 13,
            "A": 14,
        }
        if text not in mapping:
            raise ValueError(f"Unknown rank: {value}")
        return mapping[text]

    def _fresh_deck(self) -> List[int]:
        deck = [rank for rank in range(2, 15) for _ in range(4)]
        self.rng.shuffle(deck)
        return deck

    def reset(
        self,
        base_bet: int,
        stacks: Sequence[int] = (1000, 1000),
        profiles: Optional[Sequence[PlayerProfile]] = None,
        first_actor: Seat = Seat.PLAYER,
        forced_cards: Optional[Sequence[Any]] = None,
    ) -> FireStationState:
        if len(stacks) != 2:
            raise ValueError("stacks must contain exactly two seats")
        player_stack, opponent_stack = int(stacks[0]), int(stacks[1])
        if base_bet <= 0:
            raise ValueError("base_bet must be positive")
        if player_stack < base_bet or opponent_stack < base_bet:
            raise ValueError("both seats must be able to post the base bet")

        if profiles is None:
            active_profiles = [PlayerProfile(), PlayerProfile()]
        else:
            if len(profiles) != 2:
                raise ValueError("profiles must contain exactly two seats")
            active_profiles = [profiles[0], profiles[1]]

        if forced_cards is not None:
            if len(forced_cards) != 2:
                raise ValueError("forced_cards must contain exactly two ranks")
            cards = (
                self.normalize_rank(forced_cards[0]),
                self.normalize_rank(forced_cards[1]),
            )
        else:
            deck = self._fresh_deck()
            cards = (deck.pop(), deck.pop())

        posted_stacks = [player_stack - base_bet, opponent_stack - base_bet]
        self.state = FireStationState(
            base_bet=int(base_bet),
            pot=int(base_bet * 2),
            current_bet=int(base_bet),
            stacks=posted_stacks,
            initial_stacks=(player_stack, opponent_stack),
            cards=cards,
            to_act=Seat(first_actor),
            last_raiser=None,
            round_num=0,
            raises=[0, 0],
            profiles=active_profiles,
            action_history=[
                {
                    "event": "hand_start",
                    "base_bet": int(base_bet),
                    "initial_stacks": [player_stack, opponent_stack],
                    "cards": {
                        "player": RANK_LABELS[cards[Seat.PLAYER]],
                        "opponent": RANK_LABELS[cards[Seat.OPPONENT]],
                    },
                }
            ],
        )
        return self.state

    def _require_state(self) -> FireStationState:
        if self.state is None:
            raise RuntimeError("Call reset() before using the environment")
        return self.state

    def _can_use_credit_call(self, seat: Seat) -> bool:
        return seat in self.allow_credit_call_for

    def _call_shortfall(self, seat: Seat) -> int:
        state = self._require_state()
        return max(0, state.current_bet - state.stacks[seat])

    def observation(self, seat: Seat) -> Observation:
        state = self._require_state()
        other = seat.other
        return Observation(
            seat=seat,
            private_rank=state.cards[seat],
            private_strength=self.rank_strength(state.cards[seat]),
            my_chips=state.stacks[seat],
            opponent_chips=state.stacks[other],
            pot=state.pot,
            current_bet=state.current_bet,
            round_num=state.round_num,
            my_raises=state.raises[seat],
            opponent_raises=state.raises[other],
            last_raiser=state.last_raiser,
            can_raise=state.stacks[seat] >= state.current_bet,
            call_uses_credit=self._call_shortfall(seat) > 0,
            my_profile=state.profiles[seat].summary(),
            opponent_profile=state.profiles[other].summary(),
        )

    def _raise_options(self, seat: Seat) -> List[Action]:
        state = self._require_state()
        chips = state.stacks[seat]
        if chips < state.current_bet:
            return []

        candidates = [
            (ActionType.MIN_RAISE, state.current_bet),
            (ActionType.DOUBLE_RAISE, state.current_bet * 2),
            (ActionType.PRESSURE_RAISE, max(state.current_bet * 3, state.pot // 2, state.current_bet)),
            (ActionType.ALL_IN, chips),
        ]

        unique_amounts = set()
        options: List[Action] = []
        for kind, amount in candidates:
            amount = max(state.current_bet, min(chips, int(amount)))
            if amount in unique_amounts:
                continue
            unique_amounts.add(amount)
            options.append(Action(kind=kind, amount=amount))
        return options

    def legal_actions(self, seat: Optional[Seat] = None) -> List[Action]:
        state = self._require_state()
        acting_seat = state.to_act if seat is None else Seat(seat)
        if state.terminal or acting_seat != state.to_act:
            return []

        actions: List[Action] = []
        if state.last_raiser in (None, acting_seat.other):
            shortfall = self._call_shortfall(acting_seat)
            if shortfall == 0 or self._can_use_credit_call(acting_seat):
                actions.append(Action(ActionType.CALL))
        actions.extend(self._raise_options(acting_seat))
        actions.append(Action(ActionType.FOLD))
        return actions

    def _resolve_action(self, seat: Seat, action: Action) -> Action:
        state = self._require_state()
        if action.kind == ActionType.RAISE_AMOUNT:
            if action.amount is None:
                raise ValueError("RAISE_AMOUNT requires an explicit amount")
            if state.stacks[seat] < state.current_bet:
                raise ValueError("seat cannot raise because it cannot cover the minimum raise")
            amount = int(action.amount)
            if amount < state.current_bet or amount > state.stacks[seat]:
                raise ValueError("raise amount outside legal range")
            return Action(ActionType.RAISE_AMOUNT, amount=amount)

        if action.kind in {
            ActionType.FOLD,
            ActionType.CALL,
            ActionType.MIN_RAISE,
            ActionType.DOUBLE_RAISE,
            ActionType.PRESSURE_RAISE,
            ActionType.ALL_IN,
        }:
            if action.kind in {ActionType.MIN_RAISE, ActionType.DOUBLE_RAISE, ActionType.PRESSURE_RAISE, ActionType.ALL_IN}:
                for legal in self._raise_options(seat):
                    if legal.kind == action.kind:
                        return legal
                raise ValueError(f"Illegal raise action for current state: {action.kind}")
            return Action(action.kind, amount=None)

        raise ValueError(f"Unknown action kind: {action.kind}")

    def _final_rewards(self, state: FireStationState) -> Tuple[int, int]:
        return (
            state.stacks[Seat.PLAYER] - state.initial_stacks[Seat.PLAYER],
            state.stacks[Seat.OPPONENT] - state.initial_stacks[Seat.OPPONENT],
        )

    def _update_profiles(self, state: FireStationState) -> None:
        loser = None
        if state.terminal and state.winner is not None:
            loser = state.winner.other

        showdown = state.win_reason == "showdown"
        for seat in (Seat.PLAYER, Seat.OPPONENT):
            profile = state.profiles[seat]
            own_rank = state.cards[seat]
            weak_bluff_punished = bool(
                showdown
                and loser == seat
                and state.raises[seat] > 0
                and self.rank_strength(own_rank) < 0.35
            )
            profile.record_hand(
                folded=state.win_reason == "fold" and loser == seat,
                raises=state.raises[seat],
                showdown_rank=own_rank if showdown else None,
                weak_bluff_punished=weak_bluff_punished,
            )

    def _finish_fold(self, folding_seat: Seat) -> StepResult:
        state = self._require_state()
        winner = folding_seat.other
        state.stacks[winner] += state.pot
        state.terminal = True
        state.winner = winner
        state.win_reason = "fold"
        state.to_act = None
        self._update_profiles(state)
        rewards = self._final_rewards(state)
        info = {
            "winner": winner.value,
            "reason": "fold",
            "pot": state.pot,
            "revealed_cards": state.visible_cards(reveal_all=False),
            "final_stacks": list(state.stacks),
        }
        return StepResult(
            state=state,
            legal_actions=[],
            next_actor=None,
            terminal=True,
            rewards=rewards,
            info=info,
        )

    def _finish_showdown(self) -> StepResult:
        state = self._require_state()
        player_rank = state.cards[Seat.PLAYER]
        opponent_rank = state.cards[Seat.OPPONENT]

        if player_rank > opponent_rank:
            state.stacks[Seat.PLAYER] += state.pot
            state.winner = Seat.PLAYER
        elif player_rank < opponent_rank:
            state.stacks[Seat.OPPONENT] += state.pot
            state.winner = Seat.OPPONENT
        else:
            player_share = state.pot // 2
            opponent_share = state.pot - player_share
            state.stacks[Seat.PLAYER] += player_share
            state.stacks[Seat.OPPONENT] += opponent_share
            state.winner = None

        state.terminal = True
        state.win_reason = "showdown"
        state.to_act = None
        self._update_profiles(state)
        rewards = self._final_rewards(state)
        info = {
            "winner": None if state.winner is None else state.winner.value,
            "reason": "showdown",
            "pot": state.pot,
            "revealed_cards": state.visible_cards(reveal_all=True),
            "final_stacks": list(state.stacks),
        }
        return StepResult(
            state=state,
            legal_actions=[],
            next_actor=None,
            terminal=True,
            rewards=rewards,
            info=info,
        )

    def step(self, action: Action, seat: Optional[Seat] = None) -> StepResult:
        state = self._require_state()
        if state.terminal:
            raise RuntimeError("Cannot step a finished hand")

        acting_seat = state.to_act if seat is None else Seat(seat)
        if acting_seat != state.to_act:
            raise ValueError(f"It is not seat {acting_seat}'s turn")

        legal = self.legal_actions(acting_seat)
        resolved = self._resolve_action(acting_seat, action)

        if resolved.kind != ActionType.RAISE_AMOUNT and not any(
            legal_action.kind == resolved.kind and legal_action.amount == resolved.amount
            for legal_action in legal
        ):
            raise ValueError(f"Illegal action for current state: {resolved}")

        other = acting_seat.other
        state.round_num += 1

        if resolved.kind == ActionType.FOLD:
            state.action_history.append(
                {
                    "turn": state.round_num,
                    "seat": acting_seat.value,
                    "action": "fold",
                    "pot_after": state.pot,
                }
            )
            return self._finish_fold(acting_seat)

        if resolved.kind == ActionType.CALL:
            if state.last_raiser == other:
                shortfall = self._call_shortfall(acting_seat)
                if shortfall > 0 and not self._can_use_credit_call(acting_seat):
                    raise ValueError("seat cannot call because it cannot cover the current bet")
                state.stacks[acting_seat] -= state.current_bet
                state.pot += state.current_bet

            state.action_history.append(
                {
                    "turn": state.round_num,
                    "seat": acting_seat.value,
                    "action": "call" if state.last_raiser == other else "showdown",
                    "amount": state.current_bet if state.last_raiser == other else 0,
                    "pot_after": state.pot,
                }
            )
            return self._finish_showdown()

        raise_amount = resolved.amount
        if raise_amount is None:
            raise ValueError("Raise action must resolve to a concrete amount")
        if state.stacks[acting_seat] < raise_amount:
            raise ValueError("seat cannot cover the chosen raise amount")

        state.stacks[acting_seat] -= raise_amount
        state.pot += raise_amount
        state.current_bet = raise_amount
        state.raises[acting_seat] += 1
        state.last_raiser = acting_seat
        state.to_act = other
        state.action_history.append(
            {
                "turn": state.round_num,
                "seat": acting_seat.value,
                "action": "raise",
                "raise_kind": resolved.kind.value,
                "amount": raise_amount,
                "pot_after": state.pot,
            }
        )

        return StepResult(
            state=state,
            legal_actions=self.legal_actions(other),
            next_actor=other,
            terminal=False,
            rewards=(0, 0),
            info={
                "resolved_action": resolved.label(),
                "pot": state.pot,
                "current_bet": state.current_bet,
                "stacks": list(state.stacks),
            },
        )
