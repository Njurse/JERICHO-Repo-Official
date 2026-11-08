#!/usr/bin/env python3
"""sync_store.py - compare the store index with the newest source of every mod.

Why this exists: the store compares VERSIONS, so a package rebuilt without a
version bump is invisible to everyone who already has it, and a version nobody
remembered to check is never published. This tool asks the mod's own repository
for the newest ref (its highest semver release tag, else the branch head), reads
the mod.toml there, and says exactly what the store is missing.

    python tools/sync_store.py                 # check every mod
    python tools/sync_store.py --only carhacks # check one
    python tools/sync_store.py --publish       # build + index every NEWER version
    python tools/sync_store.py --publish --jericho ../REDRIVER2

--check never writes. --publish refuses to write if any mod changed without a
version bump: bump it in the mod repository first, then run --publish again.

Exit: 0 clean, 1 something needs attention, 2 usage.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.dirname(HERE)

DROP_DIRS = {".git", "D1CARS", "obj", "lib"}
DROP_EXT = {".pdb", ".ilk", ".exp", ".o"}
ROOT_DROP_EXT = {".lib", ".obj", ".idb"}
BUILD_ARTIFACTS = {".dll", ".so", ".dylib"}
TEXT_EXT = {".md", ".txt", ".toml", ".c", ".h", ".json", ".ini", ".bat", ".sh",
            ".py", ".obj", ".mtl", ".gitignore", ".gitattributes", ".yml",
            ".yaml", ".xml", ".csv", ".inc", ".cfg", ".ps1", ".lua"}
VER_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
VER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")


def warn(msg):
    print("sync_store: %s" % msg, file=sys.stderr)


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def parse_version(text):
    if not isinstance(text, str):
        return None
    m = VER.match(text.strip())
    if not m:
        return None
    return tuple(int(x) if x else 0 for x in m.groups())


def excluded(rel):
    parts = rel.split("/")
    if any(p in DROP_DIRS for p in parts[:-1]):
        return True
    if parts[-1] == ".git":
        return True
    ext = os.path.splitext(rel)[1].lower()
    if ext in DROP_EXT:
        return True
    if len(parts) == 1 and ext in ROOT_DROP_EXT:
        return True
    return False


def is_text(rel):
    return (os.path.splitext(rel)[1].lower() in TEXT_EXT
            or os.path.basename(rel) in (".gitignore", ".gitattributes"))


def file_hash(path, rel):
    with open(path, "rb") as fh:
        data = fh.read()
    if is_text(rel):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def content_map(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DROP_DIRS]
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        for name in filenames:
            rel = (rel_dir + "/" + name).lstrip("/")
            if excluded(rel):
                continue
            out[rel] = file_hash(os.path.join(dirpath, name), rel)
    return out


def zip_map(zip_path, mod_id):
    """The published package's files under its id folder, or None if malformed."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        prefix = None
        for cand in ("JERICHO/MODS/%s/" % mod_id, "MODS/%s/" % mod_id):
            if any(n.startswith(cand) for n in names):
                prefix = cand
                break
        if prefix is None:
            return None
        out = {}
        for name in names:
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            rel = name[len(prefix):]
            if not rel or excluded(rel):
                continue
            data = z.read(name)
            if is_text(rel):
                data = data.replace(b"\r\n", b"\n")
            out[rel] = hashlib.sha256(data).hexdigest()
        return out


def compare_content(source_root, zip_path, mod_id):
    src = content_map(source_root)
    pub = zip_map(zip_path, mod_id)
    if pub is None:
        return None, ["package has no JERICHO/MODS/%s/ folder" % mod_id]
    lower_count = {}
    for rel in pub:
        lower_count[rel.lower()] = lower_count.get(rel.lower(), 0) + 1
    src_ci = {k.lower(): (k, v) for k, v in src.items()}

    differs = []
    for rel, sha in sorted(pub.items()):
        if lower_count.get(rel.lower(), 0) > 1 and rel not in src:
            continue                      # a case-only duplicate; Windows cannot hold both
        if rel in src:
            hit = src[rel]
        else:
            ci = src_ci.get(rel.lower())
            if ci is None:
                if os.path.splitext(rel)[1].lower() in BUILD_ARTIFACTS:
                    continue              # the built DLL is not in source control
                differs.append(rel)
                continue
            hit = ci[1]
        if hit != sha:
            differs.append(rel)
    return src, differs


def ls_tags(repo):
    out = run(["git", "ls-remote", "--tags", "--refs", repo])
    tags = []
    for line in out.splitlines():
        ref = line.split("refs/tags/", 1)
        if len(ref) != 2:
            continue
        name = ref[1].strip()
        m = VER_TAG.match(name)
        if m:
            tags.append((tuple(int(x) for x in m.groups()), name))
    return tags


