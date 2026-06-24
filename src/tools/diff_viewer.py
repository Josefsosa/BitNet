"""
Aegis Diff Viewer — Two-pane GTK+WebKit2 visual diff viewer.

Left pane:  HEAD version of the file (syntax-highlighted)
Right pane: Working tree version (with diff hunks marked)

Follows the mermaid_viewer.py pattern: GTK window launched as subprocess.

Usage:
    from tools.diff_viewer import launch_viewer
    launch_viewer(filepath, old_content, new_content, unified_diff)
"""

import os
import sys
import html
import hashlib
import tempfile
import re

# ANSI for terminal output before GTK window opens
CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"

# ── HTML template for a single diff pane ──────────────────────────────────

_PANE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #1e1e2e;
    color: #cdd6f4;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.5;
  }}
  .header {{
    padding: 8px 16px;
    background: #181825;
    border-bottom: 1px solid #313244;
    font-weight: bold;
    color: {header_color};
    font-size: 14px;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  .stats {{
    float: right;
    font-size: 12px;
    color: #6c7086;
    font-weight: normal;
  }}
  .stats .add {{ color: #a6e3a1; }}
  .stats .del {{ color: #f38ba8; }}
  table {{
    width: 100%;
    border-collapse: collapse;
  }}
  tr {{
    height: 21px;
  }}
  td {{
    padding: 0 8px;
    white-space: pre;
    vertical-align: top;
  }}
  .ln {{
    width: 50px;
    min-width: 50px;
    text-align: right;
    color: #585b70;
    user-select: none;
    padding-right: 12px;
    border-right: 1px solid #313244;
  }}
  .code {{
    padding-left: 12px;
  }}
  .line-add {{
    background: rgba(166, 227, 161, 0.12);
  }}
  .line-add .ln {{
    color: #a6e3a1;
  }}
  .line-del {{
    background: rgba(243, 139, 168, 0.12);
  }}
  .line-del .ln {{
    color: #f38ba8;
  }}
  .line-change {{
    background: rgba(249, 226, 175, 0.10);
  }}
  .line-change .ln {{
    color: #f9e2af;
  }}
  .hunk-sep {{
    background: #181825;
    color: #585b70;
    font-style: italic;
    padding: 4px 8px;
  }}
  .hunk-sep td {{
    padding: 4px 8px;
  }}
</style>
</head>
<body>
<div class="header">
  {label}
  <span class="stats">{stats}</span>
</div>
<table id="code-table">
{rows}
</table>
<script>
  // Synchronized scrolling via postMessage
  window.addEventListener('scroll', function() {{
    var pct = window.scrollY / (document.body.scrollHeight - window.innerHeight || 1);
    window.webkit.messageHandlers.syncScroll &&
      window.webkit.messageHandlers.syncScroll.postMessage(String(pct));
  }});
</script>
</body>
</html>"""


class DiffViewer:
    """GTK+WebKit2 two-pane visual diff viewer."""

    def __init__(self, filepath: str, old_content: str, new_content: str,
                 unified_diff: str):
        self.filepath = filepath
        self.old_content = old_content
        self.new_content = new_content
        self.unified_diff = unified_diff

    def _parse_hunks(self):
        """Parse unified diff to extract line-level change maps for left and right panes.
        Returns (old_highlights, new_highlights) dicts mapping line_num -> type.
        """
        old_hl = {}  # line_num -> 'del' | 'change'
        new_hl = {}  # line_num -> 'add' | 'change'

        old_line = 0
        new_line = 0

        for line in self.unified_diff.splitlines():
            # Hunk header: @@ -old_start[,old_count] +new_start[,new_count] @@
            hunk_match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if hunk_match:
                old_line = int(hunk_match.group(1))
                new_line = int(hunk_match.group(2))
                continue

            if line.startswith('diff ') or line.startswith('index ') or \
               line.startswith('---') or line.startswith('+++'):
                continue

            if line.startswith('-'):
                old_hl[old_line] = 'del'
                old_line += 1
            elif line.startswith('+'):
                new_hl[new_line] = 'add'
                new_line += 1
            elif line.startswith(' ') or line == '':
                old_line += 1
                new_line += 1

        return old_hl, new_hl

    def _build_html_pane(self, content: str, highlights: dict, label: str,
                         header_color: str) -> str:
        """Build HTML for one pane with line-level highlighting."""
        lines = content.splitlines() if content else []
        add_count = sum(1 for v in highlights.values() if v == 'add')
        del_count = sum(1 for v in highlights.values() if v == 'del')
        stats_parts = []
        if add_count:
            stats_parts.append(f'<span class="add">+{add_count}</span>')
        if del_count:
            stats_parts.append(f'<span class="del">-{del_count}</span>')
        stats = " / ".join(stats_parts) if stats_parts else ""

        rows = []
        for i, line_text in enumerate(lines, 1):
            css_class = ""
            hl_type = highlights.get(i)
            if hl_type == 'add':
                css_class = ' class="line-add"'
            elif hl_type == 'del':
                css_class = ' class="line-del"'
            elif hl_type == 'change':
                css_class = ' class="line-change"'

            escaped = html.escape(line_text)
            rows.append(
                f'<tr{css_class}>'
                f'<td class="ln">{i}</td>'
                f'<td class="code">{escaped}</td>'
                f'</tr>'
            )

        # Pad shorter pane so both have equal rows for scroll sync
        if not rows:
            rows.append(
                '<tr><td class="ln">~</td>'
                '<td class="code" style="color:#585b70;">(empty / new file)</td></tr>'
            )

        return _PANE_HTML.format(
            header_color=header_color,
            label=html.escape(label),
            stats=stats,
            rows="\n".join(rows),
        )

    def _count_changes(self):
        """Count additions and deletions from the unified diff."""
        additions = 0
        deletions = 0
        for line in self.unified_diff.splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        return additions, deletions

    def show(self):
        """Open GTK window with two WebKit2 panes."""
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.0")
        from gi.repository import Gtk, WebKit2, Gdk

        old_hl, new_hl = self._parse_hunks()
        additions, deletions = self._count_changes()

        basename = os.path.basename(self.filepath)

        left_html = self._build_html_pane(
            self.old_content, old_hl,
            f"HEAD (before) — {basename}",
            "#89b4fa",
        )
        right_html = self._build_html_pane(
            self.new_content, new_hl,
            f"Working Tree (after) — {basename}",
            "#a6e3a1",
        )

        # ── GTK Window ────────────────────────────────────────────────
        win = Gtk.Window(title=f"Aegis Diff — {basename}")
        win.set_default_size(1500, 850)
        win.connect("destroy", Gtk.main_quit)

        # Dark title bar
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        # ── Stats bar ─────────────────────────────────────────────────
        stats_bar = Gtk.Label()
        stats_bar.set_markup(
            f'<span font_family="monospace" font_size="10000">'
            f'  <span foreground="#cdd6f4">{html.escape(self.filepath)}</span>'
            f'  <span foreground="#585b70">│</span>'
            f'  <span foreground="#a6e3a1">+{additions}</span>'
            f'  <span foreground="#f38ba8">-{deletions}</span>'
            f'  <span foreground="#585b70">lines</span>'
            f'</span>'
        )
        stats_bar.set_xalign(0)
        stats_bar.set_margin_start(8)
        stats_bar.set_margin_top(4)
        stats_bar.set_margin_bottom(4)

        # Style the stats bar background
        stats_css = Gtk.CssProvider()
        stats_css.load_from_data(b"""
            .stats-bar {
                background-color: #11111b;
                padding: 4px 8px;
            }
        """)
        stats_bar.get_style_context().add_class("stats-bar")
        stats_bar.get_style_context().add_provider(
            stats_css, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        # ── Left pane (HEAD) ──────────────────────────────────────────
        left_web = WebKit2.WebView()
        left_settings = left_web.get_settings()
        left_settings.set_property("enable-javascript", True)
        left_web.set_settings(left_settings)
        left_web.load_html(left_html, "file:///")

        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        left_scroll.add(left_web)

        # ── Right pane (Working Tree) ─────────────────────────────────
        right_web = WebKit2.WebView()
        right_settings = right_web.get_settings()
        right_settings.set_property("enable-javascript", True)
        right_web.set_settings(right_settings)
        right_web.load_html(right_html, "file:///")

        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        right_scroll.add(right_web)

        # ── Synchronized scrolling ────────────────────────────────────
        _syncing = [False]

        def sync_left_to_right(adj):
            if _syncing[0]:
                return
            _syncing[0] = True
            r_adj = right_scroll.get_vadjustment()
            l_adj = left_scroll.get_vadjustment()
            if l_adj.get_upper() > l_adj.get_page_size():
                pct = l_adj.get_value() / (l_adj.get_upper() - l_adj.get_page_size())
                target = pct * (r_adj.get_upper() - r_adj.get_page_size())
                r_adj.set_value(target)
            _syncing[0] = False

        def sync_right_to_left(adj):
            if _syncing[0]:
                return
            _syncing[0] = True
            l_adj = left_scroll.get_vadjustment()
            r_adj = right_scroll.get_vadjustment()
            if r_adj.get_upper() > r_adj.get_page_size():
                pct = r_adj.get_value() / (r_adj.get_upper() - r_adj.get_page_size())
                target = pct * (l_adj.get_upper() - l_adj.get_page_size())
                l_adj.set_value(target)
            _syncing[0] = False

        left_scroll.get_vadjustment().connect("value-changed", sync_left_to_right)
        right_scroll.get_vadjustment().connect("value-changed", sync_right_to_left)

        # ── Assemble panes ────────────────────────────────────────────
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack1(left_scroll, resize=True, shrink=False)
        paned.pack2(right_scroll, resize=True, shrink=False)
        paned.set_position(750)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(stats_bar, False, False, 0)
        vbox.pack_start(paned, True, True, 0)

        # ── Keyboard shortcuts ────────────────────────────────────────
        accel = Gtk.AccelGroup()

        # Ctrl+R = refresh from disk
        def on_refresh(*_args):
            nonlocal old_hl, new_hl
            try:
                new_content = open(self.filepath, "r").read()
            except Exception:
                return
            self.new_content = new_content
            old_hl, new_hl = self._parse_hunks()
            new_html = self._build_html_pane(
                self.new_content, new_hl,
                f"Working Tree (after) — {basename}",
                "#a6e3a1",
            )
            right_web.load_html(new_html, "file:///")

        key, mod = Gtk.accelerator_parse("<Control>r")
        accel.connect(key, mod, 0, on_refresh)

        # Ctrl+Q / Ctrl+W = close
        def on_close(*_args):
            win.close()

        key, mod = Gtk.accelerator_parse("<Control>q")
        accel.connect(key, mod, 0, on_close)
        key, mod = Gtk.accelerator_parse("<Control>w")
        accel.connect(key, mod, 0, on_close)

        win.add_accel_group(accel)
        win.add(vbox)
        win.show_all()
        Gtk.main()


def launch_viewer(filepath: str, old_content: str, new_content: str,
                  unified_diff: str):
    """Launch diff viewer as subprocess (same pattern as mermaid_viewer.py).
    Passes data via temp files to avoid argument length limits.
    """
    import subprocess as sp

    # Write data to temp files
    uid = hashlib.md5(filepath.encode()).hexdigest()[:8]
    tmp_dir = tempfile.gettempdir()
    old_path = os.path.join(tmp_dir, f"aegis_diff_old_{uid}")
    new_path = os.path.join(tmp_dir, f"aegis_diff_new_{uid}")
    patch_path = os.path.join(tmp_dir, f"aegis_diff_patch_{uid}")

    with open(old_path, "w") as f:
        f.write(old_content)
    with open(new_path, "w") as f:
        f.write(new_content)
    with open(patch_path, "w") as f:
        f.write(unified_diff)

    # Launch subprocess
    script = os.path.abspath(__file__)
    sp.Popen(
        [sys.executable, script, filepath, old_path, new_path, patch_path],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(f"Usage: python3 {sys.argv[0]} <filepath> <old_tmp> <new_tmp> <patch_tmp>")
        sys.exit(1)

    filepath = sys.argv[1]
    old_path = sys.argv[2]
    new_path = sys.argv[3]
    patch_path = sys.argv[4]

    try:
        old_content = open(old_path, "r").read()
        new_content = open(new_path, "r").read()
        unified_diff = open(patch_path, "r").read()
    except FileNotFoundError as e:
        print(f"{RD}[TRIT_NEG]{RS} Temp file not found: {e}")
        sys.exit(1)
    finally:
        # Clean up temp files
        for p in (old_path, new_path, patch_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    viewer = DiffViewer(filepath, old_content, new_content, unified_diff)
    viewer.show()
