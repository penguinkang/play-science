#!/usr/bin/env python3
"""Exercise the five-phase Q-learning inspector in a real browser."""

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
<title>Step visualization browser test</title>
<style>html, body { margin: 0; } iframe { display: block; border: 0; width: 390px; height: 900px; }</style>
<pre id="result">WAITING</pre>
<script>
const result = document.querySelector("#result");
const checks = [];
function check(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}
const pause = (win, delay = 10) => new Promise(resolve => win.setTimeout(resolve, delay));
const waitUntil = async (predicate, win, limit = 500) => {
  for (let attempt = 0; attempt < limit; attempt += 1) {
    if (predicate()) return;
    await pause(win);
  }
  throw new Error("Timed out waiting for inspector phase");
};
const roundTo = (value, places) => {
  const scale = 10 ** places;
  return Math.round((value + Number.EPSILON) * scale) / scale;
};
const frame = document.createElement("iframe");
frame.addEventListener("load", async () => {
  try {
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    const api = win.__playScienceTest;
    check(api && typeof api.runAnimatedStep === "function", "animated-step test API is exposed");
    check(win.matchMedia("(prefers-reduced-motion: reduce)").matches,
      "browser test emulates reduced motion");
    doc.querySelector("[data-open-game]").click();
    api.reset();
    api.setEpsilon(0);
    api.setQ([0, 0], "right", 2);
    api.setQ([0, 1], "right", 8);
    doc.querySelector("#animation-speed").value = "100";

    const inspector = doc.querySelector("#formula-inspector");
    const subtitle = doc.querySelector("#subtitle");
    const seen = [];
    const subtitles = new Map();
    const observedAt = new Map();
    const capture = () => {
      const phase = inspector.dataset.inspectorPhase;
      if (phase && seen.at(-1) !== phase) {
        seen.push(phase);
        subtitles.set(phase, subtitle.textContent.trim());
        observedAt.set(phase, win.performance.now());
      }
    };
    const observer = new win.MutationObserver(capture);
    observer.observe(inspector, { attributes: true, subtree: true, childList: true, characterData: true });

    doc.querySelector("#step-button").click();
    await waitUntil(() => inspector.dataset.inspectorPhase === "1", win);
    await pause(win, 40);
    check(inspector.dataset.inspectorPhase === "1" && subtitle.textContent.includes("First"),
      "reduced motion preserves readable phase timing and its subtitle");
    check(api.getQ([0, 0], "right") === 2, "Q-value is not committed during phase 1");
    check(doc.querySelector('[data-phase="1"]').textContent.includes("State (0, 0)")
      && doc.querySelector('[data-phase="1"]').textContent.includes("action right")
      && doc.querySelector('[data-phase="1"]').textContent.includes("old Q = 2.000000"),
      "phase 1 shows current coordinates, action, and old Q");
    check(doc.querySelectorAll(".formula-card").length === 5,
      "all five semantic formula cards persist throughout the animation");
    check(api.visualSnapshot().stepBusy && doc.querySelector("#step-button").disabled,
      "a run token busy state guards concurrent steps");
    doc.querySelector("#step-button").click();

    await waitUntil(() => inspector.dataset.inspectorPhase === "2", win);
    check(doc.querySelector('[data-phase="2"]').textContent.includes("R = -1")
      && doc.querySelector('[data-phase="2"]').textContent.includes("next state (0, 1)"),
      "phase 2 shows reward and next coordinates");
    check(api.getQ([0, 0], "right") === 2, "Q-value remains old during phase 2");
    doc.querySelector("#learning-rate").value = "0.75";
    doc.querySelector("#learning-rate").dispatchEvent(new Event("input", { bubbles: true }));
    doc.querySelector("#discount-rate").value = "0.25";
    doc.querySelector("#discount-rate").dispatchEvent(new Event("input", { bubbles: true }));

    await waitUntil(() => inspector.dataset.inspectorPhase === "3", win);
    check(doc.querySelector('[data-phase="3"] .formula').textContent.trim()
      === "-1.000000 + 0.990000 × 8.000000 ≈ 6.920000",
      "phase 3 substitutes R + gamma times max Q into the target");
    await waitUntil(() => inspector.dataset.inspectorPhase === "4", win);
    check(doc.querySelector('[data-phase="4"] .formula').textContent.trim()
      === "(1 − 0.100000) × 2.000000 + 0.100000 × 6.920000 ≈ 2.492000",
      "phase 4 substitutes old Q, alpha, target, and new Q");
    await waitUntil(() => inspector.dataset.inspectorPhase === "5", win);
    check(doc.querySelector('[data-phase="5"] .formula').textContent.trim()
      === "+0.492000 · Q(0, 0, right) = 2.492000",
      "phase 5 shows the signed delta and committed Q-value");
    check(api.getQ([0, 0], "right") === 2.492,
      "phase 5 commits exactly the displayed Q-value");

    await waitUntil(() => inspector.dataset.inspectorPhase === "waiting", win);
    observer.disconnect();
    capture();
    check(seen.join(",") === "1,2,3,4,5,waiting",
      `inspector emits exact ordered phases (received ${seen.join(",")})`);
    check(["1", "2", "3", "4", "5"].every((phase, index, phases) =>
      index === phases.length - 1 || observedAt.get(phases[index + 1]) - observedAt.get(phase) >= 50),
      "reduced motion keeps each instructional phase observable over time");
    check(["1", "2", "3", "4", "5"].every(phase =>
      subtitles.get(phase) && subtitles.get(phase).length >= 20 && !/[=×γΔ]/.test(subtitles.get(phase))),
      "every phase has a nonempty plain-language subtitle");
    check(!doc.querySelector("#continue-button").hidden && doc.querySelector("#step-button").hidden,
      "waiting state shows Continue without auto-advancing");
    check(!api.visualSnapshot().stepBusy, "waiting state releases the busy guard");

    const style = win.getComputedStyle(inspector);
    check(["auto", "scroll"].includes(style.overflowY) && style.overflowWrap === "anywhere",
      "formula inspector wraps and can scroll instead of clipping");
    check(inspector.scrollWidth <= inspector.clientWidth,
      "formula content is not horizontally clipped on a narrow viewport");
    check([...doc.querySelectorAll(".formula-card")].every(card => card.getBoundingClientRect().width <= inspector.clientWidth),
      "every formula card stays within the inspector width");
    check(["alpha", "gamma", "reward", "q-value", "target"].every(name =>
      doc.querySelector(`#formula-inspector .${name}`)),
      "formula roles retain alpha, gamma, reward, Q, and target color hooks");

    const toggle = doc.querySelector("#subtitle-toggle");
    check(subtitle.getAttribute("aria-live") === "polite", "subtitles use a polite live region");
    toggle.click();
    check(toggle.getAttribute("aria-pressed") === "false" && subtitle.hidden,
      "subtitle toggle updates aria-pressed and visibility");
    api.reset();
    check(toggle.getAttribute("aria-pressed") === "false" && subtitle.hidden,
      "subtitle preference is retained during the page session");
    check(inspector.dataset.inspectorPhase === "idle" && doc.querySelector("#continue-button").hidden,
      "reset test API cancels the run and restores a non-deadlocked idle state");

    api.setEpsilon(0);
    api.setQ([0, 0], "right", 2);
    doc.querySelector("#animation-speed").value = "1500";
    const interrupted = api.runAnimatedStep();
    await waitUntil(() => inspector.dataset.inspectorPhase === "1", win);
    api.reset();
    const timeout = Symbol("timeout");
    const cancellation = await Promise.race([
      interrupted,
      pause(win, 250).then(() => timeout),
    ]);
    check(cancellation !== timeout && cancellation.canceled,
      "reset settles a phase delay without deadlocking the animated run");
    check(inspector.dataset.inspectorPhase === "idle" && !api.visualSnapshot().stepBusy,
      "reset leaves the test API idle after interrupting a phase");

    api.setEpsilon(0);
    ["up", "down", "left"].forEach(action => api.setQ([0, 0], action, -3));
    api.setQ([0, 0], "right", -2);
    api.setQ([0, 1], "right", 0.0048);
    doc.querySelector("#animation-speed").value = "100";
    const precisionRun = api.runAnimatedStep();
    await waitUntil(() => inspector.dataset.inspectorPhase === "3", win);
    const precision = Number(inspector.dataset.valuePrecision);
    check(precision === 6, "formula inspector documents six-decimal value precision");
    const phase3Values = [...doc.querySelectorAll('[data-phase="3"] [data-value]')]
      .map(node => Number(node.dataset.value));
    check(roundTo(phase3Values[0] + phase3Values[1] * phase3Values[2], precision) === phase3Values[3],
      "displayed target operands reproduce the displayed target at declared precision");
    await waitUntil(() => inspector.dataset.inspectorPhase === "4", win);
    const phase4Values = [...doc.querySelectorAll('[data-phase="4"] [data-value]')]
      .map(node => Number(node.dataset.value));
    check(roundTo((1 - phase4Values[0]) * phase4Values[1]
      + phase4Values[2] * phase4Values[3], precision) === phase4Values[4],
      "displayed update operands reproduce displayed new Q at declared precision");
    await waitUntil(() => inspector.dataset.inspectorPhase === "5", win);
    const shownNewQ = Number(doc.querySelector('[data-phase="5"] [data-new-q]').dataset.value);
    check(shownNewQ === -1.899525 && api.getQ([0, 0], "right") === shownNewQ,
      "phase 5 commits exactly the non-exact numeric new Q it displays");
    check([...inspector.querySelectorAll("[data-value]")].every(node =>
      Number(node.textContent) === Number(node.dataset.value)),
      "formula text and exposed numeric operands come from the same quantized values");
    await precisionRun;

    api.reset();
    api.setEpsilon(0);
    api.setQ([0, 0], "right", 2);
    doc.querySelector("#animation-speed").value = "100";
    const movedThenCanceled = api.runAnimatedStep();
    await waitUntil(() => inspector.dataset.inspectorPhase === "3", win);
    doc.querySelector("[data-close-game]").click();
    const canceledAfterMovement = await movedThenCanceled;
    check(canceledAfterMovement.canceled
      && JSON.stringify(api.snapshot().state) === "[0,0]"
      && api.getQ([0, 0], "right") === 2
      && api.snapshot().steps === 0,
      "canceling after movement rolls back the uncommitted transition");

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
        if self.path == "/__step_visualization_test__":
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
    with tempfile.TemporaryDirectory(prefix="play-science-step-") as profile:
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--force-prefers-reduced-motion=reduce",
            "--window-size=430,1000",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=12000",
            "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/__step_visualization_test__",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            output, browser_errors = process.communicate(timeout=18)
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
    excerpt = output[marker : marker + 2200] if marker >= 0 else output[-2200:]
    raise RuntimeError(
        "Browser step visualization test failed.\n"
        f"Chrome exit code: {browser_exit_code}\n"
        f"DOM excerpt: {html.unescape(excerpt)}\n"
        f"Chrome stderr: {browser_errors[-1200:]}"
    )

start = output.find("PASS:")
end = output.find("</pre>", start)
print(html.unescape(output[start:end]))
