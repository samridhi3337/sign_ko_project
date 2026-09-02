"""
Downloads real professional motion-capture ASL animation clips from the
Studio Galt Sign Language Mocap Archive
(https://github.com/StudioGalt/Sign-Language-Mocap-Archive, CC0-1.0)
for any of this project's known words the archive has a matching entry
for, and writes/updates `data/mocap_manifest.json` + `data/mocap/*.fbx`.

Why this exists (see sign_animation/README.md "Pass 6" for the full
writeup): this archive's animation is captured with dedicated
professional hardware (Xsens Link motion-capture suit + StretchSense
finger-tracking gloves), not estimated from 2D video the way this
project's own WLASL-derived word data is -- a real accuracy upgrade
for any word it covers. It ships Mixamo-standard-named FBX exports
that match this project's existing avatar rig (`avatar_feminine.fbx`)
bone-for-bone (52/53 bones matched exactly in the pass that verified
this), so no new avatar or retargeting scheme is needed -- only a new,
parallel *source* of real bone-rotation animation, played back via
Three.js's own AnimationMixer instead of this project's point-cloud
retargeting math (see static/js/sign_animation.js `playMocapWord`).

Honest caveat (also in README): the archive's creator states outright
they are a hearing, non-native ASL signer and that "mistakes can and
will happen" -- there is no formal Deaf-community audit process
described. This is real captured motion from a real (if imperfect,
by the creator's own account) signer, not fabricated -- not a claim
of zero errors.

The archive's own internal folder layout has changed several times
over its life (flat files -> "FBX Files/Game Ready/" ->
"FBX Files/Mixamo/" -> newest entries with no Mixamo export at all
yet), so this script tries each known layout in turn per word rather
than assuming one fixed structure.

Usage:
    python sign_animation/fetch_mocap_words.py
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

import config

ARCHIVE_BASE = (
    "https://raw.githubusercontent.com/StudioGalt/"
    "Sign-Language-Mocap-Archive/main/SG%20ASL%20Dictionary"
)
GITHUB_API_BASE = (
    "https://api.github.com/repos/StudioGalt/"
    "Sign-Language-Mocap-Archive/contents/SG%20ASL%20Dictionary"
)
MANIFEST_PATH = config.MOCAP_MANIFEST_PATH
MOCAP_DIR = config.MOCAP_DIR

# Known historical layouts, tried in order, cheapest (no extra network
# call) first. "{base}" is the entry folder name with " Upload"
# stripped, e.g. "SG ASL Cold 2025-3-8".
PATH_PATTERNS = [
    "{folder}/{base} No Mesh Mixamo.fbx",
    "{folder}/FBX Files/Game Ready/{base} No Mesh Mixamo.fbx",
    "{folder}/FBX Files/Mixamo/{base} No Mesh Mixamo.fbx",
    "{folder}/FBX Files/Mixamo/{base} Mixamo.fbx",
]

ENTRY_RE = re.compile(r"SG ASL (.+?)\s+(\d{4}-\d{1,2}-\d{1,2})\s+Upload$")


def _curl_ok(url):
    r = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "15", "-I", url],
        capture_output=True, text=True,
    )
    return r.stdout.strip() == "200"


def _list_letter_folder(letter):
    """One GitHub API call per starting letter -- lists every dictionary
    entry (folder) under that letter. Uses the API (not raw content)
    because directory listings aren't available any other way."""
    import urllib.request

    url = f"{GITHUB_API_BASE}/ASL%20{letter}"
    req = urllib.request.Request(url, headers={"User-Agent": "sign_project-fetch_mocap_words"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    if isinstance(data, dict):
        raise RuntimeError(f"GitHub API error for letter {letter}: {data.get('message')}")
    return [item["name"] for item in data if item["type"] == "dir"]


def _extract_core_and_date(folder_name):
    m = ENTRY_RE.match(folder_name)
    if not m:
        return None, None
    core = re.sub(r"\s+Alt(\s+\d+)?$", "", m.group(1))
    core = re.sub(r"\s+\d+$", "", core)
    return core.strip().lower(), m.group(2)


def _date_key(d):
    y, mo, da = d.split("-")
    return (int(y), int(mo), int(da))


def resolve_word(word, entries_by_core):
    """Returns a resolved raw-content URL for `word`'s newest archive
    take, or None if no known path pattern matches."""
    takes = entries_by_core.get(word.lower())
    if not takes:
        return None
    takes = sorted(takes, key=lambda t: _date_key(t[0]), reverse=True)
    date, letter, folder = takes[0]
    base = re.sub(r"\s+Upload$", "", folder)

    for pattern in PATH_PATTERNS:
        rel = pattern.format(folder=folder, base=base)
        url = f"{ARCHIVE_BASE}/ASL%20{letter}/{urllib.parse.quote(rel)}"
        if _curl_ok(url):
            return url
    return None


def main():
    os.makedirs(MOCAP_DIR, exist_ok=True)
    words = sorted(config.known_words())

    print("Listing archive entries for each available starting letter...")
    available_letters = "ABCDEFHMNOPTVWY"  # only letters the archive currently has
    entries_by_core = {}
    for letter in available_letters:
        try:
            names = _list_letter_folder(letter)
        except Exception as e:
            print(f"  WARNING: could not list letter {letter}: {e}")
            continue
        for name in names:
            core, date = _extract_core_and_date(name)
            if core is None:
                continue
            entries_by_core.setdefault(core, []).append((date, letter, name))
        time.sleep(0.3)

    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    resolved, skipped = 0, 0
    for word in words:
        if word[0].upper() not in available_letters:
            continue
        url = resolve_word(word, entries_by_core)
        if not url:
            skipped += 1
            continue

        dest_name = f"{word.replace(' ', '_')}.fbx"
        dest_path = os.path.join(MOCAP_DIR, dest_name)
        subprocess.run(["curl", "-sL", "--max-time", "30", "-o", dest_path, url], check=False)
        if os.path.getsize(dest_path) < 10_000:
            print(f"  FAILED download: {word}")
            os.remove(dest_path)
            skipped += 1
            continue

        manifest[word] = {
            "file": dest_name,
            "source_url": url,
            "source_repo": "https://github.com/StudioGalt/Sign-Language-Mocap-Archive",
            "license": "CC0-1.0",
        }
        resolved += 1
        print(f"  OK: {word}")
        time.sleep(0.15)

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nResolved {resolved} new/updated word(s), {skipped} unavailable in the archive.")
    print(f"Manifest now has {len(manifest)} total word(s) -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
