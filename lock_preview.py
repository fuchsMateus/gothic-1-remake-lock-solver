from __future__ import annotations

import tkinter as tk
import time
from collections.abc import Callable, Sequence


class LockPreview(tk.Canvas):
    """Interactive visual model of the lock's fixed pins and sliding layers."""

    HOLE_COUNT = 7
    TARGET_POSITION = 4
    WIDTH = 640
    HEIGHT = 450
    HOLE_SPACING = 42
    PLATE_PADDING = 20
    PLATE_HEIGHT = 42
    LAYER_SPACING = 52
    BASE_PLATE_X = 145
    TOP_Y = 40

    def __init__(
        self,
        parent: tk.Misc,
        on_select_layer: Callable[[int], None],
        on_set_position: Callable[[int, int], None],
    ) -> None:
        super().__init__(
            parent,
            width=self.WIDTH,
            height=self.HEIGHT,
            background="#121416",
            highlightthickness=0,
            cursor="hand2",
        )
        self.on_select_layer = on_select_layer
        self.on_set_position = on_set_position
        self._animation_after_id: str | None = None

    def render(self, positions: Sequence[float], selected_layer: int) -> None:
        self.delete("all")
        layer_count = len(positions)
        if not layer_count:
            return

        pin_x = self._pin_x()
        bottom_y = self._layer_y(0, layer_count)
        top_y = self._layer_y(layer_count - 1, layer_count)
        self.create_line(pin_x, top_y - 35, pin_x, bottom_y + 35, fill="#8d7651", width=2)

        # The highest-numbered layer is drawn first. Layer 1 is therefore the front, lower layer.
        for layer_id in range(layer_count - 1, -1, -1):
            self._draw_layer(layer_id, positions[layer_id], layer_count, layer_id == selected_layer)

        self.create_text(
            self.WIDTH / 2,
            self.HEIGHT - 14,
            text="Click a layer to select it. Click one of its holes to set its position.",
            fill="#bfc2c5",
            font=("Segoe UI", 9),
        )

    @property
    def is_animating(self) -> bool:
        return self._animation_after_id is not None

    def animate_layer(
        self,
        layer_id: int,
        target_position: int,
        positions: Sequence[int],
        selected_layer: int,
        on_complete: Callable[[], None],
    ) -> None:
        if self.is_animating:
            return

        start_position = positions[layer_id]
        if start_position == target_position:
            on_complete()
            return

        animation_positions = list(positions)
        started_at = time.monotonic()
        duration_seconds = max(0.18, 0.12 * abs(target_position - start_position))

        def tick() -> None:
            progress = min(1.0, (time.monotonic() - started_at) / duration_seconds)
            eased_progress = 1 - (1 - progress) ** 3
            animation_positions[layer_id] = start_position + (
                target_position - start_position
            ) * eased_progress
            self.render(animation_positions, selected_layer)
            if progress < 1.0:
                self._animation_after_id = self.after(16, tick)
                return

            self._animation_after_id = None
            on_complete()

        self._animation_after_id = self.after_idle(tick)

    def _draw_layer(self, layer_id: int, position: float, layer_count: int, selected: bool) -> None:
        plate_x = self._plate_x(position)
        plate_y = self._layer_y(layer_id, layer_count)
        plate_width = self.PLATE_PADDING * 2 + (self.HOLE_COUNT - 1) * self.HOLE_SPACING
        layer_tag = f"layer-{layer_id}"
        fill = "#595b5d" if selected else "#444649"
        outline = "#d3aa62" if selected else "#222426"
        outline_width = 3 if selected else 1

        self.create_rectangle(
            plate_x + 3,
            plate_y + 4,
            plate_x + plate_width + 3,
            plate_y + self.PLATE_HEIGHT + 4,
            fill="#08090a",
            outline="",
            tags=(layer_tag,),
        )
        self.create_rectangle(
            plate_x,
            plate_y,
            plate_x + plate_width,
            plate_y + self.PLATE_HEIGHT,
            fill=fill,
            outline=outline,
            width=outline_width,
            tags=(layer_tag,),
        )
        self.create_line(
            plate_x + 4,
            plate_y + 5,
            plate_x + plate_width - 4,
            plate_y + 5,
            fill="#96989a",
            tags=(layer_tag,),
        )

        self.create_text(
            594,
            plate_y + self.PLATE_HEIGHT / 2,
            text=f"Layer {layer_id + 1}",
            fill="#f0e8da" if selected else "#c5c7c8",
            font=("Segoe UI", 10, "bold" if selected else "normal"),
            tags=(layer_tag,),
        )

        hole_y = plate_y + self.PLATE_HEIGHT / 2
        for hole_position in range(1, self.HOLE_COUNT + 1):
            hole_x = plate_x + self.PLATE_PADDING + (hole_position - 1) * self.HOLE_SPACING
            hole_tag = f"hole-{layer_id}-{hole_position}"
            self.create_oval(
                hole_x - 10,
                hole_y - 10,
                hole_x + 10,
                hole_y + 10,
                fill="#111214",
                outline="#989a9b",
                width=1,
                tags=(layer_tag, hole_tag),
            )
            self.create_oval(
                hole_x - 6,
                hole_y - 6,
                hole_x + 6,
                hole_y + 6,
                fill="#050606",
                outline="",
                tags=(layer_tag, hole_tag),
            )
            self.tag_bind(
                hole_tag,
                "<Button-1>",
                lambda _event, current_layer=layer_id, current_position=hole_position: self._set_position(
                    current_layer, current_position
                ),
            )

            if selected:
                self.create_text(
                    hole_x,
                    plate_y - 10,
                    text=str(hole_position),
                    fill="#ddd0bb",
                    font=("Segoe UI", 8),
                    tags=(layer_tag, hole_tag),
                )

        is_aligned = abs(position - self.TARGET_POSITION) < 0.01
        pin_color = "#bf302b" if is_aligned else "#b3884f"
        pin_outline = "#ff766d" if is_aligned else "#e1ba77"
        pin_x = self._pin_x()
        self.create_oval(
            pin_x - 8,
            hole_y - 8,
            pin_x + 8,
            hole_y + 8,
            fill=pin_color,
            outline=pin_outline,
            width=2,
            tags=(layer_tag,),
        )

        self.tag_bind(layer_tag, "<Button-1>", lambda _event, current_layer=layer_id: self.on_select_layer(current_layer))

    def _set_position(self, layer_id: int, position: int) -> str:
        self.on_set_position(layer_id, position)
        return "break"

    def _plate_x(self, position: float) -> float:
        return self.BASE_PLATE_X + (self.TARGET_POSITION - position) * self.HOLE_SPACING

    def _pin_x(self) -> int:
        return self.BASE_PLATE_X + self.PLATE_PADDING + (self.TARGET_POSITION - 1) * self.HOLE_SPACING

    def _layer_y(self, layer_id: int, layer_count: int) -> int:
        return self.TOP_Y + (layer_count - 1 - layer_id) * self.LAYER_SPACING