def resolve_ref(repo, branch, ignore_tags):
    if not ignore_tags:
        tags = ls_tags(repo)
        if tags:
            return max(tags)[1], "tag"
    return branch, "branch"


class Sources:
    def __init__(self, temp_root, jericho):
        self.temp = temp_root
        self.jericho = jericho
        self.clones = {}

    def root(self, mod_id, spec):
        if "jericho_subdir" in spec:
            if not self.jericho:
                return None, "local JERICHO", "pass --jericho (or set JERICHO_SRC)"
            root = os.path.join(self.jericho, spec["jericho_subdir"])
            if not os.path.isdir(root):
                return None, "local JERICHO", "no folder at %s" % root
            return root, "local", None

        repo = spec.get("repo")
        if not repo:
            return None, "-", "no repo or jericho_subdir in sources.json"
        ref, kind = resolve_ref(repo, spec.get("branch", "main"),
                                bool(spec.get("ignore_tags")))
        key = (repo, ref)
        if key not in self.clones:
            dest = os.path.join(self.temp, "clone-%d" % len(self.clones))
            run(["git", "-c", "core.autocrlf=false", "clone", "--quiet",
                 "--depth", "1", "--branch", ref, "--single-branch",
                 "--no-recurse-submodules", repo, dest])
            self.clones[key] = dest
        root = self.clones[key]
        sub = spec.get("subdir", ".")
        if sub and sub != ".":
            root = os.path.join(root, sub.replace("/", os.sep))
        label = "%s (%s)" % (ref, kind)
        return root, label, None


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def published_zip(entry):
    if not entry:
        return None
    name = os.path.basename(entry.get("file", ""))
    for cand in (os.path.join(STORE, "packages", name), os.path.join(STORE, name)):
        if name and os.path.isfile(cand):
            return cand
    return None


def pack(mod_id, version, root, out_dir):
    path = os.path.join(out_dir, "%s-%s.zip" % (mod_id, version))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in DROP_DIRS]
            rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if rel_dir == ".":
                rel_dir = ""
            for name in filenames:
                rel = (rel_dir + "/" + name).lstrip("/")
                if excluded(rel):
                    continue
                z.write(os.path.join(dirpath, name),
                        "JERICHO/MODS/%s/%s" % (mod_id, rel))
    return path


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_deps(manifest):
    deps = manifest.get("dependencies", manifest.get("requires", []))
    if isinstance(deps, str):
        deps = [d.strip() for d in deps.split(",") if d.strip()]
    return deps


def entry_from_manifest(mod_id, manifest, old, file_name, sha, size):
    entry = dict(old) if old else {}
    entry["id"] = mod_id
    entry["name"] = manifest.get("name", mod_id)
    entry["version"] = manifest["version"]
    if "author" in manifest and not old:
        entry["author"] = manifest["author"]
    if "description" in manifest:
        entry["description"] = manifest["description"]
    entry["file"] = "packages/%s" % file_name
    entry["sha256"] = sha
    if isinstance(manifest.get("interface"), int):
        entry["interface"] = manifest["interface"]
    deps = manifest_deps(manifest)
    if deps:
        entry["requires"] = deps
    elif "requires" in entry:
        del entry["requires"]
    default = manifest.get("default-enabled", manifest.get("default_enabled"))
    if isinstance(default, bool):
        entry["default_enabled"] = default
    entry["size"] = size
    return entry


