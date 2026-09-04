# Q-Learning Quest Design

## Purpose

Build the first playable experience in `play-science`: a browser-based science-game hub whose initial game teaches tabular Q-learning through a retro platform-game-inspired 6×6 grid world. The application should favor clarity and learning over simulation speed while still supporting fast and batch training.

## Application structure

The application remains a static site. `index.html` contains all application markup, custom CSS, and JavaScript; Tailwind CSS is loaded from its CDN. `README.md` documents the game and controls. A GitHub Actions workflow deploys the static files to GitHub Pages.

The first screen is a game library made from responsive tiles. “Q-Learning Quest” is playable. Additional tiles are visually marked “Coming soon” so the library can grow without implying unfinished games are available.

## Visual direction

Use an original retro pixel-game treatment inspired by classic platform games without depending on copyrighted image assets. Emoji and CSS-drawn scenery represent the agent, goal, coins, hazards, and grass. A bright sky palette, blocky borders, pixel-like shadows, and readable typography create the theme.

The game screen uses a responsive two-column layout on desktop and a single-column layout on smaller screens. The left side contains the Canvas grid, view controls, training controls, statistics, and a compact return chart. The right side contains a DOM-based formula inspector. Keeping math in the DOM prevents clipping, supports scrolling, and makes the explanation accessible and testable.

## Environment and learning engine

The environment is a fixed 6×6 grid. The agent begins at `(0, 0)`. It contains one terminal goal worth `+100`, multiple collectible coins worth `+10`, terminal hazards worth `−50`, and normal steps worth `−1`. Available actions are up, down, left, and right. Attempts to leave the board keep the agent in the same cell and receive the normal step penalty.

The Q-table stores four values per state. Actions are selected epsilon-greedily, with random tie-breaking among equally valued greedy actions. Every transition applies:

`Q(s,a) ← (1 − α)Q(s,a) + α[R + γ max Q(s′,a′)]`

Terminal transitions use a next-state maximum of zero. Epsilon decays at episode boundaries and does not fall below a small practical floor. Reset restores the table, agent, counters, rewards, coins, and default hyperparameters.

## Animated learning step

The Step control runs one transition through five sequential phases:

1. **Current state** — highlight `s`, the selected action, and `Q(s,a)`.
2. **Take action** — animate movement with `requestAnimationFrame`, then reveal `R` and `s′`.
3. **Target** — show all next-state action values, highlight the maximum, and substitute numbers into `R + γ max Q(s′,a′)`.
4. **New value** — substitute numbers into `(1 − α)Q_old + α Target`.
5. **Reflect** — commit the table update, refresh the selected visualization, and animate the signed `ΔQ` in green or red.

Each phase uses the speed slider’s delay. Formula values are derived from a frozen transition record so the displayed arithmetic exactly matches the update performed by the engine.

After Phase 5, the application enters a deliberate interpretation pause. A visible Continue control appears and the subtitle explains that training is waiting. A click on Continue or a keyboard input resumes. Pointer input outside interactive controls may also resume without accidentally activating another training action. Step controls remain locked while a transition is active.

Fast Episode performs transitions without phase animation or interpretation pauses. Train 100 Episodes runs silently in chunks that yield to the browser so the page remains responsive, then redraws the visualizations.

## Subtitle system

A persistent subtitle area translates each formula phase into plain language. A toggle hides or reveals this area without changing training behavior. The text updates for every phase and includes concrete values and coordinates when useful. The preference is retained for the current page session.

## Views and reporting

The game Canvas supports:

- **World:** entities, remaining coins, hazards, goal, and agent.
- **Q-value arrows:** directional arrows in each non-terminal state, with intensity and size based on relative Q-values.
- **Heatmap:** cell colors based on each state’s maximum Q-value, normalized against current table extrema.

Statistics show completed episodes, current episode reward, current step count, and epsilon. A small Canvas chart plots recent episode returns and rescales as data changes.

## Responsive behavior and accessibility

Canvas dimensions follow their containers while preserving crisp rendering through device-pixel-ratio scaling. The formula panel uses wrapping and internal overflow safeguards, never fixed-height clipping. Buttons expose clear labels and visible focus states. Controls are reachable by keyboard. Motion is shortened when the user requests reduced motion.

## Error and edge handling

Training controls are guarded against concurrent runs. Reset cancels pending waits and invalidates any active run. Terminal transitions do not bootstrap from next-state Q-values. Episode runs use a maximum-step cap to prevent unbounded loops. Resizing triggers redraws but does not reset learning state.

## Testing and deployment

Browser automation will verify navigation, controls, all five phases, numeric update consistency, subtitle toggling, interpretation pause by button and keyboard, terminal episode handling, reset, batch training, view changes, and responsive rendering. Tests will capture console errors and screenshots.

The repository will be public. GitHub Actions will publish the repository root as a GitHub Pages artifact using the official Pages actions. Completion requires a successful workflow run and a live response from `https://penguinkang.github.io/play-science/`.
