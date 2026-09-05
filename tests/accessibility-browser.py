#!/usr/bin/env python3
"""Exercise Task 6 content, accessibility, and responsive behavior in Chrome."""

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

ERROR_CAPTURE = r"""<script>
window.__task6Errors = [];
window.addEventListener("error", event => window.__task6Errors.push(`page: ${event.message}`));
window.addEventListener("unhandledrejection", event => window.__task6Errors.push(`promise: ${event.reason}`));
const originalConsoleError = console.error;
console.error = (...args) => {
  window.__task6Errors.push(`console: ${args.map(String).join(" ")}`);
  originalConsoleError.apply(console, args);
};
</script>"""

HARNESS = r"""<!doctype html>
<meta charset="utf-8">
<title>Task 6 accessibility browser test</title>
<style>html, body { margin: 0; } iframe { display: block; width: 390px; height: 1000px; border: 0; }</style>
<pre id="result">WAITING</pre>
<script>
const result = document.querySelector("#result");
const checks = [];
function check(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}
const pause = (win, delay = 32) => new Promise(resolve => win.setTimeout(resolve, delay));
const waitUntil = async (predicate, win, message, limit = 400) => {
  for (let attempt = 0; attempt < limit; attempt += 1) {
    if (predicate()) return;
    await pause(win, 16);
  }
  throw new Error(`Timed out: ${message}`);
};
const frame = document.createElement("iframe");
frame.addEventListener("load", async () => {
  try {
    const win = frame.contentWindow;
    const doc = frame.contentDocument;
    const api = win.__playScienceTest;
    check(api && typeof api.snapshot === "function", "test API is available");

    doc.querySelector("[data-open-game]").click();
    await pause(win);
    check(!doc.querySelector("#game-screen").hidden, "quest opens from the library");

    const tutorial = doc.querySelector("#q-learning-tutorial");
    check(tutorial instanceof win.HTMLDetailsElement, "tutorial uses an expandable disclosure");
    tutorial.querySelector("summary").click();
    check(tutorial.open, "tutorial expands from its summary");
    const expectedTerms = ["agent", "state", "action", "reward", "q-value", "alpha", "gamma", "epsilon"];
    const terms = [...tutorial.querySelectorAll("[data-tutorial-term]")]
      .map(node => node.dataset.tutorialTerm);
    expectedTerms.forEach(term => check(terms.includes(term), `tutorial explains ${term}`));

    const unnamedButtons = [...doc.querySelectorAll("button")].filter(button => {
      const name = button.getAttribute("aria-label") || button.getAttribute("aria-labelledby") || button.textContent.trim();
      return !name;
    });
    check(unnamedButtons.length === 0, "every button has an accessible name");

    const focusTarget = doc.querySelector("#step-button");
    focusTarget.focus();
    const focusStyle = win.getComputedStyle(focusTarget);
    check(focusStyle.outlineStyle !== "none" && parseFloat(focusStyle.outlineWidth) >= 2,
      "keyboard focus has a visible outline");

    const beforeSubtitle = JSON.stringify(api.snapshot());
    const subtitleToggle = doc.querySelector("#subtitle-toggle");
    subtitleToggle.click();
    check(doc.querySelector("#subtitle").hidden
      && subtitleToggle.getAttribute("aria-pressed") === "false",
      "subtitle toggle exposes and applies its off state");
    check(JSON.stringify(api.snapshot()) === beforeSubtitle,
      "subtitle toggle does not mutate engine state");
    subtitleToggle.click();
    check(!doc.querySelector("#subtitle").hidden
      && JSON.stringify(api.snapshot()) === beforeSubtitle,
      "subtitle toggle restores subtitles without mutating engine state");

    check(doc.documentElement.scrollWidth <= doc.documentElement.clientWidth,
      "390px mobile viewport has no horizontal overflow");
    const inspector = doc.querySelector("#formula-inspector");
    const inspectorStyle = win.getComputedStyle(inspector);
    check(inspector.scrollHeight <= inspector.clientHeight || ["auto", "scroll"].includes(inspectorStyle.overflowY),
      "formula inspector grows or scrolls instead of truncating content");

    doc.querySelector("#animation-speed").value = "100";
    await api.performAnimatedStep(() => 0);
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "idle", win, "animated core flow to settle");
    check(win.__task6Errors.length === 0,
      `core flow has no console or page errors: ${win.__task6Errors.join(" | ")}`);

    doc.querySelector("[data-close-game]").click();
    check(doc.querySelector("#game-screen").hidden
      && !doc.querySelector("#landing-screen").hidden,
      "back to game library restores the landing screen");
    check(doc.activeElement === doc.querySelector("[data-open-game]"),
      "back to game library returns focus to Play quest");

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
        if self.path == "/__accessibility_test__":
            self.send_html(HARNESS.encode())
            return
        if self.path == "/index.html":
            source = (ROOT / "index.html").read_text(encoding="utf-8")
            source = source.replace(
                '<script src="https://cdn.tailwindcss.com"></script>',
                "<!-- Tailwind CDN omitted by browser test server -->",
            )
            source = source.replace("<head>", f"<head>{ERROR_CAPTURE}", 1)
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
    with tempfile.TemporaryDirectory(prefix="play-science-accessibility-") as profile:
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--force-prefers-reduced-motion=reduce",
            "--window-size=390,1000",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=15000",
            "--dump-dom",
            f"http://127.0.0.1:{server.server_port}/__accessibility_test__",
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
    excerpt = output[marker : marker + 2400] if marker >= 0 else output[-2400:]
    raise RuntimeError(
        "Browser accessibility test failed.\n"
        f"Chrome exit code: {browser_exit_code}\n"
        f"DOM excerpt: {html.unescape(excerpt)}\n"
        f"Chrome stderr: {browser_errors[-1200:]}"
    )

start = output.find("PASS:")
end = output.find("</pre>", start)
print(html.unescape(output[start:end]))
