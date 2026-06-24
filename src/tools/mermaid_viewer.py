"""
Aegis Mermaid Viewer — Two-pane GTK+WebKit2 viewer.

Left pane: mermaid source code (editable text view)
Right pane: rendered diagram (WebKit2 with mermaid.js)

Usage:
    from tools.mermaid_viewer import MermaidViewer
    MermaidViewer("/path/to/diagram.mermaid").show()
"""

import os
import threading

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, WebKit2, GLib, Pango

# ANSI for terminal output before GTK window opens
CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"

# Mermaid.js loaded from CDN; renders locally in WebKit
_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0; padding: 16px;
    background: #1e1e2e; color: #cdd6f4;
    font-family: monospace;
    display: flex; justify-content: center; align-items: flex-start;
    min-height: 100vh;
  }}
  #diagram {{
    width: 100%;
    overflow: auto;
  }}
  .mermaid svg {{
    max-width: 100%;
  }}
  .error {{
    color: #f38ba8; padding: 1em;
    font-family: monospace; white-space: pre-wrap;
  }}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
</head>
<body>
<div id="diagram">
  <pre class="mermaid">
{mermaid_source}
  </pre>
</div>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'dark',
    securityLevel: 'loose',
    flowchart: {{ useMaxWidth: true, htmlLabels: true }},
    fontFamily: 'monospace'
  }});
</script>
</body>
</html>"""

# Offline fallback when CDN is unreachable
_HTML_OFFLINE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{
    margin: 0; padding: 24px;
    background: #1e1e2e; color: #cdd6f4;
    font-family: monospace;
  }}
  pre {{ white-space: pre-wrap; line-height: 1.6; }}
  .label {{ color: #89b4fa; font-weight: bold; }}
</style>
</head>
<body>
<p class="label">Mermaid source (offline — no CDN):</p>
<pre>{mermaid_source}</pre>
</body>
</html>"""


class MermaidViewer:
    """GTK+WebKit2 two-pane mermaid viewer."""

    def __init__(self, filepath: str):
        self.filepath = os.path.abspath(filepath)
        if not os.path.isfile(self.filepath):
            raise FileNotFoundError(f"Not found: {self.filepath}")
        self.source = open(self.filepath, "r").read()

    def _build_html(self, source: str) -> str:
        """Build HTML with mermaid source embedded."""
        # Escape HTML entities in mermaid source
        safe = (source
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
        return _HTML_TEMPLATE.format(mermaid_source=safe)

    def show(self):
        """Open the two-pane GTK window. Blocks until closed."""
        win = Gtk.Window(title=f"Aegis Mermaid — {os.path.basename(self.filepath)}")
        win.set_default_size(1400, 800)
        win.connect("destroy", Gtk.main_quit)

        # ── Left pane: source editor ──────────────────────────────
        source_buf = Gtk.TextBuffer()
        source_buf.set_text(self.source)

        source_view = Gtk.TextView(buffer=source_buf)
        source_view.set_monospace(True)
        source_view.modify_font(Pango.FontDescription("monospace 11"))
        source_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        source_view.set_left_margin(8)
        source_view.set_right_margin(8)
        source_view.set_top_margin(8)

        # Dark theme for source editor
        from gi.repository import Gdk
        bg = Gdk.RGBA()
        bg.parse("#1e1e2e")
        fg = Gdk.RGBA()
        fg.parse("#cdd6f4")
        source_view.override_background_color(Gtk.StateFlags.NORMAL, bg)
        source_view.override_color(Gtk.StateFlags.NORMAL, fg)

        source_scroll = Gtk.ScrolledWindow()
        source_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        source_scroll.add(source_view)

        # Source label
        source_label = Gtk.Label(label="  SOURCE  ")
        source_label.set_markup(
            '<span foreground="#89b4fa" font_weight="bold">  SOURCE  </span>'
        )

        source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        source_box.pack_start(source_label, False, False, 4)
        source_box.pack_start(source_scroll, True, True, 0)

        # ── Refresh button ────────────────────────────────────────
        btn_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        refresh_btn = Gtk.Button(label="Render  ▶")
        refresh_btn.set_tooltip_text("Re-render the diagram from source (Ctrl+R)")
        btn_bar.pack_start(refresh_btn, True, True, 4)
        source_box.pack_start(btn_bar, False, False, 4)

        # ── Right pane: WebKit2 rendered diagram ──────────────────
        webview = WebKit2.WebView()
        settings = webview.get_settings()
        settings.set_property("enable-javascript", True)
        settings.set_property("enable-developer-extras", False)
        webview.set_settings(settings)

        # Initial render
        html = self._build_html(self.source)
        webview.load_html(html, "file:///")

        render_label = Gtk.Label()
        render_label.set_markup(
            '<span foreground="#a6e3a1" font_weight="bold">  DIAGRAM  </span>'
        )

        render_scroll = Gtk.ScrolledWindow()
        render_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        render_scroll.add(webview)

        render_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        render_box.pack_start(render_label, False, False, 4)
        render_box.pack_start(render_scroll, True, True, 0)

        # ── Refresh callback ──────────────────────────────────────
        def on_refresh(_btn=None):
            start, end = source_buf.get_bounds()
            new_src = source_buf.get_text(start, end, True)
            webview.load_html(self._build_html(new_src), "file:///")

        refresh_btn.connect("clicked", on_refresh)

        # Ctrl+R keyboard shortcut
        accel = Gtk.AccelGroup()
        key, mod = Gtk.accelerator_parse("<Control>r")
        accel.connect(key, mod, 0, lambda *_: on_refresh())
        win.add_accel_group(accel)

        # ── Assemble panes ────────────────────────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack1(source_box, resize=True, shrink=False)
        paned.pack2(render_box, resize=True, shrink=False)
        paned.set_position(500)

        win.add(paned)
        win.show_all()
        Gtk.main()


def launch_viewer(filepath: str):
    """Launch the mermaid viewer in a background thread so the REPL isn't blocked."""
    def _run():
        try:
            viewer = MermaidViewer(filepath)
            viewer.show()
        except FileNotFoundError as e:
            print(f"\n{RD}[TRIT_NEG]{RS} {e}\n")
        except Exception as e:
            print(f"\n{RD}[TRIT_NEG]{RS} Mermaid viewer error: {e}\n")

    # GTK must run on its own; use subprocess to avoid GLib main loop conflicts
    import subprocess, sys
    script = os.path.abspath(__file__)
    subprocess.Popen(
        [sys.executable, script, filepath],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <file.mermaid>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"{RD}[TRIT_NEG]{RS} File not found: {path}")
        sys.exit(1)
    viewer = MermaidViewer(path)
    viewer.show()
