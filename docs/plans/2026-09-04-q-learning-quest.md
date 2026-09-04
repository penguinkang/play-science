# Q-Learning Quest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and deploy a responsive static science-game hub whose first game teaches tabular Q-learning through an animated 6×6 grid world with plain-language subtitles and user-paced update turns.

**Architecture:** Keep the product dependency-light: one `index.html` contains the UI, styling, Canvas rendering, Q-learning engine, and interaction state machine. Keep formulas and subtitles in semantic HTML while using Canvas for the grid and return chart. Expose a narrow `window.__playScienceTest` read-only/control surface so browser tests can verify calculations and phase transitions without coupling to Canvas pixels.

**Tech Stack:** HTML5, Canvas 2D, Tailwind CSS CDN, Vanilla JavaScript, Python static server, Playwright/browser automation, GitHub Actions, GitHub Pages.

---

### Task 1: Create an isolated implementation worktree and static test harness

**Files:**
- Create: `tests/browser-smoke.py`
- Create: `tests/check-static.py`
- Modify: `index.html`

**Step 1: Create the implementation branch/worktree**

Run from the repository root:

```bash
git worktree add ../play-science-q-learning -b feat/q-learning-quest
cd ../play-science-q-learning
```

Expected: a clean worktree on `feat/q-learning-quest` containing the approved design.

**Step 2: Write the failing static test**

Create `tests/check-static.py` using only the Python standard library. Assert that `index.html` contains unique IDs for `landing-screen`, `game-screen`, `world-canvas`, `formula-inspector`, `subtitle`, `subtitle-toggle`, `step-button`, `continue-button`, `fast-episode-button`, `train-100-button`, `reset-button`, and `reward-chart`.

**Step 3: Run the test to verify it fails**

Run:

```bash
python3 tests/check-static.py
```

Expected: FAIL because the application shell does not exist.

**Step 4: Implement the minimum application shell**

Create the semantic landing screen, one playable game tile, two coming-soon tiles, hidden game screen, responsive two-column game layout, formula inspector, subtitle region, canvases, controls, tutorial disclosure, and retro visual tokens in `index.html`. Load Tailwind from `https://cdn.tailwindcss.com` and include all custom CSS inline.

**Step 5: Run the static test**

Run:

```bash
python3 tests/check-static.py
```

Expected: PASS with all required landmarks found exactly once.

**Step 6: Commit**

```bash
git add index.html tests/check-static.py
git commit -m "feat: scaffold science game hub"
```

### Task 2: Implement and test the Q-learning engine

**Files:**
- Modify: `index.html`
- Create: `tests/engine-browser.py`

**Step 1: Write the failing browser engine test**

Create `tests/engine-browser.py` to load the site, wait for `networkidle`, open Q-Learning Quest, and use `window.__playScienceTest` to verify:

- 6×6 state space and four actions
- initial state `(0,0)`
- default hyperparameters `alpha=.1`, `gamma=.99`, `epsilon=1`, `epsilonDecay=.995`
- normal, coin, terminal-goal, and terminal-hazard rewards
- terminal target uses `maxNextQ = 0`
- an injected deterministic transition computes `target` and `newQ` from the documented formula

**Step 2: Run the test to verify it fails**

Serve the worktree and run the browser test. Expected: FAIL because the test API and engine are absent.

**Step 3: Implement the engine**

Inside `index.html`, add:

- constants for grid size, actions, goal, coins, and hazards
- Q-table creation and reset
- valid state transitions with boundary handling
- epsilon-greedy action selection with random tie-breaking
- frozen transition records containing `state`, `action`, `oldQ`, `nextState`, `reward`, `terminal`, `maxNextQ`, `target`, `newQ`, and `deltaQ`
- update commit separated from transition calculation
- episode reset, epsilon decay, max-step cap, and return history
- slider bindings with live values
- a narrow `window.__playScienceTest` API for snapshots and deterministic transition tests

Use zero bootstrap for terminal transitions.

**Step 4: Run the browser engine test**

Expected: all engine assertions PASS and no page errors.

**Step 5: Commit**

```bash
git add index.html tests/engine-browser.py
git commit -m "feat: add tabular q-learning engine"
```

### Task 3: Render the grid, views, movement, and chart

**Files:**
- Modify: `index.html`
- Create: `tests/views-browser.py`

**Step 1: Write the failing views test**

