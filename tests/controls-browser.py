#!/usr/bin/env python3
"""Exercise paced continuation and training controls in a real browser."""

from __future__ import annotations

import html
import base64
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

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
window.__trustedTabReady = false;
window.__trustedTabSent = false;
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
    doc.querySelector("#step-button").focus();
    check(doc.activeElement === doc.querySelector("#step-button"),
      "Step starts the paced transition with keyboard focus");
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
    check(doc.activeElement === doc.querySelector("#continue-button"),
      "waiting moves focus from the hidden Step button to Continue");

    window.parent.__trustedTabReady = true;
    await waitUntil(() => window.parent.__trustedTabSent, win, "trusted CDP Tab input");
    check(api.visualSnapshot().inspectorPhase === "waiting",
      "trusted Tab input does not continue training");
    check(doc.activeElement === doc.querySelector("#reset-button"),
      "trusted Tab input moves focus from Continue to Reset");
    check(waitingStatus.textContent.includes("character key")
      && !waitingStatus.textContent.includes("non-modifier"),
      "waiting copy accurately limits keyboard continuation to character keys");

    const nonContentKeys = [
      "Shift", "Control", "Alt", "Meta", "CapsLock", "AltGraph", "Fn", "FnLock",
      "NumLock", "ScrollLock", "Symbol", "SymbolLock", "Hyper", "Super", "OS",
      "Tab", "Escape", "ArrowUp", "ArrowRight", "ArrowDown", "ArrowLeft",
      "Home", "End", "PageUp", "PageDown", "Insert", "ContextMenu", "PrintScreen",
      "Enter", "Backspace", "Delete", "F1", "F12",
    ];
    for (const key of nonContentKeys) {
      doc.dispatchEvent(new win.KeyboardEvent("keydown", { key, bubbles: true }));
      await pause(win, 10);
      check(api.visualSnapshot().inspectorPhase === "waiting",
        `${key} does not continue training`);
    }
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
      "a character document key resolves the paced wait");
    check(doc.activeElement === doc.querySelector("#step-button"),
      "character continuation returns focus to the visible Step control");

    const continued = api.runAnimatedStep();
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "waiting", win, "button waiting state");
    doc.querySelector("#continue-button").click();
    check(!(await continued).canceled, "the animated transition completes before continuation");
    await waitUntil(() => api.visualSnapshot().inspectorPhase === "idle", win, "button continuation");
    check(api.visualSnapshot().inspectorPhase === "idle",
      "the separate Continue button resolves the paced wait");
    check(doc.activeElement === doc.querySelector("#step-button"),
      "Continue returns focus to the visible Step control");

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


def reserve_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class DevToolsClient:
    """Small dependency-free WebSocket client for trusted CDP input."""

    def __init__(self, websocket_url: str) -> None:
        parsed = urlparse(websocket_url)
        self.connection = socket.create_connection((parsed.hostname, parsed.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = (
            f"GET {target} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.connection.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.connection.recv(4096)
            if not chunk:
                raise RuntimeError("CDP WebSocket closed during handshake")
            response += chunk
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError(f"CDP WebSocket handshake failed: {response[:200]!r}")
        self.next_id = 1

    def close(self) -> None:
        self.connection.close()

    def _read_exactly(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self.connection.recv(length - len(chunks))
            if not chunk:
                raise RuntimeError("CDP WebSocket closed unexpectedly")
            chunks.extend(chunk)
        return bytes(chunks)

    def _receive(self) -> dict[str, Any]:
        first, second = self._read_exactly(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exactly(8))[0]
        payload = self._read_exactly(length)
        if opcode == 9:
            self._send(payload, opcode=10)
            return self._receive()
        if opcode != 1:
            raise RuntimeError(f"Unexpected CDP WebSocket opcode: {opcode}")
        return json.loads(payload.decode())

    def _send(self, payload: bytes, opcode: int = 1) -> None:
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.connection.sendall(bytes(header) + mask + masked)

    def call(self, method: str, **params: object) -> dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self._send(json.dumps({"id": message_id, "method": method, "params": params}).encode())
        while True:
            response = self._receive()
            if response.get("id") != message_id:
                continue
            if "error" in response:
                raise RuntimeError(f"CDP {method} failed: {response['error']}")
            return response["result"]

    def evaluate(self, expression: str) -> object:
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        return result["result"].get("value")


def connect_to_test_page(port: int, timeout: float = 12) -> DevToolsClient:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                targets = json.load(response)
            target = next(item for item in targets if "__controls_test__" in item.get("url", ""))
            return DevToolsClient(target["webSocketDebuggerUrl"])
        except (OSError, RuntimeError, StopIteration) as error:
            last_error = error
            time.sleep(0.05)
    raise RuntimeError(f"Could not connect to controls page over CDP: {last_error}")


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

output = ""
browser_errors = ""
browser_exit_code = -1
try:
    with tempfile.TemporaryDirectory(prefix="play-science-controls-") as profile:
        debugging_port = reserve_port()
        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--force-prefers-reduced-motion=reduce",
            "--window-size=900,1000",
            f"--user-data-dir={profile}",
            f"--remote-debugging-port={debugging_port}",
            f"http://127.0.0.1:{server.server_port}/__controls_test__",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            client = connect_to_test_page(debugging_port)
            deadline = time.monotonic() + 42
            while time.monotonic() < deadline and not client.evaluate("window.__trustedTabReady === true"):
                time.sleep(0.02)
            if not client.evaluate("window.__trustedTabReady === true"):
                raise RuntimeError("Timed out waiting for the trusted Tab checkpoint")
            tab = {
                "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9,
                "nativeVirtualKeyCode": 9,
            }
            client.call("Input.dispatchKeyEvent", type="rawKeyDown", **tab)
            client.call("Input.dispatchKeyEvent", type="keyUp", **tab)
            client.evaluate("window.__trustedTabSent = true")
            while time.monotonic() < deadline:
                status = client.evaluate("document.querySelector('#result').dataset.status || ''")
                if status in ("pass", "fail"):
                    break
                time.sleep(0.02)
            output = str(client.evaluate("document.querySelector('#result').outerHTML"))
            client.close()
        finally:
            process.terminate()
            try:
                _, browser_errors = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, browser_errors = process.communicate()
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
