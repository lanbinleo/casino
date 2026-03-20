"""Simple self-play arena for the Fire Station environment.

Usage:
    python -m fire_station_ai.selfplay --hands 500
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from .env import FireStationEnv, PlayerProfile, Seat
from .policies import DifficultyPolicy, HeuristicPolicy


@dataclass
class ArenaResult:
    hands_played: int
    starting_stacks: Tuple[int, int]
    final_stacks: Tuple[int, int]
    seat0_wins: int
    seat1_wins: int
    ties: int
    bankroll_delta: Tuple[int, int]
    bankrupt_seat: int | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hands_played": self.hands_played,
            "starting_stacks": list(self.starting_stacks),
            "final_stacks": list(self.final_stacks),
            "seat0_wins": self.seat0_wins,
            "seat1_wins": self.seat1_wins,
            "ties": self.ties,
            "bankroll_delta": list(self.bankroll_delta),
            "bankrupt_seat": self.bankrupt_seat,
        }


def run_match(
    policy_player,
    policy_opponent,
    *,
    hands: int = 200,
    base_bet: int = 10,
    starting_stacks: Sequence[int] = (1000, 1000),
    seed: int | None = None,
) -> ArenaResult:
    env = FireStationEnv(seed=seed, allow_credit_call_for=())
    profiles = [PlayerProfile(), PlayerProfile()]
    stacks = [int(starting_stacks[0]), int(starting_stacks[1])]

    seat0_wins = 0
    seat1_wins = 0
    ties = 0
    played = 0

    for hand_index in range(hands):
        if stacks[0] < base_bet or stacks[1] < base_bet:
            break

        first_actor = Seat.PLAYER if hand_index % 2 == 0 else Seat.OPPONENT
        env.reset(base_bet=base_bet, stacks=stacks, profiles=profiles, first_actor=first_actor)

        while not env.state.terminal:
            acting = env.state.to_act
            observation = env.observation(acting)
            legal_actions = env.legal_actions(acting)
            if acting == Seat.PLAYER:
                chosen = policy_player.act(observation, legal_actions, env.rng)
            else:
                chosen = policy_opponent.act(observation, legal_actions, env.rng)
            env.step(chosen, acting)

        stacks = list(env.state.stacks)
        profiles = env.state.profiles
        played += 1

        if env.state.winner == Seat.PLAYER:
            seat0_wins += 1
        elif env.state.winner == Seat.OPPONENT:
            seat1_wins += 1
        else:
            ties += 1

    bankrupt_seat = None
    if stacks[0] < base_bet:
        bankrupt_seat = 0
    elif stacks[1] < base_bet:
        bankrupt_seat = 1

    return ArenaResult(
        hands_played=played,
        starting_stacks=(int(starting_stacks[0]), int(starting_stacks[1])),
        final_stacks=(int(stacks[0]), int(stacks[1])),
        seat0_wins=seat0_wins,
        seat1_wins=seat1_wins,
        ties=ties,
        bankroll_delta=(int(stacks[0] - starting_stacks[0]), int(stacks[1] - starting_stacks[1])),
        bankrupt_seat=bankrupt_seat,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Fire Station self-play")
    parser.add_argument("--hands", type=int, default=500)
    parser.add_argument("--base-bet", type=int, default=10)
    parser.add_argument("--stack", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--player-level", type=str, default="hard", choices=["easy", "normal", "hard"])
    parser.add_argument("--opponent-level", type=str, default="normal", choices=["easy", "normal", "hard"])
    args = parser.parse_args()

    player_policy = DifficultyPolicy.for_level(HeuristicPolicy(personality="tricky", mood=0.55), args.player_level)
    opponent_policy = DifficultyPolicy.for_level(HeuristicPolicy(personality="tight", mood=0.45), args.opponent_level)

    result = run_match(
        player_policy,
        opponent_policy,
        hands=args.hands,
        base_bet=args.base_bet,
        starting_stacks=(args.stack, args.stack),
        seed=args.seed,
    )

    print("Fire Station self-play")
    for key, value in result.to_dict().items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
