"""Runtime helpers for loading saved policies and using them in the game."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .cfr import CFRPolicy
from .env import Action, ActionType, Observation, PlayerProfile, Seat
from .trainer import GenomePolicy, PolicyGenome


RUNS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def discover_saved_policies(runs_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    root = runs_dir or RUNS_DIR
    if not os.path.isdir(root):
        return []

    discovered: List[Dict[str, Any]] = []
    for dirpath, _, filenames in os.walk(root):
        if "best_policy.json" not in filenames:
            continue

        policy_path = os.path.join(dirpath, "best_policy.json")
        summary_path = os.path.join(dirpath, "summary.json")
        try:
            with open(policy_path, "r", encoding="utf-8") as f:
                policy_payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        summary_payload = {}
        if os.path.exists(summary_path):
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_payload = json.load(f)
            except (OSError, json.JSONDecodeError):
                summary_payload = {}

        codename = (
            policy_payload.get("model_name")
            or policy_payload.get("model_codename")
            or summary_payload.get("model_name")
            or summary_payload.get("model_codename")
            or os.path.basename(dirpath)
        )
        discovered.append(
            {
                "path": policy_path,
                "run_dir": dirpath,
                "codename": codename,
                "policy_type": policy_payload.get("policy_type", "unknown"),
                "best_training_score": _safe_float(summary_payload.get("best_training_score"), 0.0),
                "validation_score": _safe_float(summary_payload.get("validation", {}).get("score_per_scheduled_hand"), 0.0),
                "validation_win_rate": _safe_float(summary_payload.get("validation", {}).get("win_rate"), 0.0),
                "modified_time": os.path.getmtime(policy_path),
            }
        )

    discovered.sort(key=lambda item: item["modified_time"], reverse=True)
    return discovered


def load_saved_policy(policy_path: str) -> Dict[str, Any]:
    with open(policy_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    codename = payload.get("model_name") or payload.get("model_codename")
    if not codename:
        codename = os.path.basename(os.path.dirname(policy_path))
    policy_type = payload.get("policy_type", "genome_policy")
    if policy_type == "cfr_policy":
        policy = CFRPolicy.from_payload(payload)
    else:
        genome = payload.get("genome", {})
        policy = GenomePolicy(PolicyGenome(**genome), name=codename)
    return {
        "path": policy_path,
        "codename": codename,
        "policy_type": policy_type,
        "genome": payload.get("genome", {}),
        "strategy_table": payload.get("strategy_table", {}),
        "policy": policy,
        "payload": payload,
    }


def build_model_observation(
    *,
    card_rank: int,
    my_chips: int,
    opponent_chips: int,
    pot: int,
    current_bet: int,
    round_num: int,
    my_raises: int,
    opponent_raises: int,
    opponent_profile_dict: Optional[Dict[str, Any]] = None,
) -> Observation:
    opponent_profile = PlayerProfile.from_casino_dict(opponent_profile_dict).summary()
    return Observation(
        seat=Seat.OPPONENT,
        private_rank=card_rank,
        private_strength=(card_rank - 2) / 12,
        my_chips=my_chips,
        opponent_chips=opponent_chips,
        pot=pot,
        current_bet=current_bet,
        round_num=round_num,
        my_raises=my_raises,
        opponent_raises=opponent_raises,
        last_raiser=Seat.PLAYER,
        can_raise=my_chips >= current_bet,
        call_uses_credit=False,
        my_profile=PlayerProfile().summary(),
        opponent_profile=opponent_profile,
    )


def build_model_legal_actions(current_bet: int, pot: int, my_chips: int) -> List[Action]:
    actions: List[Action] = []
    if my_chips >= current_bet:
        actions.append(Action(ActionType.CALL))
        candidates = [
            (ActionType.MIN_RAISE, current_bet),
            (ActionType.DOUBLE_RAISE, current_bet * 2),
            (ActionType.PRESSURE_RAISE, max(current_bet * 3, pot // 2, current_bet)),
            (ActionType.ALL_IN, my_chips),
        ]
        seen = set()
        for kind, amount in candidates:
            amount = max(current_bet, min(my_chips, int(amount)))
            if amount in seen:
                continue
            seen.add(amount)
            actions.append(Action(kind=kind, amount=amount))
    actions.append(Action(ActionType.FOLD))
    return actions


def choose_model_action(
    loaded_policy: Dict[str, Any],
    *,
    card_rank: int,
    my_chips: int,
    opponent_chips: int,
    pot: int,
    current_bet: int,
    round_num: int,
    my_raises: int,
    opponent_raises: int,
    opponent_profile_dict: Optional[Dict[str, Any]] = None,
    rng_module=None,
) -> Action:
    rng_module = rng_module or __import__("random")
    observation = build_model_observation(
        card_rank=card_rank,
        my_chips=my_chips,
        opponent_chips=opponent_chips,
        pot=pot,
        current_bet=current_bet,
        round_num=round_num,
        my_raises=my_raises,
        opponent_raises=opponent_raises,
        opponent_profile_dict=opponent_profile_dict,
    )
    legal_actions = build_model_legal_actions(current_bet=current_bet, pot=pot, my_chips=my_chips)
    return loaded_policy["policy"].act(observation, legal_actions, rng_module)
