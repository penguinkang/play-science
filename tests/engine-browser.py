#!/usr/bin/env python3
"""Exercise the Q-learning engine in a real, headless browser."""

from __future__ import annotations

import html
import http.server
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)

HARNESS = r"""<!doctype html>
<meta charset="utf-8">
<title>Q-learning engine browser test</title>
<pre id="result">WAITING</pre>
<script>
const result = document.querySelector("#result");
const checks = [];
function check(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}
function closeTo(actual, expected, message) {
  check(Math.abs(actual - expected) < 1e-10,
    `${message}: expected ${expected}, received ${actual}`);
}
const frame = document.createElement("iframe");
frame.addEventListener("load", () => {
  try {
    const api = frame.contentWindow.__playScienceTest;
    check(api && typeof api.snapshot === "function", "test API is exposed");

    let snapshot = api.snapshot();
    check(snapshot.rows === 6 && snapshot.columns === 6, "state space is 6x6");
    check(snapshot.actions.join(",") === "up,right,down,left", "four actions are exposed");
    check(JSON.stringify(snapshot.state) === "[0,0]", "initial state is (0,0)");
    closeTo(snapshot.alpha, 0.1, "default alpha");
    closeTo(snapshot.gamma, 0.99, "default gamma");
    closeTo(snapshot.epsilon, 1, "default epsilon");
    closeTo(snapshot.epsilonDecay, 0.995, "default epsilon decay");
    closeTo(snapshot.epsilonMin, 0.02, "minimum epsilon");
    check(JSON.stringify(snapshot.remainingCoins) === "[[0,2],[3,4]]",
      "snapshot exposes the episode's remaining coins");
    snapshot.remainingCoins[0][0] = 99;
    check(api.snapshot().remainingCoins[0][0] === 0,
      "snapshot cannot mutate the engine's remaining coins");
    check(snapshot.qTable.length === 36, "Q-table has one row per state");
    check(snapshot.qTable.every(row => row.length === 4 && row.every(value => value === 0)),
      "Q-table starts at zero");

    const boundary = api.transition([0, 0], "up");
    check(JSON.stringify(boundary.nextState) === "[0,0]", "boundaries keep the agent in place");
    check(boundary.reward === -1 && boundary.terminal === false, "normal transition rewards -1");

    const coin = api.transition([0, 1], "right");
    check(coin.reward === 10 && coin.terminal === false, "coin rewards +10 without terminating");
    const revisitedCoin = api.transition([0, 1], "right");
    check(revisitedCoin.reward === -1 && revisitedCoin.terminal === false,
      "a collected coin rewards -1 when revisited in the same episode");
    api.runEpisode(() => 0);
    const restoredCoin = api.transition([0, 1], "right");
    check(restoredCoin.reward === 10,
      "episode completion restores coins for the next episode");
    const hazard = api.transition([1, 3], "down");
    check(hazard.reward === -50 && hazard.terminal === true, "hazard rewards -50 and terminates");
    const goal = api.transition([5, 4], "right");
    check(goal.reward === 100 && goal.terminal === true, "goal rewards +100 and terminates");

    api.reset();
    check(JSON.stringify(api.snapshot().remainingCoins) === "[[0,2],[3,4]]",
      "full reset restores all coins");
    api.setQ([0, 0], "right", 2);
    api.setQ([0, 1], "up", 3);
    api.setQ([0, 1], "right", 8);
    const update = api.calculateTransition({
      state: [0, 0], action: "right", nextState: [0, 1], reward: -1, terminal: false
    });
    check(Object.isFrozen(update) && Object.isFrozen(update.state) && Object.isFrozen(update.nextState),
      "transition record is frozen");
    check(Object.keys(update).join(",") ===
      "state,action,oldQ,nextState,reward,terminal,maxNextQ,target,newQ,deltaQ",
      "transition record has the required fields");
    closeTo(update.oldQ, 2, "injected old Q");
    closeTo(update.maxNextQ, 8, "maximum next Q");
    closeTo(update.target, -1 + 0.99 * 8, "non-terminal target formula");
    closeTo(update.newQ, 2 + 0.1 * ((-1 + 0.99 * 8) - 2), "new Q formula");
    closeTo(update.deltaQ, update.newQ - update.oldQ, "delta Q formula");
    closeTo(api.getQ([0, 0], "right"), 2, "calculation does not commit");
    api.commitTransition(update);
    closeTo(api.getQ([0, 0], "right"), update.newQ, "commit stores calculated Q");

    api.reset();
    api.setEpsilon(0);
    api.setQ([0, 0], "right", 5);
    api.setQ([0, 0], "down", 5);
    check(api.chooseAction([0, 0], () => 0.99) === "down",
      "greedy action breaks maximum-Q ties randomly");

    api.setQ([2, 2], "up", 999);
    const terminalUpdate = api.calculateTransition({
      state: [1, 2], action: "down", nextState: [2, 2], reward: -50, terminal: true
    });
    check(terminalUpdate.maxNextQ === 0, "terminal transition has maxNextQ 0");
    check(terminalUpdate.target === -50, "terminal target excludes future Q");

    const alpha = frame.contentDocument.querySelector("#learning-rate");
    alpha.value = "0.25";
    alpha.dispatchEvent(new Event("input", {bubbles: true}));
    closeTo(api.snapshot().alpha, 0.25, "alpha slider updates engine live");
    check(alpha.previousElementSibling.querySelector("output").value === "0.25",
      "alpha slider updates its output");
    const gamma = frame.contentDocument.querySelector("#discount-rate");
    gamma.value = "0.75";
    gamma.dispatchEvent(new Event("input", {bubbles: true}));
    closeTo(api.snapshot().gamma, 0.75, "gamma slider updates engine live");
    check(gamma.previousElementSibling.querySelector("output").value === "0.75",
      "gamma slider updates its output");

    api.reset();
    const cappedEpisode = api.runEpisode(() => 0);
    snapshot = api.snapshot();
    check(cappedEpisode.steps === 100 && cappedEpisode.terminal === false,
      "episode stops at the maximum step count");
    check(snapshot.episodes === 1 && snapshot.returnHistory.length === 1,
      "completed episode is added to return history");
    closeTo(snapshot.epsilon, 0.995, "episode completion decays epsilon");
    check(JSON.stringify(snapshot.state) === "[0,0]" && snapshot.steps === 0,
      "episode completion resets agent state and step count");

    api.reset();
    api.setEpsilon(0.02001);
    api.runEpisode(() => 0);
    closeTo(api.snapshot().epsilon, 0.02, "episode decay clamps epsilon to its minimum");

    api.reset();
    snapshot = api.snapshot();
    check(snapshot.episodes === 0 && snapshot.steps === 0 && snapshot.episodeReturn === 0,
      "reset clears episode counters");
    check(snapshot.returnHistory.length === 0, "reset clears return history");
    check(snapshot.epsilon === 1, "reset restores epsilon");
    check(snapshot.alpha === 0.1 && snapshot.gamma === 0.99, "reset restores learning defaults");

    result.dataset.status = "pass";
    result.textContent = `PASS: ${checks.length} browser checks`;
  } catch (error) {
    result.dataset.status = "fail";
    result.textContent = `FAIL: ${error.stack || error}`;
  }
});
frame.src = "/index.html";
document.body.append(frame);
</script>
"""


class TestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path == "/__engine_test__":
            self.send_html(HARNESS.encode())
            return
        if self.path == "/index.html":
            # The CDN provides styling only. Remove it in tests so browser startup
            # is deterministic and the inline application runs without a network.
            source = (ROOT / "index.html").read_text(encoding="utf-8")
            source = source.replace(
                '<script src="https://cdn.tailwindcss.com"></script>',
                "<!-- Tailwind CDN omitted by browser test server -->",
            )
            self.send_html(source.encode())
            return
        super().do_GET()

    def log_message(self, format: str, *args: object) -> None:
        pass


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for command in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(command)
        if found:
            return found
    raise RuntimeError("No Chrome/Chromium browser found")


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

try:
    with tempfile.TemporaryDirectory(prefix="play-science-chrome-") as profile:
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=5000",
            "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/__engine_test__",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            output, browser_errors = process.communicate(timeout=12)
        except subprocess.TimeoutExpired:
            # Current macOS Chrome can leave background services alive after
            # --dump-dom has emitted the complete document.
            process.kill()
            output, browser_errors = process.communicate()
        browser_exit_code = process.returncode
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)

if 'data-status="pass"' not in output:
    marker = output.find('id="result"')
    excerpt = output[marker : marker + 1200] if marker >= 0 else output[-1200:]
    raise RuntimeError(
        "Browser engine test failed.\n"
        f"Chrome exit code: {browser_exit_code}\n"
        f"DOM excerpt: {html.unescape(excerpt)}\n"
        f"Chrome stderr: {browser_errors[-1200:]}"
    )

start = output.find("PASS:")
end = output.find("</pre>", start)
print(html.unescape(output[start:end]))
