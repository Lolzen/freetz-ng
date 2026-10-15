#!/usr/bin/env python3
"""Bounded, opt-in OpenAI repair of a failed Freetz-NG build."""
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path.cwd()
MAX_ATTEMPTS = 3
ALLOWED = ("config/", "make/", "patches/", "tools/", "packages/", "make/")
FORBIDDEN = (".github/", ".git/", "scripts/auto_repair.py", ".config")


def run(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def github(method, endpoint, payload=None):
    req = urllib.request.Request(
        "https://api.github.com" + endpoint,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response) if response.status != 204 else {}


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY secret missing: automatic repair disabled.")
        return 0
    if os.environ.get("GITHUB_REF_NAME") != "labor":
        return 0
    subject = run("git", "log", "-1", "--format=%s").stdout.strip()
    match = re.search(r"\[auto-repair (\d+)/3\]", subject)
    attempt = int(match.group(1)) if match else 0
    if attempt >= MAX_ATTEMPTS:
        print("Maximum of 3 consecutive automatic repair attempts reached.")
        return 0

    # Only act on the commit that actually failed; never overwrite a newer push.
    branch = github("GET", "/repos/" + os.environ["GITHUB_REPOSITORY"] + "/branches/labor")
    head = run("git", "rev-parse", "HEAD").stdout.strip()
    if branch["commit"]["sha"] != head:
        print("Branch advanced since build started; skip repair.")
        return 0

    log = pathlib.Path("/tmp/freetz-build.log")
    diagnostic = log.read_text(errors="replace")[-32000:] if log.exists() else (
        "Build failed before make. Inspect workflow logs manually; no automatic patch.")
    if not log.exists():
        print(diagnostic)
        return 0

    # Supply focused source context, not a full repository or secrets.
    files = [
        "config/ui/toolchain.in", "config/ui/firmware.in",
        "config/avm/version.in", "make/libs/libatomic/libatomic.mk",
        "make/libs/libstdcxx/libstdcxx.mk",
    ]
    context = []
    for name in files:
        path = ROOT / name
        if path.is_file():
            content = path.read_text(errors="replace")
            context.append(f"FILE {name}\n{content[:16000]}")

    prompt = (
        "You are fixing a Freetz-NG build for FRITZ!Box 6850 5G V1, "
        "FRITZ!OS 8.40 Labor 136254 and custom Celllock. "
        "Diagnose the actual build error, do not guess. "
        "Return ONLY a git-compatible unified diff, with diff --git headers, "
        "or the exact word NO_FIX if evidence is insufficient. "
        "Modify only existing files under config/, make/, patches/, tools/ or packages/. "
        "Never edit GitHub workflows, scripts, secrets, credentials, or .config. "
        "Keep changes minimal and do not replace Labor with stable.\n\n"
        "BUILD LOG (tail):\n" + diagnostic +
        "\n\nSOURCE CONTEXT:\n" + "\n\n".join(context)
    )
    request = {
        "model": os.environ.get("OPENAI_REPAIR_MODEL", "gpt-5.4"),
        "input": prompt,
        "max_output_tokens": 6500,
        "store": False,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request).encode(),
        headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        answer = json.load(response)
    content = "\n".join(
        item.get("text", "") for msg in answer.get("output", [])
        if msg.get("type") == "message"
        for item in msg.get("content", []) if item.get("type") == "output_text"
    ).strip()
    if content.startswith("```"):
        content = re.sub(r"^\x60{3}(?:diff)?\s*|\s*\x60{3}$", "", content).strip()
    if content == "NO_FIX" or not content.startswith("diff --git "):
        print("Model supplied no validated patch.")
        return 0

    changed = re.findall(r"^diff --git a/(.+?) b/(.+)$", content, re.M)
    if not changed or len(changed) > 5:
        print("Rejected patch: invalid file count.")
        return 0
    for old, new in changed:
        if old != new or old.startswith(FORBIDDEN) or not old.startswith(ALLOWED):
            print("Rejected path:", old, new)
            return 0
        if not (ROOT / old).is_file():
            print("Rejected new/nonexistent path:", old)
            return 0

    patch = pathlib.Path("/tmp/freetz-auto-repair.patch")
    patch.write_text(content + "\n")
    if run("git", "apply", "--check", str(patch), check=False).returncode:
        print("Rejected patch: git apply --check failed.")
        return 0
    run("git", "apply", str(patch))
    diffcheck = run("git", "diff", "--check", check=False)
    if diffcheck.returncode:
        print("Rejected patch: whitespace errors.", diffcheck.stderr)
        run("git", "reset", "--hard", "HEAD")
        return 0
    # Validate configuration grammar using the project's own Kconfig machinery.
    validation = run("timeout", "300", "make", "olddefconfig", check=False)
    if validation.returncode:
        print("Rejected patch: olddefconfig failed:", validation.stderr[-2000:])
        run("git", "reset", "--hard", "HEAD")
        return 0
    run("git", "checkout", "--", ".config", check=False)
    paths = [p for p in run("git", "diff", "--name-only").stdout.splitlines() if p]
    if set(paths) != {old for old, _ in changed}:
        print("Rejected unexpected file modifications:", paths)
        run("git", "reset", "--hard", "HEAD")
        return 0
    run("git", "config", "user.name", "freetz-repair-bot")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "--", *paths)
    run("git", "commit", "-m", f"fix(labor): AI-assisted build repair [auto-repair {attempt + 1}/3]")
    pushed = run("git", "push", "origin", "HEAD:refs/heads/labor", check=False)
    if pushed.returncode:
        print("Push rejected (concurrent change?):", pushed.stderr[-1500:])
        return 1
    # A push made with GITHUB_TOKEN does not trigger push workflows.
    # workflow_dispatch is the documented exception.
    github("POST", "/repos/" + os.environ["GITHUB_REPOSITORY"] +
           "/actions/workflows/build.yml/dispatches", {"ref": "labor"})
    print("Patch pushed and new build dispatched.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Automatic repair stopped:", type(exc).__name__, str(exc))
        sys.exit(1)
