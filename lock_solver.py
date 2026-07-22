"""Pure solver for the Gothic lock puzzle."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

MIN_POSITION = 0
MAX_POSITION = 6
TARGET_POSITION = 3


class Direction(Enum):
    LEFT = "LEFT"      # Sent to the game as A
    RIGHT = "RIGHT"    # Sent to the game as D


@dataclass(frozen=True)
class Step:
    lock_layer_id: int
    direction: Direction
    actions: int = 1


@dataclass(frozen=True)
class LockLayerDefinition:
    position: int
    positive_links: tuple[int, ...] = ()
    negative_links: tuple[int, ...] = ()


class SolverLimitError(RuntimeError):
    """Raised when the configured puzzle is too large for a breadth-first search."""


class LockSolver:
    """Finds a minimum number of A/D lock movements using breadth-first search."""

    def __init__(self, layers: list[LockLayerDefinition], max_states: int = 1_000_000):
        self.layers = layers
        self.max_states = max_states
        self._validate_layers()

    def solve(self) -> list[Step] | None:
        initial_state = tuple(layer.position for layer in self.layers)
        target_state = (TARGET_POSITION,) * len(self.layers)
        if initial_state == target_state:
            return []

        states = deque([initial_state])
        parents: dict[tuple[int, ...], tuple[tuple[int, ...], Step] | None] = {
            initial_state: None
        }

        while states:
            current = states.popleft()
            for layer_id in range(len(self.layers)):
                for direction in (Direction.LEFT, Direction.RIGHT):
                    next_state = self._move(current, layer_id, direction)
                    if next_state is None or next_state in parents:
                        continue

                    parents[next_state] = (current, Step(layer_id, direction))
                    if next_state == target_state:
                        return self._build_steps(next_state, parents)
                    if len(parents) >= self.max_states:
                        raise SolverLimitError(
                            f"Search stopped after {self.max_states:,} states. Reduce the number of layers."
                        )
                    states.append(next_state)

        return None

    def _move(
        self, state: tuple[int, ...], layer_id: int, direction: Direction
    ) -> tuple[int, ...] | None:
        position_delta = 1 if direction is Direction.LEFT else -1
        next_positions = list(state)
        next_positions[layer_id] += position_delta

        layer = self.layers[layer_id]
        for linked_layer_id in layer.positive_links:
            next_positions[linked_layer_id] += position_delta
        for linked_layer_id in layer.negative_links:
            next_positions[linked_layer_id] -= position_delta

        if any(position < MIN_POSITION or position > MAX_POSITION for position in next_positions):
            return None
        return tuple(next_positions)

    @staticmethod
    def _build_steps(
        solved_state: tuple[int, ...],
        parents: dict[tuple[int, ...], tuple[tuple[int, ...], Step] | None],
    ) -> list[Step]:
        raw_steps: list[Step] = []
        state = solved_state
        while parents[state] is not None:
            previous_state, step = parents[state]
            raw_steps.append(step)
            state = previous_state
        raw_steps.reverse()

        compressed: list[Step] = []
        for step in raw_steps:
            if (
                compressed
                and compressed[-1].lock_layer_id == step.lock_layer_id
                and compressed[-1].direction is step.direction
            ):
                previous = compressed[-1]
                compressed[-1] = Step(
                    previous.lock_layer_id,
                    previous.direction,
                    previous.actions + 1,
                )
            else:
                compressed.append(step)
        return compressed

    def _validate_layers(self) -> None:
        if not self.layers:
            raise ValueError("Add at least one lock layer.")

        layer_count = len(self.layers)
        for layer_id, layer in enumerate(self.layers):
            if not MIN_POSITION <= layer.position <= MAX_POSITION:
                raise ValueError(f"Layer {layer_id}: position must be between 0 and 6.")
            positive = set(layer.positive_links)
            negative = set(layer.negative_links)
            if len(positive) != len(layer.positive_links) or len(negative) != len(layer.negative_links):
                raise ValueError(f"Layer {layer_id}: duplicate links are not allowed.")
            if positive & negative:
                raise ValueError(f"Layer {layer_id}: a link cannot be both positive and negative.")
            for linked_layer_id in positive | negative:
                if not 0 <= linked_layer_id < layer_count:
                    raise ValueError(
                        f"Layer {layer_id}: linked layer {linked_layer_id} does not exist."
                    )
