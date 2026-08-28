#!/usr/bin/env python3
"""Download selected PhysioNet datasets with credentials from .env."""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import HTTPBasicAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DATASETS = {
    "cds": {
        "name": "MIMIC-IV-Ext clinical decision support",
        "slug": "mimic-iv-ext-cds",
        "version": "1.0.2",
        "url": "https://physionet.org/files/mimic-iv-ext-cds/1.0.2/",
        "access": "credentialed",
        "size": "small (CSV extracts)",
        "recommended": True,
        "why": "Primary source: HPI, vitals, chief complaint, ICD diagnoses, triage acuity.",
        "dua": "https://physionet.org/sign-dua/mimic-iv-ext-cds/1.0.2/",
    },
    "direct": {
        "name": "MIMIC-IV-Ext-DiReCT",
        "slug": "mimic-iv-ext-direct",
        "version": "1.0.0",
        "url": "https://physionet.org/files/mimic-iv-ext-direct/1.0.0/",
        "access": "restricted",
        "size": "small (511 annotated notes)",
        "recommended": True,
        "why": "Diagnostic-reasoning format check. Not the 1000-case evaluation set.",
        "dua": "https://physionet.org/sign-dua/mimic-iv-ext-direct/1.0.0/",
    },
    "ed": {
        "name": "MIMIC-IV-ED",
        "slug": "mimic-iv-ed",
        "version": "2.2",
        "url": "https://physionet.org/files/mimic-iv-ed/2.2/",
        "access": "credentialed",
        "size": "medium (~1-2 GB)",
        "recommended": False,
        "why": "Raw ED stays. Only needed if CDS is missing fields we want.",
        "dua": "https://physionet.org/sign-dua/mimic-iv-ed/2.2/",
    },
    "mimiciv": {
        "name": "MIMIC-IV",
        "slug": "mimiciv",
        "version": "3.1",
        "url": "https://physionet.org/files/mimiciv/3.1/",
        "access": "credentialed",
        "size": "large (tens of GB)",
        "recommended": False,
        "why": "Parent EHR dump. Skip unless CDS/ED are insufficient.",
        "dua": "https://physionet.org/sign-dua/mimiciv/3.1/",
    },
    "notes": {
        "name": "MIMIC-IV-Note",
        "slug": "mimic-iv-note",
        "version": "2.2",
        "url": "https://physionet.org/files/mimic-iv-note/2.2/",
        "access": "credentialed",
        "size": "large (several GB of notes)",
        "recommended": False,
        "why": "Raw notes. CDS already extracted HPI. Do not send notes to public LLM APIs.",
        "dua": "https://physionet.org/sign-dua/mimic-iv-note/2.2/",
    },
}

HREF_RE = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
SKIP_NAMES = {"", ".", "..", "index.html", "index.htm"}
USER_AGENT = "Wget/1.21.4"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def make_opener(username: str, password: str):
    manager = HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, "https://physionet.org/", username, password)
    return build_opener(HTTPBasicAuthHandler(manager))


def request_for(url: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT})


def fetch(opener, url: str, timeout: int = 60) -> bytes:
    with opener.open(request_for(url), timeout=timeout) as response:
        return response.read()


def iter_links(html: str, base_url: str):
    for href in HREF_RE.findall(html):
        href = unquote(href).strip()
        if href.startswith("?") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        name = unquote(urlparse(full).path.rstrip("/").split("/")[-1])
        if name.lower() in SKIP_NAMES:
            continue
        yield full, href.endswith("/")


def is_under(url: str, root: str) -> bool:
    return url.startswith(root)


def download_file(opener, url: str, dest: Path, retries: int = 4) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with opener.open(request_for(url), timeout=120) as response:
                length = response.headers.get("Content-Length")
                expected = int(length) if length and length.isdigit() else None
                if dest.exists() and expected and dest.stat().st_size == expected:
                    print(f"  skip  {dest.relative_to(ROOT)}")
                    return
                with tmp.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        handle.write(chunk)
            tmp.replace(dest)
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  saved {dest.relative_to(ROOT)} ({size_mb:.2f} MB)")
            return
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if tmp.exists():
                tmp.unlink()
            if attempt == retries:
                raise
            wait = 2**attempt
            print(f"  retry {attempt}/{retries} after {wait}s: {exc}")
            time.sleep(wait)


def crawl(opener, root_url: str, out_dir: Path, dua: str) -> None:
    seen: set[str] = set()
    queue = [root_url]
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if url.endswith("/"):
            print(f"listing {url}")
            try:
                html = fetch(opener, url).decode("utf-8", errors="replace")
            except HTTPError as exc:
                if exc.code in {401, 403}:
                    raise PermissionError(
                        f"Access denied for {url} (HTTP {exc.code}). "
                        f"Sign the project DUA, then retry: {dua}"
                    ) from exc
                raise
            for child, is_dir in iter_links(html, url):
                if not is_under(child, root_url):
                    continue
                if is_dir:
                    queue.append(child if child.endswith("/") else child + "/")
                else:
                    rel = unquote(urlparse(child).path)
                    prefix = urlparse(root_url).path
                    rel_path = rel[len(prefix) :].lstrip("/")
                    download_file(opener, child, out_dir / rel_path)
        else:
            rel = unquote(urlparse(url).path)
            prefix = urlparse(root_url).path
            rel_path = rel[len(prefix) :].lstrip("/")
            download_file(opener, url, out_dir / rel_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets",
        default="cds,direct",
        help="Comma-separated keys: cds,direct,ed,mimiciv,notes or 'all' / 'recommended'",
    )
    parser.add_argument("--list", action="store_true", help="Print dataset catalog and exit")
    return parser.parse_args()


def selected_keys(spec: str) -> list[str]:
    spec = spec.strip().lower()
    if spec == "all":
        return list(DATASETS)
    if spec == "recommended":
        return [key for key, meta in DATASETS.items() if meta["recommended"]]
    keys = [part.strip() for part in spec.split(",") if part.strip()]
    unknown = [key for key in keys if key not in DATASETS]
    if unknown:
        raise SystemExit(f"Unknown dataset key(s): {', '.join(unknown)}")
    return keys


def main() -> int:
    args = parse_args()
    if args.list:
        for key, meta in DATASETS.items():
            flag = "YES" if meta["recommended"] else "later"
            print(
                f"{key:8}  download={flag:5}  {meta['name']}  "
                f"[{meta['access']}, {meta['size']}]"
            )
            print(f"          {meta['why']}")
        return 0

    env = load_env(ENV_PATH)
    username = env.get("PHYSIONET_USERNAME", "").strip()
    password = env.get("PHYSIONET_PASSWORD", "").strip()
    if not username or not password:
        raise SystemExit(
            f"Fill PHYSIONET_USERNAME and PHYSIONET_PASSWORD in {ENV_PATH}"
        )

    data_dir = Path(env.get("PHYSIONET_DATA_DIR") or ROOT / "data" / "physionet")
    opener = make_opener(username, password)
    keys = selected_keys(args.datasets)

    print("Download plan:")
    for key in keys:
        meta = DATASETS[key]
        print(f"  - {key}: {meta['name']} ({meta['size']})")

    failures: list[str] = []
    for key in keys:
        meta = DATASETS[key]
        dest = data_dir / f"{meta['slug']}-{meta['version']}"
        print(f"\n=== {meta['name']} ===")
        try:
            crawl(opener, meta["url"], dest, meta["dua"])
        except PermissionError as exc:
            print(exc)
            failures.append(key)

    if failures:
        print("\nFinished with access failures:", ", ".join(failures))
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
