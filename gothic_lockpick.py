from __future__ import annotations

import math
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from game_input import GameInputExecutor
from lock_preview import LockPreview
from lock_solver import Direction, LockLayerDefinition, LockSolver, SolverLimitError, Step
from preset_store import PresetStore

DEFAULT_PRESET_NAME = "Default"


def build_default_preset() -> dict[str, object]:
    return {
        "name": DEFAULT_PRESET_NAME,
        "layerCount": 7,
        "layers": [
            {"position": 4, "positiveLinks": [], "negativeLinks": []}
            for _ in range(7)
        ],
        "startDelaySeconds": 3.0,
        "keyDelayMilliseconds": 100,
    }


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.window: tk.Toplevel | None = None
        self.show_job: str | None = None
        widget.bind("<Enter>", self._schedule_show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule_show(self, _event: tk.Event) -> None:
        self.show_job = self.widget.after(400, self._show)

    def _show(self) -> None:
        self.show_job = None
        if self.window is not None:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.configure(background="#1d2024")
        tk.Label(
            self.window,
            text=self.text,
            justify="left",
            background="#1d2024",
            foreground="#f1ece3",
            padx=10,
            pady=8,
        ).pack()
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
        y = self.widget.winfo_rooty()
        self.window.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event: tk.Event | None = None) -> None:
        if self.show_job is not None:
            self.widget.after_cancel(self.show_job)
            self.show_job = None
        if self.window is not None:
            self.window.destroy()
            self.window = None


class LockpickApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Gothic 1 Remake Lockpick")
        self.geometry("1140x650")
        self.resizable(False, False)
        self._set_window_icon()
        self.logo_image = self._load_logo()
        self.layer_count = tk.IntVar(value=7)
        self.start_delay = tk.DoubleVar(value=3.0)
        self.key_delay = tk.IntVar(value=100)
        self.preset_name = tk.StringVar(value=DEFAULT_PRESET_NAME)
        self.status = tk.StringVar(value="Configure the layers and click Play in Gothic.")
        self.layer_rows: list[tuple[tk.IntVar, set[int], set[int]]] = []
        self.link_buttons: list[tuple[ttk.Button, ttk.Button]] = []
        self.steps: list[Step] | None = None
        self.solution_cached = False
        self.events: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.rebuild_job: str | None = None
        self.selected_layer = 0
        self.preset_store = PresetStore()
        try:
            self.presets = self.preset_store.load()
        except ValueError as error:
            self.presets = {}
            self.status.set(str(error))
        self.layer_count.trace_add("write", self._schedule_table_rebuild)

        self._build_controls()
        self._rebuild_table()
        self._refresh_preset_choices()
        self.after(100, self._poll_events)

    @staticmethod
    def _load_logo() -> tk.PhotoImage | None:
        logo_path = Path(__file__).resolve().parent / "assets" / "gothic-lock-solver-logo.png"
        return tk.PhotoImage(file=str(logo_path)) if logo_path.exists() else None

    def _set_window_icon(self) -> None:
        icon_path = Path(__file__).resolve().parent / "assets" / "lock-solver.ico"
        if icon_path.exists():
            self.iconbitmap(default=str(icon_path))

    def _build_controls(self) -> None:
        controls = ttk.Frame(self, padding=(14, 12, 14, 8))
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)

        preset_row = ttk.Frame(controls)
        preset_row.grid(row=0, column=0, sticky="w")
        ttk.Label(preset_row, text="Preset:").grid(row=0, column=0, sticky="w")
        self.preset_selector = ttk.Combobox(
            preset_row, state="readonly", textvariable=self.preset_name, width=26
        )
        self.preset_selector.grid(row=0, column=1, padx=(6, 10), sticky="w")
        self.preset_selector.bind("<<ComboboxSelected>>", self._load_selected_preset)
        ttk.Button(preset_row, text="Save", command=self._save_preset).grid(row=0, column=2)
        ttk.Button(preset_row, text="Save as...", command=self._save_preset_as).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(preset_row, text="Delete", command=self._delete_preset).grid(row=0, column=4, padx=(8, 0))

        action_row = ttk.Frame(controls)
        action_row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.action_row = action_row
        ttk.Label(action_row, text="Layers:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(
            action_row,
            from_=3,
            to=7,
            width=5,
            textvariable=self.layer_count,
            validate="key",
            validatecommand=(self.register(self._is_valid_layer_count), "%P"),
        ).grid(row=0, column=1, padx=(6, 18), sticky="w")

        ttk.Label(action_row, text="Delay before Play (s):").grid(row=0, column=2, padx=(0, 6))
        ttk.Spinbox(action_row, from_=0, to=30, increment=0.5, width=5, textvariable=self.start_delay).grid(
            row=0, column=3
        )
        ttk.Label(action_row, text="Delay between keys (ms):").grid(row=0, column=4, padx=(20, 6))
        ttk.Spinbox(action_row, from_=0, to=1_000, increment=10, width=6, textvariable=self.key_delay).grid(
            row=0, column=5
        )
        ttk.Button(action_row, text="Copy solution", command=self._copy_solution).grid(
            row=0, column=7, padx=(18, 8)
        )
        self.play_button = ttk.Button(action_row, text="Play in Gothic", command=self._play)
        self.play_button.grid(row=0, column=8, sticky="e")
        self.stop_button = ttk.Button(action_row, text="Stop", command=self._stop_play)
        self.stop_button.grid(row=0, column=9, padx=(8, 0), sticky="e")
        self.stop_button.grid_remove()

        help_text = (
            "Choose linked layers. + moves in the same direction; - moves in the opposite direction. "
            "Positions use 1-7 (target: 4). In-game: W/S select a layer; A performs LEFT; D performs RIGHT."
        )
        ttk.Label(controls, text=help_text, wraplength=900).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )

        workspace = ttk.Frame(self, padding=(14, 0, 14, 8))
        workspace.grid(row=1, column=0, sticky="nsew")
        self.workspace = workspace

        self.table = ttk.Frame(workspace)
        self.table.grid(row=0, column=0, sticky="nw", padx=(0, 12))

        if self.logo_image is not None:
            self.logo_label = tk.Label(
                workspace,
                image=self.logo_image,
                borderwidth=0,
                highlightthickness=0,
            )
            self.logo_label.place(x=200, y=270, anchor="n")

        self.preview_frame = ttk.Frame(workspace, padding=0)
        self.preview_frame.grid(row=0, column=1, sticky="nsew")
        self.preview = LockPreview(
            self.preview_frame,
            on_select_layer=self._select_layer,
            on_set_position=self._set_layer_position,
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.after_idle(self._align_action_buttons)

        self.status_label = tk.Label(
            self,
            textvariable=self.status,
            anchor="w",
            borderwidth=0,
            padx=12,
            pady=6,
        )
        self.status_label.grid(row=2, column=0, sticky="ew")

    def _align_action_buttons(self) -> None:
        preview_right = self.preview_frame.winfo_rootx() + self.preview_frame.winfo_width()
        play_button_right = self.play_button.winfo_rootx() + self.play_button.winfo_width()
        adjustment = preview_right - play_button_right
        spacer_width = self.action_row.grid_bbox(6, 0)[2]
        self.action_row.columnconfigure(6, minsize=max(0, spacer_width + adjustment))

    def _schedule_table_rebuild(self, *_: object) -> None:
        if self.rebuild_job is not None:
            self.after_cancel(self.rebuild_job)
        self.rebuild_job = self.after(150, self._rebuild_table)

    def _rebuild_table(self) -> None:
        self.rebuild_job = None
        try:
            count = self.layer_count.get()
            if not 3 <= count <= 7:
                raise ValueError
        except (tk.TclError, ValueError):
            return

        previous = self.layer_rows
        self._invalidate_solution()
        for child in self.table.winfo_children():
            child.destroy()
        self.layer_rows = []
        self.link_buttons = []

        headers = ("Layer", "Initial position", "Positive links", "Negative links")
        for column, header in enumerate(headers):
            ttk.Label(self.table, text=header).grid(row=0, column=column, padx=5, pady=4, sticky="w")
        links_help_button = ttk.Button(self.table, text="?", width=3, command=self._show_links_help)
        links_help_button.grid(row=0, column=4, padx=(2, 0), pady=4, sticky="w")
        Tooltip(
            links_help_button,
            "Positive links move in the same direction as the selected layer.\n"
            "Negative links move in the opposite direction.",
        )

        for layer_id in range(count):
            position = tk.IntVar(value=previous[layer_id][0].get() if layer_id < len(previous) else 4)
            positive = {
                linked_layer for linked_layer in previous[layer_id][1] if linked_layer <= count
            } if layer_id < len(previous) else set()
            negative = {
                linked_layer for linked_layer in previous[layer_id][2] if linked_layer <= count
            } if layer_id < len(previous) else set()
            self.layer_rows.append((position, positive, negative))
            position.trace_add("write", lambda *_: self._on_position_changed())

            ttk.Label(self.table, text=str(layer_id + 1)).grid(
                row=layer_id + 1, column=0, padx=5, pady=2, sticky="w"
            )
            ttk.Spinbox(
                self.table,
                from_=1,
                to=7,
                width=8,
                textvariable=position,
                validate="key",
                validatecommand=(self.register(self._is_valid_position), "%P"),
            ).grid(row=layer_id + 1, column=1, padx=5, pady=2)
            positive_button = self._create_link_button(layer_id, positive, negative, "positive")
            positive_button.grid(
                row=layer_id + 1, column=2, padx=5, pady=2, sticky="ew"
            )
            negative_button = self._create_link_button(layer_id, negative, positive, "negative")
            negative_button.grid(
                row=layer_id + 1, column=3, padx=5, pady=2, sticky="ew"
            )
            self.link_buttons.append((positive_button, negative_button))

        self.selected_layer = min(self.selected_layer, count - 1)
        self._render_preview()

    def _render_preview(self) -> None:
        try:
            positions = [position.get() for position, _, _ in self.layer_rows]
        except tk.TclError:
            return
        self.preview.render(positions, self.selected_layer)

    def _on_position_changed(self) -> None:
        self._invalidate_solution()
        self._render_preview()

    def _invalidate_solution(self) -> None:
        self.steps = None
        self.solution_cached = False

    def _select_layer(self, layer_id: int) -> None:
        self.selected_layer = layer_id
        self._render_preview()

    def _set_layer_position(self, layer_id: int, position: int) -> None:
        if self.preview.is_animating:
            return

        current_position = self.layer_rows[layer_id][0].get()
        if current_position == position:
            self._select_layer(layer_id)
            return

        self.selected_layer = layer_id
        current_positions = [current.get() for current, _, _ in self.layer_rows]

        def finish_animation() -> None:
            self.layer_rows[layer_id][0].set(position)
            self._select_layer(layer_id)

        self.preview.animate_layer(
            layer_id,
            position,
            current_positions,
            self.selected_layer,
            finish_animation,
        )

    def _refresh_preset_choices(self, selected_name: str | None = None) -> None:
        names = [DEFAULT_PRESET_NAME] + sorted(
            (name for name in self.presets if name != DEFAULT_PRESET_NAME), key=str.lower
        )
        self.preset_selector.configure(values=names)
        if selected_name in names:
            self.preset_name.set(selected_name)
        elif self.preset_name.get() not in names:
            self.preset_name.set(DEFAULT_PRESET_NAME)

    def _load_selected_preset(self, _event: tk.Event | None = None) -> None:
        name = self.preset_name.get()
        if name == DEFAULT_PRESET_NAME:
            self._apply_preset(build_default_preset())
            self.status.set("Loaded default configuration.")
            return

        preset = self.presets.get(name)
        if preset is None:
            self.status.set("Select a preset to load.")
            return
        try:
            self._apply_preset(preset)
        except (KeyError, TypeError, ValueError) as error:
            self.status.set(f"Unable to load preset: {error}")
            return
        self.status.set(f"Loaded preset: {preset['name']}")

    def _save_preset(self) -> None:
        name = self.preset_name.get()
        if not name or name == DEFAULT_PRESET_NAME:
            self._save_preset_as()
            return
        self.presets[name] = self._build_preset(name)
        self._persist_presets(name, f"Saved preset: {name}")

    def _save_preset_as(self) -> None:
        name = simpledialog.askstring("Save preset", "Preset name:", parent=self)
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror("Invalid preset name", "Preset names cannot be empty.")
            return
        if name.casefold() == DEFAULT_PRESET_NAME.casefold():
            messagebox.showerror("Reserved preset name", "'Default' is reserved for the built-in configuration.")
            return
        if name in self.presets and not messagebox.askyesno(
            "Replace preset", f"Replace the existing preset '{name}'?", parent=self
        ):
            return
        self.presets[name] = self._build_preset(name)
        self._persist_presets(name, f"Saved preset: {name}")

    def _delete_preset(self) -> None:
        name = self.preset_name.get()
        if name == DEFAULT_PRESET_NAME:
            self.status.set("The built-in Default preset cannot be deleted.")
            return
        if not name or name not in self.presets:
            self.status.set("Select a preset to delete.")
            return
        if not messagebox.askyesno("Delete preset", f"Delete preset '{name}'?", parent=self):
            return
        del self.presets[name]
        self._persist_presets(None, f"Deleted preset: {name}")

    def _persist_presets(self, selected_name: str | None, status: str) -> None:
        try:
            self.preset_store.save(self.presets)
        except OSError as error:
            self.status.set(f"Unable to save presets: {error}")
            return
        self._refresh_preset_choices(selected_name)
        self.status.set(status)

    def _build_preset(self, name: str) -> dict[str, object]:
        return {
            "name": name,
            "layerCount": len(self.layer_rows),
            "layers": [
                {
                    "position": position.get(),
                    "positiveLinks": sorted(positive),
                    "negativeLinks": sorted(negative),
                }
                for position, positive, negative in self.layer_rows
            ],
            "startDelaySeconds": self.start_delay.get(),
            "keyDelayMilliseconds": self.key_delay.get(),
        }

    def _apply_preset(self, preset: dict[str, object]) -> None:
        layer_count = int(preset["layerCount"])
        layers = preset["layers"]
        if not 3 <= layer_count <= 7 or not isinstance(layers, list) or len(layers) != layer_count:
            raise ValueError("invalid layer count or layer list")

        if self.rebuild_job is not None:
            self.after_cancel(self.rebuild_job)
            self.rebuild_job = None
        self.layer_count.set(layer_count)
        if self.rebuild_job is not None:
            self.after_cancel(self.rebuild_job)
            self.rebuild_job = None
        self._rebuild_table()

        for row, saved_layer, buttons in zip(self.layer_rows, layers, self.link_buttons):
            if not isinstance(saved_layer, dict):
                raise ValueError("invalid layer entry")
            position, positive, negative = row
            position.set(int(saved_layer["position"]))
            positive.clear()
            positive.update(int(linked_layer) for linked_layer in saved_layer["positiveLinks"])
            negative.clear()
            negative.update(int(linked_layer) for linked_layer in saved_layer["negativeLinks"])
            positive_button, negative_button = buttons
            positive_button.configure(text=self._link_button_text(positive))
            negative_button.configure(text=self._link_button_text(negative))
        self.start_delay.set(float(preset["startDelaySeconds"]))
        self.key_delay.set(int(preset["keyDelayMilliseconds"]))
        self._render_preview()

    def _create_link_button(
        self, source_layer: int, selected: set[int], excluded: set[int], link_type: str
    ) -> ttk.Button:
        button = ttk.Button(self.table, width=18, text=self._link_button_text(selected))
        button.configure(
            command=lambda: self._open_link_selector(
                source_layer, selected, excluded, link_type, button
            )
        )
        return button

    def _show_links_help(self) -> None:
        messagebox.showinfo(
            "How links work",
            "Positive links move in the same direction as the selected layer.\n\n"
            "Negative links move in the opposite direction.",
            parent=self,
        )

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
            self._invalidate_solution()
            dialog.destroy()

        ttk.Button(content, text="Apply", command=save_selection).grid(
            row=len(self.layer_rows) + 1, column=0, pady=(10, 0), sticky="e"
        )

    def _read_layers(self) -> list[LockLayerDefinition]:
        layers = []
        for layer_id, (position, positive, negative) in enumerate(self.layer_rows):
            try:
                displayed_position = position.get()
                if not 1 <= displayed_position <= 7:
                    raise ValueError("position must be between 1 and 7")
                layers.append(
                    LockLayerDefinition(
                        position=displayed_position - 1,
                        positive_links=tuple(linked_layer - 1 for linked_layer in sorted(positive)),
                        negative_links=tuple(linked_layer - 1 for linked_layer in sorted(negative)),
                    )
                )
            except (tk.TclError, ValueError) as error:
                raise ValueError(f"Layer ll{layer_id}: {error}") from error
        return layers

    @staticmethod
    def _is_valid_position(proposed_value: str) -> bool:
        return proposed_value in {"1", "2", "3", "4", "5", "6", "7"}

    @staticmethod
    def _is_valid_layer_count(proposed_value: str) -> bool:
        return proposed_value in {"3", "4", "5", "6", "7"}

    def _get_solution(self) -> list[Step] | None:
        if self.solution_cached:
            if self.steps is None:
                self._show_no_solution()
            elif not self.steps:
                self.status.set("Lock already solved.")
            return self.steps

        try:
            self.steps = LockSolver(self._read_layers()).solve()
        except (SolverLimitError, ValueError) as error:
            self.steps = None
            self.status.set(f"Unable to solve: {error}")
            return None

        self.solution_cached = True

        if self.steps is None:
            self._show_no_solution()
            return None
        if not self.steps:
            self.status.set("Lock already solved.")
            return self.steps
        return self.steps

    def _show_no_solution(self) -> None:
        self.status.set("There is no solution for the current configuration.")
        messagebox.showinfo(
            "No solution",
            "There is no solution for the current lock configuration.",
            parent=self,
        )

    @staticmethod
    def _format_solution(steps: list[Step]) -> str:
        return "\n".join(
            f"{index}. Layer {step.lock_layer_id + 1}: {step.direction.value} x{step.actions}"
            for index, step in enumerate(steps, start=1)
        )

    def _copy_solution(self) -> None:
        if self.preview.is_animating:
            self.status.set("Wait for the layer animation to finish.")
            return
        self.status.set("Solving...")
        self.update_idletasks()
        steps = self._get_solution()
        if not steps:
            return
        self.clipboard_clear()
        self.clipboard_append(self._format_solution(steps))
        self.update()
        self.status.set("Solution copied to clipboard.")

    def _play(self) -> None:
        if self.preview.is_animating:
            self.status.set("Wait for the layer animation to finish.")
            return
        self.status.set("Solving...")
        self.update_idletasks()
        steps = self._get_solution()
        if not steps:
            return

        self.play_button.configure(state="disabled")
        self.stop_event = threading.Event()
        self.stop_button.configure(state="normal")
        self.stop_button.grid()
        threading.Thread(
            target=self._run_game_commands,
            args=(
                steps,
                self.start_delay.get(),
                self.key_delay.get(),
                len(self.layer_rows),
                self.stop_event,
            ),
            daemon=True,
        ).start()

    def _stop_play(self) -> None:
        if self.stop_event is None:
            return
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Stopping simulation...")

    def _run_game_commands(
        self,
        steps: list[Step],
        delay: float,
        key_delay: int,
        lock_layer_count: int,
        stop_event: threading.Event,
    ) -> None:
        whole_seconds = math.ceil(delay)
        for remaining in range(whole_seconds, 0, -1):
            self.events.put(("status", f"Focus Gothic: starting in {remaining}s..."))
            if stop_event.wait(min(1, delay)):
                self.events.put(("status", "Simulation stopped."))
                self.events.put(("done", None))
                return
            delay -= 1
        try:
            completed = GameInputExecutor(lock_layer_count, key_delay).execute(steps, stop_event)
            self.events.put(("status", "Commands sent to Gothic." if completed else "Simulation stopped."))
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
                self.stop_button.grid_remove()
                self.stop_event = None
        self.after(100, self._poll_events)


if __name__ == "__main__":
    LockpickApp().mainloop()
