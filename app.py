from __future__ import annotations

import math
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from game_input import GameInputExecutor
from lock_preview import LockPreview
from lock_solver import Direction, LockLayerDefinition, LockSolver, SolverLimitError, Step


class LockpickApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Gothic 1 Remake Lockpick")
        self.resizable(True, True)
        self.layer_count = tk.IntVar(value=6)
        self.start_delay = tk.DoubleVar(value=3.0)
        self.key_delay = tk.IntVar(value=100)
        self.status = tk.StringVar(value="Configure the layers and click Solve.")
        self.layer_rows: list[tuple[tk.IntVar, set[int], set[int]]] = []
        self.steps: list[Step] | None = None
        self.events: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.rebuild_job: str | None = None
        self.selected_layer = 0
        self.layer_count.trace_add("write", self._schedule_table_rebuild)

        self._build_controls()
        self._rebuild_table()
        self.after(100, self._poll_events)

    def _build_controls(self) -> None:
        controls = ttk.Frame(self, padding=12)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(8, weight=1)

        ttk.Label(controls, text="Layers:").grid(row=0, column=0, sticky="w")
        tk.Spinbox(controls, from_=1, to=10, width=5, textvariable=self.layer_count).grid(
            row=0, column=1, padx=(4, 12)
        )

        ttk.Label(controls, text="Delay before Play (s):").grid(row=0, column=2, padx=(18, 4))
        tk.Spinbox(controls, from_=0, to=30, increment=0.5, width=5, textvariable=self.start_delay).grid(
            row=0, column=3
        )
        ttk.Label(controls, text="Delay between keys (ms):").grid(row=0, column=4, padx=(18, 4))
        tk.Spinbox(controls, from_=0, to=1_000, increment=10, width=6, textvariable=self.key_delay).grid(
            row=0, column=5
        )
        ttk.Button(controls, text="Solve", command=self._solve).grid(row=0, column=6, padx=(18, 4))
        self.play_button = ttk.Button(controls, text="Play in Gothic", command=self._play)
        self.play_button.grid(row=0, column=7, sticky="e")

        help_text = (
            "Choose linked layers. + moves in the same direction; - moves in the opposite direction. "
            "Positions use 1-7 (target: 4). In-game: W/S select a layer; A performs LEFT; D performs RIGHT."
        )
        ttk.Label(controls, text=help_text, wraplength=900).grid(
            row=1, column=0, columnspan=8, sticky="w", pady=(10, 0)
        )

        workspace = ttk.Frame(self, padding=(12, 0, 12, 8))
        workspace.grid(row=1, column=0, sticky="nsew")
        workspace.columnconfigure(1, weight=1)

        self.table = ttk.Frame(workspace)
        self.table.grid(row=0, column=0, sticky="nw", padx=(0, 16))

        preview_frame = ttk.LabelFrame(workspace, text="Lock preview", padding=6)
        preview_frame.grid(row=0, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        self.preview = LockPreview(
            preview_frame,
            on_select_layer=self._select_layer,
            on_set_position=self._set_layer_position,
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar = ttk.Scrollbar(
            preview_frame, orient="vertical", command=self.preview.yview
        )
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview.configure(yscrollcommand=preview_scrollbar.set)
        self.columnconfigure(0, weight=1)

        result_frame = ttk.LabelFrame(self, text="Solution", padding=8)
        result_frame.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.result = scrolledtext.ScrolledText(result_frame, height=9, width=90, state="disabled")
        self.result.grid(row=0, column=0, sticky="nsew")
        result_frame.columnconfigure(0, weight=1)

        ttk.Label(self, textvariable=self.status, padding=(12, 0, 12, 12)).grid(
            row=3, column=0, sticky="w"
        )

    def _schedule_table_rebuild(self, *_: object) -> None:
        if self.rebuild_job is not None:
            self.after_cancel(self.rebuild_job)
        self.rebuild_job = self.after(150, self._rebuild_table)

    def _rebuild_table(self) -> None:
        self.rebuild_job = None
        try:
            count = self.layer_count.get()
            if not 1 <= count <= 10:
                raise ValueError
        except (tk.TclError, ValueError):
            return

        previous = self.layer_rows
        for child in self.table.winfo_children():
            child.destroy()
        self.layer_rows = []

        headers = ("Layer", "Initial position", "Positive links", "Negative links")
        for column, header in enumerate(headers):
            ttk.Label(self.table, text=header).grid(row=0, column=column, padx=5, pady=4, sticky="w")

        for layer_id in range(count):
            position = tk.IntVar(value=previous[layer_id][0].get() if layer_id < len(previous) else 4)
            positive = {
                linked_layer for linked_layer in previous[layer_id][1] if linked_layer <= count
            } if layer_id < len(previous) else set()
            negative = {
                linked_layer for linked_layer in previous[layer_id][2] if linked_layer <= count
            } if layer_id < len(previous) else set()
            self.layer_rows.append((position, positive, negative))
            position.trace_add("write", lambda *_: self._render_preview())

            ttk.Label(self.table, text=str(layer_id + 1)).grid(
                row=layer_id + 1, column=0, padx=5, pady=2, sticky="w"
            )
            tk.Spinbox(self.table, from_=1, to=7, width=8, textvariable=position).grid(
                row=layer_id + 1, column=1, padx=5, pady=2
            )
            self._create_link_button(layer_id, positive, negative, "positive").grid(
                row=layer_id + 1, column=2, padx=5, pady=2, sticky="ew"
            )
            self._create_link_button(layer_id, negative, positive, "negative").grid(
                row=layer_id + 1, column=3, padx=5, pady=2, sticky="ew"
            )

        self.selected_layer = min(self.selected_layer, count - 1)
        self._render_preview()

    def _render_preview(self) -> None:
        try:
            positions = [position.get() for position, _, _ in self.layer_rows]
        except tk.TclError:
            return
        self.preview.render(positions, self.selected_layer)

    def _select_layer(self, layer_id: int) -> None:
        self.selected_layer = layer_id
        self._render_preview()

    def _set_layer_position(self, layer_id: int, position: int) -> None:
        self.layer_rows[layer_id][0].set(position)
        self._select_layer(layer_id)

    def _create_link_button(
        self, source_layer: int, selected: set[int], excluded: set[int], link_type: str
    ) -> ttk.Button:
        button = ttk.Button(self.table, width=28, text=self._link_button_text(selected))
        button.configure(
            command=lambda: self._open_link_selector(
                source_layer, selected, excluded, link_type, button
            )
        )
        return button

    @staticmethod
    def _link_button_text(selected: set[int]) -> str:
        return ", ".join(str(linked_layer) for linked_layer in sorted(selected)) or "Choose..."

    def _open_link_selector(
        self,
        source_layer: int,
        selected: set[int],
        excluded: set[int],
        link_type: str,
        button: ttk.Button,
    ) -> None:
        dialog = tk.Toplevel(self)
        source_layer_id = source_layer + 1
        dialog.title(f"Select {link_type} links for layer {source_layer_id}")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        content = ttk.Frame(dialog, padding=12)
        content.grid(row=0, column=0)
        ttk.Label(content, text="Select one or more layers:").grid(row=0, column=0, sticky="w")

        choices: dict[int, tk.BooleanVar] = {}
        for row, linked_layer_id in enumerate(range(1, len(self.layer_rows) + 1), start=1):
            if linked_layer_id == source_layer_id:
                continue
            checked = tk.BooleanVar(value=linked_layer_id in selected)
            choices[linked_layer_id] = checked
            state = "disabled" if linked_layer_id in excluded else "normal"
            ttk.Checkbutton(
                content, text=str(linked_layer_id), variable=checked, state=state
            ).grid(row=row, column=0, sticky="w")

        def save_selection() -> None:
            selected.clear()
            selected.update(
                linked_layer for linked_layer, checked in choices.items() if checked.get()
            )
            button.configure(text=self._link_button_text(selected))
            dialog.destroy()

        ttk.Button(content, text="Apply", command=save_selection).grid(
            row=len(self.layer_rows) + 1, column=0, pady=(10, 0), sticky="e"
        )

    def _read_layers(self) -> list[LockLayerDefinition]:
        layers = []
        for layer_id, (position, positive, negative) in enumerate(self.layer_rows):
            try:
                layers.append(
                    LockLayerDefinition(
                        position=position.get() - 1,
                        positive_links=tuple(linked_layer - 1 for linked_layer in sorted(positive)),
                        negative_links=tuple(linked_layer - 1 for linked_layer in sorted(negative)),
                    )
                )
            except (tk.TclError, ValueError) as error:
                raise ValueError(f"Layer ll{layer_id}: {error}") from error
        return layers

    def _solve(self) -> list[Step] | None:
        try:
            self.steps = LockSolver(self._read_layers()).solve()
        except (SolverLimitError, ValueError) as error:
            self.steps = None
            self._show_result(f"Error: {error}")
            self.status.set("Correct the configuration and try again.")
            return None

        if self.steps is None:
            self._show_result("There is no solution for this configuration.")
            self.status.set("There are no commands to run.")
            return None
        if not self.steps:
            self._show_result("All layers are already at position 4.")
            self.status.set("Lock already solved.")
            return self.steps

        lines = [
            f"{index}. Layer {step.lock_layer_id + 1}: {step.direction.value} x{step.actions}"
            for index, step in enumerate(self.steps, 1)
        ]
        self._show_result("\n".join(lines))
        self.status.set(f"Solution found: {sum(step.actions for step in self.steps)} A/D movements.")
        return self.steps

    def _show_result(self, text: str) -> None:
        self.result.configure(state="normal")
        self.result.delete("1.0", tk.END)
        self.result.insert(tk.END, text)
        self.result.configure(state="disabled")

    def _play(self) -> None:
        steps = self._solve()
        if not steps:
            return

        self.play_button.configure(state="disabled")
        threading.Thread(
            target=self._run_game_commands,
            args=(steps, self.start_delay.get(), self.key_delay.get(), len(self.layer_rows)),
            daemon=True,
        ).start()

    def _run_game_commands(
        self, steps: list[Step], delay: float, key_delay: int, lock_layer_count: int
    ) -> None:
        whole_seconds = math.ceil(delay)
        for remaining in range(whole_seconds, 0, -1):
            self.events.put(("status", f"Focus Gothic: starting in {remaining}s..."))
            time.sleep(min(1, delay))
            delay -= 1
        try:
            GameInputExecutor(lock_layer_count, key_delay).execute(steps)
            self.events.put(("status", "Commands sent to Gothic."))
        except (RuntimeError, ValueError, OSError) as error:
            self.events.put(("error", str(error)))
        finally:
            self.events.put(("done", None))

    def _poll_events(self) -> None:
        while not self.events.empty():
            event, value = self.events.get_nowait()
            if event == "status":
                self.status.set(value or "")
            elif event == "error":
                messagebox.showerror("Unable to send commands", value or "Unknown error")
            elif event == "done":
                self.play_button.configure(state="normal")
        self.after(100, self._poll_events)


if __name__ == "__main__":
    LockpickApp().mainloop()