def main(argv):
    ap = argparse.ArgumentParser(description="compare the store with each mod's newest source")
    ap.add_argument("--publish", action="store_true",
                    help="build and index every genuinely newer version")
    ap.add_argument("--only", action="append", default=[],
                    help="limit to a mod id (repeatable)")
    ap.add_argument("--jericho", default=os.environ.get("JERICHO_SRC"),
                    help="a JERICHO checkout for mods that live in-tree")
    args = ap.parse_args(argv[1:])

    with open(os.path.join(STORE, "mods.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    index = {e["id"]: e for e in doc["mods"]}
    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as fh:
        sources = json.load(fh)["mods"]

    wanted = [m for m in sources if not args.only or m in args.only]
    if args.only:
        unknown = set(args.only) - set(sources)
        if unknown:
            warn("unknown mod(s) in --only: %s" % ", ".join(sorted(unknown)))
            return 2

    temp = tempfile.mkdtemp(prefix="jericho-sync-")
    rows = []
    problems = 0
    try:
        src = Sources(temp, args.jericho)
        print("%-14s %-22s %-9s %-9s %-9s %s" %
              ("mod", "ref", "src_ver", "pub_ver", "content", "action"))
        for mod_id in wanted:
            spec = sources[mod_id]
            root, label, error = src.root(mod_id, spec)
            if error:
                print("%-14s %-22s %-9s %-9s %-9s %s" %
                      (mod_id, label, "-", "-", "-", "UNRESOLVED: " + error))
                problems += 1
                rows.append({"id": mod_id, "action": "UNRESOLVED", "error": error})
                continue
            with open(os.path.join(root, "mod.toml"), "rb") as fh:
                manifest = tomllib.load(fh)
            src_ver = manifest.get("version")
            entry = index.get(mod_id)
            pub_ver = entry.get("version") if entry else None
            zip_path = published_zip(entry)

            if zip_path is None:
                content = "missing" if entry is None else "no package"
                action = "MISSING FROM INDEX" if entry is None else "MISSING PACKAGE"
                problems += 1
            else:
                _src, differs = compare_content(root, zip_path, mod_id)
                if differs is None:
                    content = "malformed"
                    action = "MALFORMED PACKAGE"
                    problems += 1
                else:
                    content = "same" if not differs else "differs(%d)" % len(differs)
                    sv, pv = parse_version(src_ver), parse_version(pub_ver)
                    if entry is None:
                        action = "MISSING FROM INDEX"
                        problems += 1
                    elif sv is None:
                        action = "BAD VERSION"
                        problems += 1
                    elif pv is not None and sv < pv:
                        action = "OLDER THAN PUBLISHED"
                        problems += 1
                    elif pv is not None and sv > pv:
                        action = "UPDATE"
                    elif differs:
                        action = "BUMP NEEDED"
                        problems += 1
                    else:
                        action = "up to date"

            print("%-14s %-22s %-9s %-9s %-9s %s" %
                  (mod_id, label, src_ver or "?", pub_ver or "-", content, action))
            if action == "BUMP NEEDED":
                repo = spec.get("repo", "(local)")
                sub = spec.get("subdir", "")
                where = "%s/%s" % (repo, sub) if sub and sub != "." else repo
                for rel in (differs or [])[:8]:
                    print("    differs: %s" % rel)
                print("    bump version in %s/mod.toml and push, then re-run" % where)
            rows.append({"id": mod_id, "action": action, "manifest": manifest,
                         "root": root, "spec": spec, "differs": differs})

        if not args.publish:
            return 0 if problems == 0 else 1

        # --- publish only genuinely newer versions -------------------------
        blocked = [r for r in rows if r["action"] in ("BUMP NEEDED", "OLDER THAN PUBLISHED", "BAD VERSION")]
        if blocked:
            warn("refusing to publish while a version is wrong: %s" %
                 ", ".join(r["id"] for r in blocked))
            return 1

        out = os.path.join(temp, "out")
        os.makedirs(out, exist_ok=True)
        packages = os.path.join(STORE, "packages")
        os.makedirs(packages, exist_ok=True)
        changed = []
        for row in rows:
            if row["action"] not in ("UPDATE", "MISSING FROM INDEX"):
                continue
            mod_id = row["id"]
            manifest = row["manifest"]
            version = manifest["version"]
            if (manifest.get("runtime") or "").lower() == "dll":
                built = [n for n in os.listdir(row["root"])
                         if n.lower() == (mod_id + ".dll").lower()
                         or n.lower() == (mod_id + ".so").lower()]
                if not built:
                    warn("%s is a runtime DLL mod but %s.dll/.so is not in the source; "
                         "build it first (JERICHO/sdk/build_mods.sh) and re-run" %
                         (mod_id, mod_id))
                    return 1
            zip_path = pack(mod_id, version, row["root"], out)
            name = os.path.basename(zip_path)
            sha = sha256_of(zip_path)
            shutil.copyfile(zip_path, os.path.join(packages, name))
            old = index.get(mod_id)
            entry = entry_from_manifest(mod_id, manifest, old, name, sha,
                                        os.path.getsize(zip_path))
            if old is None:
                doc["mods"].append(entry)
                index[mod_id] = entry
            else:
                old.update(entry)
            changed.append((mod_id, version, name, sha, entry["size"]))
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    if args.publish:
        if not changed:
            print("sync_store: nothing newer to publish")
            return 0
        tmp = os.path.join(STORE, "mods.json.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, os.path.join(STORE, "mods.json"))
        for mod_id, version, name, sha, size in changed:
            print("published %-14s %-9s %-28s %8d B  %s" %
                  (mod_id, version, name, size, sha))
        print("sync_store: %d package(s) published; validate with check_mod_repo.py" %
              len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