Verify that switching among World, Q-Arrows, and Heatmap updates the active mode in the test snapshot and redraw counter. Verify the canvases have nonzero backing dimensions at desktop and mobile viewport sizes. Trigger a deterministic move and assert that movement progresses before reaching the destination. Train several silent episodes and assert that return history is rendered.

**Step 2: Run the test to verify it fails**

Expected: FAIL because rendering and animation are incomplete.

**Step 3: Implement Canvas rendering**

Add device-pixel-ratio-aware resize helpers and rendering functions for:

- checkerboard grass/ground
- original emoji/CSS-inspired entities without external copyrighted assets
- agent interpolation between state centers
- current/next state highlights
- Q-value arrows with direction, relative scale, and sign-aware color
- normalized max-Q heatmap
- compact recent-return line chart with zero line and min/max labels

Use `ResizeObserver` and redraw without mutating engine state.

**Step 4: Implement movement animation**

Use `requestAnimationFrame`, elapsed-time interpolation, and reduced-motion detection. Keep logical state changes independent from render interpolation.

**Step 5: Run the views test at desktop and mobile widths**

Expected: PASS, nonzero canvases, mode changes recorded, movement observed, no horizontal page overflow.

**Step 6: Commit**

```bash
git add index.html tests/views-browser.py
git commit -m "feat: visualize q-learning grid and returns"
```

### Task 4: Build the five-phase formula inspector and subtitles

**Files:**
- Modify: `index.html`
- Create: `tests/step-visualization-browser.py`

**Step 1: Write the failing phase test**

Set animation delay to the minimum and force a deterministic nonterminal action. Click Step and collect phase changes. Assert the exact sequence `1,2,3,4,5,waiting`. For each phase, assert:

- phase 1 exposes current coordinates, action, and old Q
- phase 2 exposes reward and next coordinates
- phase 3 displays numeric `R + γ × maxQ = target`
- phase 4 displays numeric `(1 − α) × oldQ + α × target = newQ`
- phase 5 displays signed delta and commits exactly the displayed new Q
- formula values remain visible within a scrollable/wrapping inspector
- subtitle text is nonempty plain language

**Step 2: Run the test to verify it fails**

Expected: FAIL because the phase state machine is absent.

**Step 3: Implement the formula phase state machine**

Create a single async `runAnimatedStep()` guarded by a run token and busy state. Populate five persistent phase cards with consistently colored variables:

- alpha blue
- gamma purple
- reward gold
- Q green
- target orange

Animate the active phase, progressively substitute numbers, and use the frozen transition record for every displayed value. Ensure the inspector uses wrapping plus vertical overflow rather than clipping.

**Step 4: Implement phase subtitles**

Update a polite live-region subtitle with one concise explanation per sub-step, including concrete values. Add the subtitle toggle, update `aria-pressed`, and preserve the setting during the page session.

**Step 5: Run the phase test**

Expected: PASS with exact phase order, matching arithmetic, nonempty subtitles, and no clipping assertion failures.

**Step 6: Commit**

```bash
git add index.html tests/step-visualization-browser.py
git commit -m "feat: animate q-learning formula updates"
```

### Task 5: Add user-paced continuation and training controls

**Files:**
- Modify: `index.html`
- Create: `tests/controls-browser.py`

**Step 1: Write the failing pause test**

Run an animated step at minimum delay. After phase 5, assert the app stays in `waiting` longer than two phase delays and does not start another transition. Press a non-modifier key and assert the wait resolves. Repeat and resolve with the Continue button. Assert inputs originating from sliders/buttons do not accidentally double-start a transition.

**Step 2: Write failing control tests**

Verify:

- Fast Episode reaches a terminal or max-step result without entering `waiting`
- Train 100 increments completed episodes by exactly 100 and keeps the page responsive
- Reset during a wait cancels it, zeros the Q-table/history/counters, and restores the start state
- terminal animated steps wait before resetting the next episode
- stats and epsilon labels agree with the engine snapshot

**Step 3: Run tests to verify failure**

Expected: FAIL because continuation and full control behavior are absent.

**Step 4: Implement continuation**

Create an abortable promise for the post-update pause. Resolve it from the Continue button or document-level key input, excluding modifier-only presses and editable elements. Show a clear waiting banner. Invalidate pending work on Reset via a monotonically increasing run token.

**Step 5: Implement fast and batch modes**

