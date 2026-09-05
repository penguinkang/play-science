# Play Science

Play Science is a library of small, interactive games that make scientific and computational ideas visible. Its first playable experiment, **Q-Learning Quest**, teaches reinforcement learning by showing how an explorer turns actions and rewards into a useful route through a grid world.

## Q-Learning Quest

The quest takes place on a 6 × 6 grid:

- **Robot 🤖 — agent:** starts at the upper-left square and chooses one of four actions: up, right, down, or left.
- **Empty square — −1 reward:** makes shorter routes preferable.
- **Coin 🪙 — +10 reward:** gives a one-time bonus when collected.
- **Volcano 🌋 — −50 reward:** ends the episode with a penalty.
- **Flag 🏁 — +100 reward:** ends the episode successfully.

The agent stores a Q-value for every state/action pair. During exploration, epsilon (ε) controls the chance of trying a random action. As episodes finish, epsilon falls and the agent increasingly follows actions with the highest learned values. Learning rate alpha (α) controls how strongly new experience changes a Q-value; discount gamma (γ) controls how much future reward matters.

### The five animated phases

Press **Step** to follow one Q-learning update in the Formula inspector:

1. **Current state:** observe the agent's grid square, selected action, and old `Q(s, a)`.
2. **Take action:** move to the next state and receive reward `R`.
3. **Find the target:** combine the reward with the best discounted future value, `R + γ max Q(s′, a′)`.
4. **Update the value:** blend the old value and target using alpha.
5. **Reflect:** compare the old and new Q-values and save the change.

Learning subtitles narrate each phase. Use **Subtitles on/off** to change only their visibility; it does not alter training. After phase five, training pauses so the result remains available to inspect. Continue with the **Continue** button, a character key when focus is not in a control, or a click/tap on the grid world or other non-interactive page area. Navigation, function, and modifier keys do not continue training.

## Controls and views

### Training

- **Step:** animate one action and its five formula phases.
- **Continue:** leave the post-step inspection pause.
- **Fast episode:** run one complete episode without phase-by-phase pauses.
- **Train 100:** run exactly 100 episodes in a responsive batch.
- **Reset:** cancel active work and restore the initial agent, parameters, Q-table, statistics, and charts.
- **Learning rate α:** adjust how quickly experience replaces old knowledge.
- **Future reward γ:** adjust the importance of later rewards.
- **Animation speed:** adjust phase and movement pacing.

### Grid views

- **World:** show the explorer, coins, hazards, goal, and current transition.
- **Q-Arrows:** show each action's learned direction, sign, and relative strength.
- **Heatmap:** color states by their strongest Q-value.

The Episode returns chart plots recent total rewards so learning progress can be compared over time. The expandable **How does Q-learning work?** tutorial defines the agent, state, action, reward, Q-value, alpha, gamma, and epsilon in terms of what appears in the game.

## Run locally

No build step or package installation is required. From the repository root, run:

```bash
python3 -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000).

## Deployment

GitHub Pages URL: <https://penguinkang.github.io/play-science/>

The GitHub Pages workflow publishes the static site after pushes to `main`. It can also be run manually from the Actions tab.

## Technology

Q-Learning Quest is a dependency-light static site:

- semantic HTML in `index.html`
- responsive custom CSS plus Tailwind CSS from its CDN
- vanilla JavaScript for the Q-learning engine and interface state
- Canvas 2D for the world, Q-Arrows, heatmap, movement, and return chart
- Python standard-library test harnesses that drive headless Chrome

It uses no framework, bundler, package manager, backend, or persistent storage.

## Tests

Run the static check and every browser suite from the repository root:

```bash
python3 tests/check-static.py
python3 tests/engine-browser.py
python3 tests/step-visualization-browser.py
python3 tests/views-browser.py
python3 tests/controls-browser.py
python3 tests/accessibility-browser.py
```
