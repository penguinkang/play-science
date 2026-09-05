#!/usr/bin/env python3
"""Exercise Canvas views, resizing, movement, and returns in Chrome."""

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
<title>Canvas views browser test</title>
<style>html, body { margin: 0; } iframe { display: block; border: 0; height: 900px; }</style>
<pre id="result">WAITING</pre>
<script>
const result = document.querySelector("#result");
const checks = [];
function check(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}
const pause = (win, delay = 32) => new Promise(resolve => win.setTimeout(resolve, delay));
const waitFrames = async (win, count = 2) => pause(win, count * 32);
const waitUntil = async (predicate, win, limit = 180) => {
  for (let attempt = 0; attempt < limit; attempt += 1) {
    if (predicate()) return;
    await pause(win, 16);
  }
  throw new Error("Timed out waiting for browser state");
};
const settleWithin = async (promise, win, delay = 250) => {
  const timeout = Symbol("timeout");
  const outcome = await Promise.race([
    promise,
    pause(win, delay).then(() => timeout),
  ]);
  check(outcome !== timeout, "canceled movement promise settles promptly");
  return outcome;
};
const frame = document.createElement("iframe");
frame.style.width = "1100px";
frame.addEventListener("load", async () => {
  try {
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    let unhandledRejection = null;
    win.addEventListener("unhandledrejection", event => {
      unhandledRejection = event.reason;
      event.preventDefault();
    });
    const api = win.__playScienceTest;
    check(api && typeof api.visualSnapshot === "function", "visual test API is exposed");
    doc.querySelector("[data-open-game]").click();
    await waitFrames(win, 3);

    let visual = api.visualSnapshot();
    check(visual.viewMode === "world", "World is the initial active view");
    const worldCanvas = doc.querySelector("#world-canvas");
    const rewardChart = doc.querySelector("#reward-chart");
    const worldSummary = doc.querySelector("#world-summary");
    const chartSummary = doc.querySelector("#reward-chart-summary");
    check(worldCanvas.getAttribute("aria-describedby") === "world-summary"
      && worldSummary.textContent.includes("World view")
      && worldSummary.textContent.includes("Agent: row 0, column 0")
      && worldSummary.textContent.includes("Goal: row 5, column 5")
      && worldSummary.textContent.includes("Coins remaining: row 0, column 2; row 3, column 4")
      && worldSummary.textContent.includes("Hazards: row 2, column 3; row 4, column 1"),
      "world Canvas describes its mode, agent, goal, coins, and hazards");
    check(rewardChart.getAttribute("aria-describedby") === "reward-chart-summary"
      && chartSummary.textContent.includes("No episode returns yet"),
      "return chart exposes a no-data text alternative");
    const initialWorldRedraws = visual.redraws.world;
    api.setQ([0, 0], "right", 5);
    const qButton = doc.querySelector('[data-view-mode="q-arrows"]');
    qButton.click();
    await waitFrames(win);
    visual = api.visualSnapshot();
    check(visual.viewMode === "q-arrows" && visual.redraws.world > initialWorldRedraws,
      "Q-Arrows changes active mode and redraws");
    check(qButton.getAttribute("aria-pressed") === "true", "Q-Arrows exposes its active state");
    check(worldSummary.textContent.includes("Q-Arrows view")
      && worldSummary.textContent.includes("row 0, column 0: right, 5.000000"),
      "Q-Arrows summary reports each cell's best action and value");
    const qSummary = worldSummary.textContent;
    const qRedraws = visual.redraws.world;
    doc.querySelector('[data-view-mode="heatmap"]').click();
    await waitFrames(win);
    visual = api.visualSnapshot();
    check(visual.viewMode === "heatmap" && visual.redraws.world > qRedraws,
      "Heatmap changes active mode and redraws");
    check(worldSummary.textContent !== qSummary
      && worldSummary.textContent.includes("Heatmap view")
      && worldSummary.textContent.includes("maximum Q range: 0.000000 to 5.000000")
      && worldSummary.textContent.includes("Current cell maximum Q: 5.000000"),
      "Heatmap summary reports the max-Q range and current-cell value");
    const heatmapRedraws = visual.redraws.world;
    const worldButton = doc.querySelector('[data-view-mode="world"]');
    worldButton.click();
    await waitFrames(win);
    visual = api.visualSnapshot();
    check(visual.viewMode === "world" && visual.redraws.world > heatmapRedraws,
      "World changes active mode and redraws");
    check(worldButton.getAttribute("aria-pressed") === "true", "World exposes its active state");

    check(visual.canvases.world.width > 0 && visual.canvases.world.height > 0,
      "world Canvas has desktop backing dimensions");
    check(visual.canvases.chart.width > 0 && visual.canvases.chart.height > 0,
      "return chart has desktop backing dimensions");
    const ratio = Math.max(1, win.devicePixelRatio || 1);
    check(ratio > 1, "browser test runs with a forced non-default DPR");
    check(visual.canvases.world.width === Math.round(worldCanvas.clientWidth * ratio),
      "world Canvas backing width follows desktop CSS width and DPR");
    check(visual.canvases.chart.height === Math.round(rewardChart.clientHeight * ratio),
      "chart backing height follows desktop CSS height and DPR");
    const desktopWorldWidth = visual.canvases.world.width;
    const stateBeforeResize = JSON.stringify(api.snapshot());
    check(doc.documentElement.scrollWidth <= doc.documentElement.clientWidth,
      "desktop layout has no horizontal overflow");

    frame.style.width = "390px";
    win.dispatchEvent(new Event("resize"));
    await new Promise(resolve => win.setTimeout(resolve, 80));
    await waitFrames(win, 3);
    visual = api.visualSnapshot();
    check(visual.canvases.world.width > 0 && visual.canvases.world.height > 0,
      "world Canvas has mobile backing dimensions");
    check(visual.canvases.chart.width > 0 && visual.canvases.chart.height > 0,
      "return chart has mobile backing dimensions");
    check(visual.canvases.world.width < desktopWorldWidth,
      "mobile resize reduces the world Canvas backing width");
    check(JSON.stringify(api.snapshot()) === stateBeforeResize,
      "view redraws and responsive resizing do not mutate engine state");
    const sample = worldCanvas.getContext("2d").getImageData(0, 0, 1, 1).data;
    check(sample[3] > 0, "world renderer paints Canvas pixels");
    check(doc.documentElement.scrollWidth <= doc.documentElement.clientWidth,
      "mobile layout has no horizontal overflow");

    api.reset();
    api.setEpsilon(0);
    api.setQ([0, 0], "right", 5);
    doc.querySelector("#animation-speed").value = "700";
    doc.querySelector("#step-button").click();
    await waitUntil(() => {
      const move = api.visualSnapshot().movement;
      return move.active && move.progress > 0 && move.progress < 1;
    }, win);
    visual = api.visualSnapshot();
    check(visual.movement.column > 0 && visual.movement.column < 1,
      "deterministic move interpolates before its destination");
    await waitUntil(() => !api.visualSnapshot().movement.active, win);
    check(JSON.stringify(api.snapshot().state) === "[0,1]",
      "deterministic move finishes at its logical destination");
    check(worldSummary.textContent.includes("Agent: row 0, column 1"),
      "world summary updates after a state transition");

    const beginMovement = async () => {
      api.reset();
      api.setEpsilon(0);
      api.setQ([0, 0], "right", 5);
      doc.querySelector("#animation-speed").value = "700";
      const promise = api.performAnimatedStep();
      await waitUntil(() => {
        const move = api.visualSnapshot().movement;
        return move.active && move.progress > 0 && move.progress < 1;
      }, win);
      return { promise };
    };
    let interrupted = await beginMovement();
    api.reset();
    let canceled = await settleWithin(interrupted.promise, win);
    check(canceled.canceled === true, "reset reports the active movement as canceled");
    check(!api.visualSnapshot().movement.active,
      "reset leaves no abandoned animated movement");

    interrupted = await beginMovement();
    const interruptedSnapshot = api.snapshot();
    const interruptedPhase = api.visualSnapshot().inspectorPhase;
    doc.querySelector("#fast-episode-button").click();
    doc.querySelector("#train-100-button").click();
    await pause(win, 80);
    check(api.visualSnapshot().movement.active
      && api.visualSnapshot().inspectorPhase === interruptedPhase
      && api.snapshot().episodes === interruptedSnapshot.episodes,
      "disabled fast and batch controls do not interrupt active movement");
    api.reset();
    canceled = await settleWithin(interrupted.promise, win);
    check(canceled.canceled === true,
      "reset still settles movement after ignored training-control activation");

    interrupted = await beginMovement();
    doc.querySelector("[data-close-game]").click();
    canceled = await settleWithin(interrupted.promise, win);
    check(canceled.canceled === true, "closing the game cancels and settles active movement");
    check(!api.visualSnapshot().movement.active,
      "closing the game leaves no abandoned animated movement");
    doc.querySelector("[data-open-game]").click();
    await waitFrames(win, 2);

    const originalMatchMedia = win.matchMedia;
    win.matchMedia = () => ({ matches: true });
    api.reset();
    api.setEpsilon(0);
    api.setQ([0, 0], "right", 5);
    const reducedMotionResult = await api.performAnimatedStep();
    win.matchMedia = originalMatchMedia;
    check(reducedMotionResult.canceled === false,
      "reduced motion completes without cancellation");
    check(!api.visualSnapshot().movement.active
      && api.visualSnapshot().movement.progress === 1,
      "reduced motion skips interpolation and reaches the destination");

    check(typeof api.returnChartLayout === "function",
      "return chart exposes its scale layout for regression tests");
    const negativeChart = api.returnChartLayout([-10, -30], 600, 180);
    check(negativeChart.domain.minimum === -30 && negativeChart.domain.maximum === 0,
      "all-negative returns include zero in the chart domain");
    check(negativeChart.labels.maximum.value === -10
      && negativeChart.labels.maximum.y === negativeChart.yFor(-10)
      && negativeChart.labels.maximum.y > negativeChart.plot.top,
      "all-negative maximum label is positioned at its actual value");
    const positiveChart = api.returnChartLayout([10, 30], 600, 180);
    check(positiveChart.domain.minimum === 0 && positiveChart.domain.maximum === 30,
      "all-positive returns include zero in the chart domain");
    check(positiveChart.labels.minimum.value === 10
      && positiveChart.labels.minimum.y === positiveChart.yFor(10)
      && positiveChart.labels.minimum.y < positiveChart.plot.bottom,
      "all-positive minimum label is positioned at its actual value");
    const clusteredChart = api.returnChartLayout([-99, -100], 600, 180);
    check(clusteredChart.labels.minimum.visible === false
      && clusteredChart.labels.maximum.visible === true,
      "chart suppresses overlapping return labels");

    const chartRedraws = api.visualSnapshot().redraws.chart;
    doc.querySelector("#train-100-button").click();
    await waitFrames(win, 2);
    visual = api.visualSnapshot();
    check(api.snapshot().returnHistory.length === 100,
      "silent training creates return history");
    check(visual.redraws.chart > chartRedraws && visual.chartPoints > 0,
      "silent training redraws return history chart");
    check(!chartSummary.textContent.includes("No episode returns yet")
      && chartSummary.textContent.includes("Recent returns")
      && /Trend: (improving|declining|steady)/.test(chartSummary.textContent),
      "return chart summary exposes recent values and their trend");
    api.reset();
    check(chartSummary.textContent.includes("No episode returns yet")
      && worldSummary.textContent.includes("World view")
      && worldSummary.textContent.includes("Agent: row 0, column 0"),
      "reset restores both Canvas text alternatives");
    check(unhandledRejection === null, "movement cancellation causes no unhandled rejection");

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
        if self.path == "/__views_test__":
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
    with tempfile.TemporaryDirectory(prefix="play-science-views-") as profile:
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1440,1000",
            "--force-device-scale-factor=2",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=15000",
            "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/__views_test__",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            output, browser_errors = process.communicate(timeout=20)
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
    excerpt = output[marker : marker + 1800] if marker >= 0 else output[-1800:]
    raise RuntimeError(
        "Browser views test failed.\n"
        f"Chrome exit code: {browser_exit_code}\n"
        f"DOM excerpt: {html.unescape(excerpt)}\n"
        f"Chrome stderr: {browser_errors[-1200:]}"
    )

start = output.find("PASS:")
end = output.find("</pre>", start)
print(html.unescape(output[start:end]))
