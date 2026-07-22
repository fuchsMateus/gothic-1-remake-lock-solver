from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence


class LockPreview(tk.Canvas):
    """Interactive visual model of the lock's fixed pins and sliding layers."""

    HOLE_COUNT = 7
    TARGET_POSITION = 4
    WIDTH = 800
    HEIGHT = 430
    HOLE_SPACING = 54
    PLATE_PADDING = 24
    PLATE_HEIGHT = 42
    LAYER_SPACING = 58
    BASE_PLATE_X = 195
    TOP_Y = 52

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
        self._mousewheel_active = False
        self.bind("<Enter>", self._enable_mousewheel)
        self.bind("<Leave>", self._disable_mousewheel)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel, add="+")

    def render(self, positions: Sequence[int], selected_layer: int) -> None:
        self.delete("all")
        layer_count = len(positions)
        if not layer_count:
            return

        content_height = self._content_height(layer_count)
        self.configure(scrollregion=(0, 0, self.WIDTH, content_height))
        pin_x = self._pin_x()
        bottom_y = self._layer_y(0, layer_count)
        top_y = self._layer_y(layer_count - 1, layer_count)
        self.create_line(pin_x, top_y - 35, pin_x, bottom_y + 35, fill="#8d7651", width=2)

        # The highest-numbered layer is drawn first. Layer 1 is therefore the front, lower layer.
        for layer_id in range(layer_count - 1, -1, -1):
            self._draw_layer(layer_id, positions[layer_id], layer_count, layer_id == selected_layer)

        self.create_text(
            self.WIDTH / 2,
            content_height - 14,
            text="Click a layer to select it. Click one of its holes to set its position.",
            fill="#bfc2c5",
            font=("Segoe UI", 9),
        )

    def _draw_layer(self, layer_id: int, position: int, layer_count: int, selected: bool) -> None:
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
            754,
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

        pin_color = "#bf302b" if position == self.TARGET_POSITION else "#b3884f"
        pin_outline = "#ff766d" if position == self.TARGET_POSITION else "#e1ba77"
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

    def _plate_x(self, position: int) -> int:
        return self.BASE_PLATE_X + (self.TARGET_POSITION - position) * self.HOLE_SPACING

    def _pin_x(self) -> int:
        return self.BASE_PLATE_X + self.PLATE_PADDING + (self.TARGET_POSITION - 1) * self.HOLE_SPACING

    def _layer_y(self, layer_id: int, layer_count: int) -> int:
        return self.TOP_Y + (layer_count - 1 - layer_id) * self.LAYER_SPACING

    def _content_height(self, layer_count: int) -> int:
        bottom_layer_y = self._layer_y(0, layer_count)
        return max(self.HEIGHT, bottom_layer_y + self.PLATE_HEIGHT + 42)

    def _enable_mousewheel(self, _event: tk.Event) -> None:
        self._mousewheel_active = True

    def _disable_mousewheel(self, _event: tk.Event) -> None:
        self._mousewheel_active = False

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        if not self._mousewheel_active:
            return None

        if getattr(event, "delta", 0):
            amount = -int(event.delta / 120)
        elif event.num == 4:
            amount = -1
        else:
            amount = 1
        self.yview_scroll(amount or (-1 if event.delta > 0 else 1), "units")
        return "break"
