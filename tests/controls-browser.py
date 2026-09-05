#!/usr/bin/env python3
"""Exercise paced continuation and training controls in a real browser."""

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
<title>Training controls browser test</title>
<pre id="result">WAITING</pre>
<script>
const result = document.querySelector("#result");
const checks = [];
function check(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}
const pause = (win, delay = 10) => new Promise(resolve => win.setTimeout(resolve, delay));
const waitUntil = async (predicate, win, message, limit = 1000) => {
  for (let attempt = 0; attempt < limit; attempt += 1) {
    if (predicate()) return;
    await pause(win);
  }
  throw new Error(`Timed out: ${message}`);
};
const frame = document.createElement("iframe");
frame.addEventListener("load", async () => {
  try {
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    const api = win.__playScienceTest;
    doc.querySelector("[data-open-game]").click();
    doc.querySelector("#animation-speed").value = "100";
    doc.querySelector("#subtitle-toggle").click();
    check(doc.querySelector("#subtitle").hidden,
      "learning subtitles can be hidden before an animated run");

    api.reset();
    api.setEpsilon(0);
    ["up", "down", "left"].forEach(action => api.setQ([0, 0], action, -2));
    api.setQ([0, 0], "right", 1);
    const beforeAnimatedControls = api.snapshot();
    const paced = api.runAnimatedStep();
    check(api.visualSnapshot().inspectorPhase === "1",
      "animated training enters phase 1 synchronously");
    check(doc.querySelector("#step-button").disabled
      && doc.querySelector("#fast-episode-button").disabled
      && doc.querySelector("#train-100-button").disabled,
      "every conflicting training control is disabled during animated phases");
    check(!doc.querySelector("#reset-button").disabled,
      "Reset remains available during animated phases");
    doc.querySelector("#fast-episode-button").click();
    doc.querySelector("#train-100-button").click();
    await pause(win, 25);
    check(api.visualSnapshot().inspectorPhase === "1"
      && api.snapshot().episodes === beforeAnimatedControls.episodes
      && api.snapshot().steps === beforeAnimatedControls.steps,
      "disabled training controls cannot cancel or replace an animated phase");
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "waiting", win, "first waiting state");
    const waitingSnapshot = api.snapshot();
    const waitingStatus = doc.querySelector("#waiting-status");
    check(waitingStatus && !waitingStatus.hidden
      && waitingStatus.getAttribute("role") === "status"
      && waitingStatus.textContent.includes("Continue")
      && doc.querySelector("#subtitle").hidden,
      "waiting has an explanatory status banner even when subtitles are off");
    check(doc.querySelector("#step-button").disabled
      && doc.querySelector("#fast-episode-button").disabled
      && doc.querySelector("#train-100-button").disabled
      && !doc.querySelector("#continue-button").disabled
      && !doc.querySelector("#reset-button").disabled,
      "waiting keeps training controls locked while Continue and Reset remain available");
    await pause(win, 250);
    check(api.visualSnapshot().inspectorPhase === "waiting"
      && api.snapshot().steps === waitingSnapshot.steps,
      "animated step remains waiting beyond two phase delays without a second transition");
    check(doc.querySelector("#continue-button").hidden === false
      && doc.querySelector("#step-button").hidden === true,
      "waiting state clearly offers Continue instead of Step");

    doc.dispatchEvent(new win.KeyboardEvent("keydown", { key: "Shift", shiftKey: true, bubbles: true }));
    await pause(win, 25);
    check(api.visualSnapshot().inspectorPhase === "waiting", "modifier-only keys do not continue training");
    const slider = doc.querySelector("#learning-rate");
    slider.focus();
    slider.dispatchEvent(new win.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    slider.click();
    doc.querySelector("#fast-episode-button").click();
    await pause(win, 25);
    check(api.visualSnapshot().inspectorPhase === "waiting"
      && api.snapshot().episodes === waitingSnapshot.episodes,
      "slider, button, and editable-origin input cannot resolve or double-start a waiting run");

    doc.body.focus();
    doc.dispatchEvent(new win.KeyboardEvent("keydown", { key: "x", bubbles: true }));
    const pacedResult = await paced;
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "idle", win, "keyboard continuation");
    check(!pacedResult.canceled,
      "a non-modifier document key resolves the paced wait");

    const continued = api.runAnimatedStep();
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "waiting", win, "button waiting state");
    doc.querySelector("#continue-button").click();
    check(!(await continued).canceled, "the animated transition completes before continuation");
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "idle", win, "button continuation");
    check(api.visualSnapshot().inspectorPhase === "idle",
      "the separate Continue button resolves the paced wait");

    const clicked = api.runAnimatedStep();
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "waiting", win, "pointer waiting state");
    doc.querySelector("#world-canvas").click();
    check(!(await clicked).canceled, "the pointer-run transition completes");
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "idle", win, "pointer continuation");
    check(api.visualSnapshot().inspectorPhase === "idle",
      "non-interactive click-anywhere continuation resolves the wait");

    api.reset();
    let sawWaitingDuringFast = false;
    const inspectorObserver = new win.MutationObserver(() => {
      if (api.visualSnapshot().inspectorPhase === "waiting") sawWaitingDuringFast = true;
    });
    inspectorObserver.observe(doc.querySelector("#formula-inspector"), { attributes: true });
    const beforeFast = api.snapshot().episodes;
    doc.querySelector("#fast-episode-button").click();
    await waitUntil(() => api.snapshot().episodes === beforeFast + 1, win, "fast episode completion");
    inspectorObserver.disconnect();
    const afterFast = api.snapshot();
    check(!sawWaitingDuringFast && afterFast.steps === 0 && afterFast.returnHistory.length === 1,
      "Fast Episode reaches terminal or max-step completion without waiting");

    const beforeBatch = afterFast.episodes;
    let responsive = false;
    win.setTimeout(() => { responsive = true; }, 0);
    doc.querySelector("#train-100-button").click();
    check(doc.querySelector("#step-button").disabled
      && doc.querySelector("#fast-episode-button").disabled
      && doc.querySelector("#train-100-button").disabled,
      "conflicting training controls are disabled while a batch runs");
    await waitUntil(() => api.snapshot().episodes === beforeBatch + 100
      && !doc.querySelector("#train-100-button").disabled, win, "100 episode training", 3000);
    check(responsive && api.snapshot().returnHistory.length === beforeBatch + 100,
      "Train 100 completes exactly 100 episodes and yields to keep the page responsive");
    check(!doc.querySelector("#step-button").disabled
      && !doc.querySelector("#fast-episode-button").disabled
      && !doc.querySelector("#train-100-button").disabled,
      "training controls are restored after a batch");

    api.reset();
    api.setEpsilon(0);
    api.setQ([0, 0], "right", 3);
    const resetRun = api.runAnimatedStep();
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "waiting", win, "reset waiting state");
    doc.querySelector("#reset-button").click();
    await resetRun;
    const resetSnapshot = api.snapshot();
    check(JSON.stringify(resetSnapshot.state) === "[0,0]"
      && resetSnapshot.episodes === 0 && resetSnapshot.steps === 0
      && resetSnapshot.episodeReturn === 0 && resetSnapshot.returnHistory.length === 0
      && resetSnapshot.qTable.flat().every(value => value === 0)
      && api.visualSnapshot().inspectorPhase === "idle",
      "Reset during a wait cancels it and restores all engine and interface state");

    api.reset();
    api.setEpsilon(0);
    api.setState([4, 5]);
    ["up", "right", "left"].forEach(action => api.setQ([4, 5], action, -2));
    api.setQ([4, 5], "down", 5);
    const terminalRun = api.runAnimatedStep();
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "waiting", win, "terminal waiting state");
    check(JSON.stringify(api.snapshot().state) === "[5,5]"
      && api.snapshot().episodes === 0 && api.snapshot().steps === 1,
      "terminal animated step waits on the terminal state before episode reset");
    const terminalResult = await terminalRun;
    doc.querySelector("#continue-button").click();
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "idle", win, "terminal continuation");
    check(terminalResult.summary?.terminal && api.snapshot().episodes === 1
      && JSON.stringify(api.snapshot().state) === "[0,0]" && api.snapshot().steps === 0,
      "continuing a terminal step completes and resets the episode");

    const labels = [...doc.querySelectorAll(".stats dd")].map(node => node.textContent.trim());
    const finalSnapshot = api.snapshot();
    check(labels[0] === String(finalSnapshot.episodes)
      && labels[1] === String(finalSnapshot.episodeReturn)
      && labels[2] === String(finalSnapshot.steps)
      && labels[3] === finalSnapshot.epsilon.toFixed(2),
      "statistics and epsilon labels match the engine snapshot");

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
        if self.path == "/__controls_test__":
            self.send_html(HARNESS.encode())
            return
        if self.path == "/index.html":
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
    with tempfile.TemporaryDirectory(prefix="play-science-controls-") as profile:
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--force-prefers-reduced-motion=reduce",
            "--window-size=900,1000",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=35000",
            "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/__controls_test__",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            output, browser_errors = process.communicate(timeout=42)
        except subprocess.TimeoutExpired:
            process.kill()
            output, browser_errors = process.communicate()
        browser_exit_code = process.returncode
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)

if 'data-status="pass"' not in output:
    marker = output.find('id="result"')
    excerpt = output[marker : marker + 2600] if marker >= 0 else output[-2600:]
    raise RuntimeError(
        "Browser controls test failed.\n"
        f"Chrome exit code: {browser_exit_code}\n"
        f"DOM excerpt: {html.unescape(excerpt)}\n"
        f"Chrome stderr: {browser_errors[-1200:]}"
    )

start = output.find("PASS:")
end = output.find("</pre>", start)
print(html.unescape(output[start:end]))
