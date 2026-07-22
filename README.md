<p align="center">
  <img src="assets/gothic-lock-solver-logo.png" alt="Gothic 1 Remake Lockpick logo" width="320">
</p>

Desktop application for configuring a lock, finding a minimum movement sequence, and sending it to Gothic 1 Remake.

## Run

On Windows, with Python 3.10 or newer installed:

```powershell
python gothic_lockpick.py
```

There are no external dependencies: the interface uses `tkinter` and keyboard output uses the native Windows API.

## Presets

Use **Save as...** to give the current lock configuration a name. Saved presets can be selected, loaded, updated, or deleted from the preset controls at the top of the window.

The first launch creates `%LOCALAPPDATA%\Gothic1RemakeLockpick\presets.json`, seeded from the included example preset. This local file stores the layer configuration and keyboard-delay settings.

## Configuration

- **Layers**: choose from 3 to 7 layers.
- **Initial position**: a value from 1 to 7. The solver's target is position `4` in the interface.
- **Positive links**: select the layers that move in the same direction.
- **Negative links**: select the layers that move in the opposite direction.

IDs follow the table: the first row is `1`, followed by `2`, and so on.

## Run in the game

1. Fill in the table and choose the delay before Play and the delay between keys.
2. With the puzzle open in Gothic, click **Play in Gothic**.
3. The app solves the lock. During the countdown, manually focus the Gothic 1 Remake game window.

Use **Copy solution to clipboard** to copy the current movement sequence as text. The solver result is reused until the lock configuration changes.

The executor starts at layer `1` and uses:

- `W`: next layer
- `S`: previous layer
- `A`: `LEFT`
- `D`: `RIGHT`

If Gothic 1 Remake does not register the simulated input, increase the delay between keys.

## Tests

```powershell
python -m unittest discover -s tests
```