Use the same transition-calculation and commit functions as animated mode. Skip formula delays and wait promises. Yield periodically during 100-episode training with `requestAnimationFrame` or `setTimeout(0)`. Disable conflicting controls while runs are active.

**Step 6: Run control tests**

Expected: PASS, including exact 100-episode delta and reset cancellation.

**Step 7: Commit**

```bash
git add index.html tests/controls-browser.py
git commit -m "feat: add paced and batch training controls"
```

### Task 6: Finish content, accessibility, and responsive QA

**Files:**
- Modify: `index.html`
- Modify: `README.md`
- Create: `tests/accessibility-browser.py`

**Step 1: Write the failing content/accessibility test**

Assert that:

- tutorial expands and includes agent/state/action/reward/Q-value/alpha/gamma/epsilon explanations
- all buttons have accessible names
- visible focus styling exists
- subtitle toggle works without changing engine state
- game can return to the library
- mobile viewport has no horizontal overflow
- no console errors or uncaught page errors occur during the core flow

**Step 2: Run the test to verify it fails**

Expected: FAIL on incomplete tutorial or accessibility behavior.

**Step 3: Complete tutorial and responsive polish**

Explain Q-learning in short sections and connect each variable to what users see. Add focus states, status semantics, reduced-motion behavior, responsive spacing/type, and a back-to-library control. Confirm the inspector grows or scrolls instead of truncating content.

**Step 4: Rewrite README**

Document:

- what Play Science and Q-Learning Quest teach
- entities/rewards
- five animated phases
- subtitle and continuation behavior
- training controls and view modes
- local launch command `python3 -m http.server 8000`
- deployment URL and technology choices

**Step 5: Run the full local test suite**

Run all static and browser tests. Expected: all PASS with no page errors.

**Step 6: Commit**

```bash
git add index.html README.md tests
git commit -m "docs: explain q-learning quest"
```

### Task 7: Add GitHub Pages deployment

**Files:**
- Create: `.github/workflows/deploy-pages.yml`
- Modify: `README.md`

**Step 1: Add a static workflow check**

Extend `tests/check-static.py` to assert the workflow uses:

- `actions/configure-pages`
- `actions/upload-pages-artifact`
- `actions/deploy-pages`
- `pages: write`
- `id-token: write`
- pushes to `main`

Run the test and expect FAIL before adding the workflow.

**Step 2: Add the Pages workflow**

Create a workflow that checks out the repository, configures Pages, uploads the repository root while excluding Git metadata, and deploys through the official Pages environment. Set explicit permissions and concurrency.

**Step 3: Run static checks**

Expected: PASS.

**Step 4: Commit**

```bash
git add .github/workflows/deploy-pages.yml README.md tests/check-static.py
git commit -m "ci: deploy site to github pages"
```

### Task 8: Final verification, integrate, and verify the live site

**Files:**
- Modify only if verification exposes defects.

**Step 1: Run all tests fresh**

Start a local server and run every test script. Expected: zero failures, zero console errors.

**Step 2: Perform visual browser QA**

Capture full-page screenshots at approximately 1440×1000 and 390×844. Inspect the landing page, world view, formula Phase 5, waiting state, arrows, heatmap, and expanded tutorial. Fix and retest any clipping, overlap, unreadable contrast, or overflow.

**Step 3: Review the diff and history**

```bash
git status --short
git diff main...HEAD --check
git log --oneline --decorate main..HEAD
```

Expected: clean status, no whitespace errors, focused commits.

**Step 4: Merge the feature branch locally**

After verified review, merge `feat/q-learning-quest` into `main` with a non-fast-forward merge unless repository policy dictates otherwise.

**Step 5: Change repository visibility and configure Pages**

Explicitly make `penguinkang/play-science` public. Configure Pages to use GitHub Actions if required by the API/settings.

**Step 6: Push main**

```bash
git push origin main
```

**Step 7: Verify external state**

Read back repository visibility, Pages configuration, and the pushed commit SHA. Watch the deployment workflow to completion with `gh run watch --exit-status`.

**Step 8: Verify the live deployment**

Fetch `https://penguinkang.github.io/play-science/`, confirm an HTTP success response and the expected page title, then run a short browser smoke test against the live URL.

**Step 9: Report exact evidence**

Report the repository URL, live Pages URL, pushed commit SHA, workflow run URL/conclusion, test counts, and any known limitations.
