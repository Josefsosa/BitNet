"""
Aegis Image Hunt — AI-driven free image finder for game textures.

Parses filenames into search queries, hits free image APIs
(Unsplash, Pexels, Pixabay), downloads best match, saves with
the correct name.  Supports single-shot and batch (manifest) modes.

Usage from CLI:
  image-hunt rusty_metal_plate.png
  image-hunt --manifest textures.json --to assets/
  image-hunt --setup
  image-hunt --status
"""

import os
import re
import json
import time

WORKSPACE_ROOT = os.path.expanduser("~/workspace/aegis-ternary")
KEYS_FILE = os.path.expanduser("~/.aegis/image_hunt_keys.json")

# ANSI colors (match aegis-cli palette)
CY = "\033[1;36m"; GR = "\033[1;32m"; YL = "\033[1;33m"
RD = "\033[1;31m"; DM = "\033[0;36m"; RS = "\033[0m"


class ImageHunt:
    """
    Searches free image APIs by filename-derived keywords,
    downloads best match, saves to target directory.
    """

    SOURCES = {
        "unsplash": "https://api.unsplash.com/search/photos",
        "pexels":   "https://api.pexels.com/v1/search",
        "pixabay":  "https://pixabay.com/api/",
    }

    SIGNUP_URLS = {
        "unsplash": "https://unsplash.com/developers",
        "pexels":   "https://www.pexels.com/api/",
        "pixabay":  "https://pixabay.com/api/docs/",
    }

    def __init__(self, output_dir=None, keys=None):
        self.output_dir = output_dir or os.path.join(WORKSPACE_ROOT, "skunk-works/assets")
        self.keys = keys or self._load_keys()
        self.results_log = []  # [{name, source, url, path, status}]

    # ── Key management ────────────────────────────────────────────────────

    def _load_keys(self):
        """Load API keys from env vars, falling back to ~/.aegis/image_hunt_keys.json."""
        keys = {
            "unsplash": os.environ.get("UNSPLASH_ACCESS_KEY", ""),
            "pexels":   os.environ.get("PEXELS_API_KEY", ""),
            "pixabay":  os.environ.get("PIXABAY_API_KEY", ""),
        }
        # Try JSON file if env vars are empty
        if not any(keys.values()):
            try:
                if os.path.exists(KEYS_FILE):
                    with open(KEYS_FILE) as f:
                        file_keys = json.load(f)
                    for src in ("unsplash", "pexels", "pixabay"):
                        if file_keys.get(src):
                            keys[src] = file_keys[src]
            except (json.JSONDecodeError, IOError):
                pass
        return keys

    def _has_any_key(self):
        return any(v for v in self.keys.values())

    # ── Query parsing ─────────────────────────────────────────────────────

    def _filename_to_query(self, filename):
        """'rusty_metal_plate.png' -> 'rusty metal plate'"""
        name = os.path.splitext(filename)[0]
        # Replace underscores and hyphens with spaces
        query = re.sub(r'[_\-]', ' ', name)
        # Split camelCase: 'darkWoodFloor' -> 'dark Wood Floor'
        query = re.sub(r'([a-z])([A-Z])', r'\1 \2', query)
        return query.strip().lower()

    # ── API search methods ────────────────────────────────────────────────

    def _search(self, source, query):
        """Query a specific API, return download URL of best match or None."""
        import requests

        key = self.keys.get(source, "")
        if not key:
            return None

        try:
            if source == "unsplash":
                resp = requests.get(
                    self.SOURCES["unsplash"],
                    params={"query": query, "per_page": 1},
                    headers={"Authorization": f"Client-ID {key}"},
                    timeout=15,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if results:
                    return results[0]["urls"].get("regular") or results[0]["urls"].get("full")

            elif source == "pexels":
                resp = requests.get(
                    self.SOURCES["pexels"],
                    params={"query": query, "per_page": 1},
                    headers={"Authorization": key},
                    timeout=15,
                )
                resp.raise_for_status()
                photos = resp.json().get("photos", [])
                if photos:
                    return photos[0]["src"].get("large") or photos[0]["src"].get("original")

            elif source == "pixabay":
                resp = requests.get(
                    self.SOURCES["pixabay"],
                    params={"key": key, "q": query, "per_page": 3, "image_type": "photo"},
                    timeout=15,
                )
                resp.raise_for_status()
                hits = resp.json().get("hits", [])
                if hits:
                    return hits[0].get("largeImageURL")

        except Exception as e:
            print(f"  {DM}[{source}] Search error: {e}{RS}")
        return None

    # ── Download ──────────────────────────────────────────────────────────

    def _download(self, url, out_path):
        """Download image bytes to disk. Returns True on success."""
        import requests

        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"  {RD}[Download] Failed: {e}{RS}")
            return False

    # ── Single hunt ───────────────────────────────────────────────────────

    def hunt_single(self, filename, output_dir=None, source_pref=None, keywords=None):
        """Search + download one image by filename."""
        query = keywords if keywords else self._filename_to_query(filename)
        target_dir = output_dir or self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        out_path = os.path.join(target_dir, filename)

        print(f"\n  {CY}[hunt]{RS} Searching: \"{query}\" -> {filename}")

        # Try each source in priority order
        sources = [source_pref] if source_pref else ["unsplash", "pexels", "pixabay"]
        for src in sources:
            if not self.keys.get(src):
                continue
            print(f"  {DM}  trying {src}...{RS}", end="", flush=True)
            url = self._search(src, query)
            if url:
                ok = self._download(url, out_path)
                if ok:
                    size = os.path.getsize(out_path)
                    result = {
                        "ok": True, "path": out_path, "source": src,
                        "query": query, "url": url, "filename": filename,
                        "size": size,
                    }
                    self.results_log.append(result)
                    print(f" {GR}found!{RS}")
                    print(f"  {GR}  saved:{RS} {out_path} ({size:,} bytes from {src})")
                    return result
            print(f" {YL}no match{RS}")

        result = {"ok": False, "query": query, "filename": filename,
                  "err": "no_match_or_no_keys"}
        self.results_log.append(result)
        print(f"  {RD}  no results found for \"{query}\"{RS}")
        return result

    # ── Batch / manifest hunt ─────────────────────────────────────────────

    def hunt_manifest(self, manifest_path, output_dir=None):
        """
        Batch mode: process a JSON manifest of image names.

        Manifest format:
          ["rusty_metal.png", "brick_wall.png"]
        or:
          [{"file": "rusty_metal.png", "keywords": "optional override"}, ...]
        """
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"\n  {RD}[manifest]{RS} Failed to load {manifest_path}: {e}\n")
            return []

        print(f"\n  {CY}[manifest]{RS} Processing {len(manifest)} entries from {manifest_path}")
        results = []
        for i, entry in enumerate(manifest, 1):
            if isinstance(entry, str):
                filename = entry
                keywords = None
            else:
                filename = entry.get("file", "")
                keywords = entry.get("keywords")
            if not filename:
                continue
            print(f"\n  {DM}[{i}/{len(manifest)}]{RS}")
            result = self.hunt_single(filename, output_dir, keywords=keywords)
            results.append(result)
            # Rate-limit between requests
            if i < len(manifest):
                time.sleep(0.5)
        return results

    # ── Setup & status helpers ────────────────────────────────────────────

    def print_setup(self):
        """Print API key configuration guide."""
        print(f"""
{CY}IMAGE HUNT — API Key Setup{RS}

Image Hunt searches free stock photo APIs.  You need at least one API key.

{GR}Option A: Environment variables{RS}
  export UNSPLASH_ACCESS_KEY="your-key-here"
  export PEXELS_API_KEY="your-key-here"
  export PIXABAY_API_KEY="your-key-here"

{GR}Option B: Config file{RS}
  Create {KEYS_FILE} with:
  {{
    "unsplash": "your-access-key",
    "pexels":   "your-api-key",
    "pixabay":  "your-api-key"
  }}

{GR}Signup links (all free):{RS}
  Unsplash:  https://unsplash.com/developers        (50 req/hour)
  Pexels:    https://www.pexels.com/api/             (200 req/month)
  Pixabay:   https://pixabay.com/api/docs/           (100 req/minute)

{DM}Tip: Pixabay has the most generous free tier.{RS}
""")

    def print_status(self):
        """Show which API keys are configured."""
        print(f"\n  {CY}IMAGE HUNT — Key Status{RS}\n")
        for src in ("unsplash", "pexels", "pixabay"):
            key = self.keys.get(src, "")
            if key:
                masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "****"
                print(f"  {GR}[active]{RS}  {src:10s}  {masked}")
            else:
                print(f"  {RD}[none]{RS}    {src:10s}  — not configured")
        if not self._has_any_key():
            print(f"\n  {YL}Run 'image-hunt --setup' for configuration instructions.{RS}")
        print()

    def print_results(self):
        """Print summary of hunt session."""
        if not self.results_log:
            return
        ok = sum(1 for r in self.results_log if r.get("ok"))
        fail = len(self.results_log) - ok
        print(f"\n  {CY}[Hunt Summary]{RS}  {GR}{ok} downloaded{RS}  "
              f"{RD}{fail} failed{RS}  ({len(self.results_log)} total)\n")
        for r in self.results_log:
            if r.get("ok"):
                print(f"    {GR}OK{RS}  {r['filename']}  <- {r['source']}  "
                      f"({r.get('size', 0):,} bytes)")
            else:
                print(f"    {RD}--{RS}  {r['filename']}  ({r.get('err', 'unknown')})")
        print()
