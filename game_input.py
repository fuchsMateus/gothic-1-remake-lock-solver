"""Windows keyboard output for the Gothic lock interface."""

from __future__ import annotations

import ctypes
import os
import time

from lock_solver import Direction, Step

VK_A = 0x41
VK_D = 0x44
VK_S = 0x53
VK_W = 0x57
KEYEVENTF_KEYUP = 0x0002


class GameInputExecutor:
    """Applies solver steps starting with lock layer 0 selected.

    W selects the next layer, S selects the previous layer, A performs LEFT and
    D performs RIGHT. The active game window receives the keystrokes.
    """

    def __init__(self, lock_layer_count: int, key_delay_ms: int = 100):
        if os.name != "nt":
            raise RuntimeError("Keyboard execution is available only on Windows.")
        if lock_layer_count <= 0:
            raise ValueError("Lock layer count must be greater than zero.")
        if key_delay_ms < 0:
            raise ValueError("Key delay cannot be negative.")

        self.lock_layer_count = lock_layer_count
        self.key_delay_seconds = key_delay_ms / 1_000
        self.current_lock_layer = 0

    def execute(self, steps: list[Step]) -> None:
        for step in steps:
            self._select_lock_layer(step.lock_layer_id)
            key = VK_A if step.direction is Direction.LEFT else VK_D
            for _ in range(step.actions):
                self._press(key)

    def _select_lock_layer(self, target_layer: int) -> None:
        if not 0 <= target_layer < self.lock_layer_count:
            raise ValueError("Step references a layer outside the configured range.")

        while self.current_lock_layer < target_layer:
            self._press(VK_W)
            self.current_lock_layer += 1
        while self.current_lock_layer > target_layer:
            self._press(VK_S)
            self.current_lock_layer -= 1

    def _press(self, virtual_key: int) -> None:
        ctypes.windll.user32.keybd_event(virtual_key, 0, 0, 0)
        ctypes.windll.user32.keybd_event(virtual_key, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(self.key_delay_seconds)
