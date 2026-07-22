# Gothic 1 Remake Lockpick

Desktop application for configuring a lock, finding a minimum movement sequence, and sending it to Gothic 1 Remake.

## Run

On Windows, with Python 3.10 or newer installed:

```powershell
python app.py
```

There are no external dependencies: the interface uses `tkinter` and keyboard output uses the native Windows API.

## Configuration

- **Initial position**: a value from 1 to 7. The solver's target is position `4` in the interface.
- **Positive links**: select the layers that move in the same direction.
- **Negative links**: select the layers that move in the opposite direction.

IDs follow the table: the first row is `1`, followed by `2`, and so on.

## Run in the game

1. Fill in the table and click **Solve**.
2. Choose the delay before Play and the delay between keys.
3. With the puzzle open in Gothic, click **Play in Gothic**.
4. Focus the game window during the countdown.

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
