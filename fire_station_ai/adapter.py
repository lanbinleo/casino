"""Bridge helpers for integrating the environment back into casino.py."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .env import Action, ActionType, FireStationEnv, PlayerProfile, Seat


def build_env_from_casino(
    *,
    base_bet: int,
    player_chips: int,
    opponent_chips: int,
    player_profile: Optional[Dict[str, Any]] = None,
    opponent_profile: Optional[Dict[str, Any]] = None,
    first_actor: Seat = Seat.PLAYER,
    seed: Optional[int] = None,
    forced_cards: Optional[Sequence[Any]] = None,
    allow_credit_call_for_player: bool = True,
) -> FireStationEnv:
    """Create a pure environment from the main game's current values."""

    allow_credit = (Seat.PLAYER,) if allow_credit_call_for_player else ()
    env = FireStationEnv(seed=seed, allow_credit_call_for=allow_credit)
    profiles = [
        PlayerProfile.from_casino_dict(player_profile),
        PlayerProfile.from_casino_dict(opponent_profile),
    ]
    env.reset(
        base_bet=base_bet,
        stacks=(player_chips, opponent_chips),
        profiles=profiles,
        first_actor=first_actor,
        forced_cards=forced_cards,
    )
    return env


def to_casino_command(action: Action) -> Dict[str, Any]:
    """Convert an environment action into the command shape used by casino.py."""

    if action.kind == ActionType.FOLD:
        return {"action": "fold", "amount": 0}
    if action.kind == ActionType.CALL:
        return {"action": "call", "amount": 0}
    if action.kind in {
        ActionType.MIN_RAISE,
        ActionType.DOUBLE_RAISE,
        ActionType.PRESSURE_RAISE,
        ActionType.ALL_IN,
        ActionType.RAISE_AMOUNT,
    }:
        return {"action": "raise", "amount": int(action.amount or 0)}
    raise ValueError(f"Unsupported action kind: {action.kind}")
