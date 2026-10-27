#!/usr/bin/env python3
"""Sign, check and publish the Daochi releases of apps the node offers.

The node serves each app as signed release v2 metadata beside its immutable
ZX portable executable. ZX hosts ask the node with format=zx; hosts released
before the ZX format keep their .zib releases through 2027-10-23. Inbe and Arcade publish their node apps with this tool, and Inbe's
node receiver imports it to check every release it accepts. Each owning
project keeps its own version ledger, built bundles and publisher pins:
apps/versions.json, build/node-apps and apps/publishers.json in the working
directory unless named.
"""
import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_.-]{0,62}\Z")
# Apps the node offers: inbe.<name>, never one of the IDs Inbe bundles.
NODE_APP_ID = re.compile(r"inbe\.[a-z][a-z0-9]{1,23}\Z")
BUNDLED_IDS = {"inbe", "inbe.habits", "inbe.practices", "inbe.lists", "inbe.diary", "inbe.lumi",
               "inbe.leaderboard"}
VERSION = re.compile(r"(?:0|[1-9][0-9]{0,8})\.(?:0|[1-9][0-9]{0,8})\.(?:0|[1-9][0-9]{0,8})\Z")
# The node keeps each app's newest ten releases in its history, so a device
# on an older host still finds one built for it; going back offers the
# newest three of them that still run on the device.
RETAINED_RELEASES = 10
# Payload signatures and the suffixes the node stores them under: ZX portable
# executables, and legacy bundles of hosts released before the ZX format.
SUFFIXES = ((b"ZX\0\0", ".zx"), (b"ZIB\0", ".zib"))


def payload_suffix(data):
    """.zx or legacy .zib for payload bytes, or None for anything else."""
    return next((suffix for signature, suffix in SUFFIXES if data.startswith(signature)), None)


def stored_payload(directory, value):
    """The node file of a release's module artifact, in whichever format it was stored."""
    digest = value["artifacts"][0]["sha256"]
    legacy = directory / (digest + ".zib")
    if legacy.is_file() and not (directory / (digest + ".zx")).is_file():
        return legacy
    return directory / (digest + ".zx")


def retained_releases(directory, releases):
    """The newest release in each payload format, then the newest others.

    Hosts released before the ZX format keep their last .zib release while
    newer hosts move on.
    """
    releases = sorted(releases, key=lambda value: value["sequence"], reverse=True)
    kept = []
    formats = set()
    for value in releases:
        found = stored_payload(directory, value).suffix
        if found not in formats and len(kept) < RETAINED_RELEASES:
            formats.add(found)
            kept.append(value)
    for value in releases:
        if len(kept) >= RETAINED_RELEASES:
            break
        if value not in kept:
            kept.append(value)
    return sorted(kept, key=lambda value: value["sequence"], reverse=True)


def node_app_id(app_id):
    return bool(NODE_APP_ID.fullmatch(app_id)) and app_id not in BUNDLED_IDS


def trusted_pin(publishers, key_id, app_id):
    """The pin that may sign app_id: named, or an app the node offers under its prefix."""
    return next((pin for pin in publishers if pin["key_id"] == key_id and
                 (app_id in pin["app_ids"] or
                  (node_app_id(app_id) and "inbe." in pin.get("app_prefixes", [])))), None)


def signing_message(value):
    fields = ("app_id", "sequence", "version", "runtime", "host_api",
              "module_api", "data_schema", "key_id")
    lines = ["daochi-zib-release-v2", *(str(value[name]) for name in fields),
             str(len(value["artifacts"]))]
    for artifact in value["artifacts"]:
        lines.extend(str(artifact[name]) for name in ("variant", "sha256", "size"))
    lines.append(str(len(value["dependencies"])))
    for dependency in value["dependencies"]:
        lines.extend(str(dependency[name]) for name in ("app_id", "version", "sha256", "size"))
    return ("\n".join(lines) + "\n").encode("ascii")


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix=".inbe-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def version_tuple(value):
    return tuple(map(int, value["version"].split(".")))


def validate_release(value, app_id, publishers):
    fields = {"app_id", "sequence", "version", "runtime", "host_api", "module_api",
              "data_schema", "key_id", "artifacts", "dependencies", "signature"}
    # A beta app the node offers carries "channel":"beta"; apps hide it until
    # a person shows beta apps. It changes who sees the app, not what runs.
    present = set(value) - {"channel"} if isinstance(value, dict) else set()
    if not isinstance(value, dict) or present != fields or value["app_id"] != app_id or \
            value["runtime"] != "kryon-app-v1" or value.get("channel", "beta") != "beta" or \
            ("channel" in value and not node_app_id(app_id)):
        raise ValueError("invalid release identity or fields")
    if not isinstance(value["version"], str) or not VERSION.fullmatch(value["version"]):
        raise ValueError("invalid numeric release version")
    for field, minimum, maximum in (("sequence", 1, 2**31 - 1), ("host_api", 1, 65535),
                                     ("module_api", 1, 65535), ("data_schema", 0, 65535)):
        if type(value[field]) is not int or not minimum <= value[field] <= maximum:
            raise ValueError("invalid release sequence or API version")
    if not isinstance(value["artifacts"], list) or len(value["artifacts"]) != 1:
        raise ValueError("Inbe release must contain exactly one module artifact")
    artifact = value["artifacts"][0]
    if not isinstance(artifact, dict) or set(artifact) != {"variant", "sha256", "size"} or \
            artifact["variant"] != "module" or not isinstance(artifact["sha256"], str) or \
            not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]) or \
            type(artifact["size"]) is not int or not 8 <= artifact["size"] <= 64 * 1024 * 1024:
        raise ValueError("invalid module artifact")
    dependencies = value["dependencies"]
    # Inbe's root depends on each app it bundles; every other app on none.
    expected = sorted(BUNDLED_IDS - {"inbe"}) if app_id == "inbe" else []
    # Roots built before Leaderboard became an app have no dependency on it.
    if app_id == "inbe" and isinstance(dependencies, list) and \
            len(dependencies) == len(expected) - 1:
        expected.remove("inbe.leaderboard")
    if not isinstance(dependencies, list) or len(dependencies) != len(expected):
        raise ValueError("invalid root dependencies")
    for dependency, expected_id in zip(dependencies, expected):
        if not isinstance(dependency, dict) or set(dependency) != {"app_id", "version", "sha256", "size"} or \
                dependency["app_id"] != expected_id or not isinstance(dependency["version"], str) or \
                not VERSION.fullmatch(dependency["version"]) or not isinstance(dependency["sha256"], str) or \
                not re.fullmatch(r"[0-9a-f]{64}", dependency["sha256"]) or \
                type(dependency["size"]) is not int or not 8 <= dependency["size"] <= 64 * 1024 * 1024:
            raise ValueError("invalid dependency descriptor")
    pin = trusted_pin(publishers, value["key_id"], app_id)
    if pin is None:
        raise ValueError("publisher is not trusted for this app")
    try:
        if not isinstance(value["signature"], str) or not re.fullmatch(r"[0-9a-f]{128}", value["signature"]):
            raise ValueError("invalid release signature")
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin["public_key"])).verify(
            bytes.fromhex(value["signature"]), signing_message(value))
    except Exception as error:
        raise ValueError("release signature rejected") from error


def write_history(directory, app_id, publishers):
    """Lists up to ten releases, newest first, in history-v2.json.

    Every release stays archived. The history names the newest ones the node
    still trusts and still has the payload for, always including the newest
    release in each payload format.
    """
    releases = []
    for path in directory.glob("release-*.json"):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            continue
        try:
            value = json.loads(path.read_bytes())
            validate_release(value, app_id, publishers)
        except (ValueError, KeyError, TypeError):
            continue
        payload = stored_payload(directory, value)
        if path.name == f"release-{value['sequence']}.json" and payload.is_file():
            releases.append(value)
    if not releases:
        return
    history = dict(versions=retained_releases(directory, releases))
    atomic_write(directory / "history-v2.json", (json.dumps(history, separators=(",", ":")) + "\n").encode())


def write_histories(store, publishers_path):
    """Writes the history of every app in the store, under its publication lock."""
    publishers = json.loads(publishers_path.read_text())
    for directory in sorted(store.iterdir()):
        app_id = directory.name
        if directory.is_symlink() or not directory.is_dir() or \
                (app_id not in BUNDLED_IDS and not node_app_id(app_id)) or \
                not (directory / "latest-v2.json").is_file():
            continue
        with (directory / ".publish.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            write_history(directory, app_id, publishers)


def open_public_url(url, timeout):
    return urlopen(Request(url, headers={"User-Agent": "Inbe-Publisher/1.0"}), timeout=timeout)


def upload(archive, target, remote_store):
    """Streams archive to the node's one restricted upload command."""
    options = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes"]
    if os.environ.get("INBE_SSH_IDENTITY"):
        # Only the upload key, never another key from an agent or ~/.ssh.
        options += ["-i", os.environ["INBE_SSH_IDENTITY"], "-o", "IdentitiesOnly=yes"]
    if os.environ.get("INBE_SSH_KNOWN_HOSTS"):
        options += ["-o", "UserKnownHostsFile=" + os.environ["INBE_SSH_KNOWN_HOSTS"]]
    with archive.open("rb") as stream:
        subprocess.run(["ssh", *options, "--", target, shlex.join(["inbe-packages", remote_store])],
                       stdin=stream, check=True)


def node_app_release(name, key, key_id, beta=False, *, ledger_path, bundle_directory):
    """The signed release of NAME.zx in bundle_directory from its ledger entry."""
    versions = json.loads(ledger_path.read_text())
    component = versions.get("node_apps", {}).get(name)
    if component is None or not node_app_id(component["id"]) or component["id"] != "inbe." + name:
        raise ValueError(f"{name} is not an app the node offers")
    if not VERSION.fullmatch(component["version"]) or not 0 < component["sequence"] <= 2**31 - 1:
        raise ValueError(f"invalid {name} version or sequence")
    data = (bundle_directory / f"{name}.zx").read_bytes()
    if not data.startswith(b"ZX\0\0") or not 8 <= len(data) <= 64 * 1024 * 1024:
        raise ValueError(f"invalid {name} portable executable")
    value = dict(app_id=component["id"], sequence=component["sequence"], version=component["version"],
                 runtime="kryon-app-v1", host_api=component.get("host_api", versions["host_api"]),
                 module_api=versions["module_api"], data_schema=0, key_id=key_id,
                 artifacts=[dict(variant="module", sha256=sha256(data).hexdigest(), size=len(data))],
                 dependencies=[])
    value["signature"] = key.sign(signing_message(value)).hex()
    if beta or component.get("beta") is True:
        value["channel"] = "beta"
    return value, data


# A collection such as Arcade carries no games: each is downloaded on its
# own. They sit beside its bundle in NAME.games/<sha256>.zx, and its catalog
# pins their digests. The node serves a file only for a signed release that
# names it, so each game gets a lookup: this same release with that game as
# its module. It is never a latest or archived release.
GAME_LIMIT = 32


def node_app_games(value, key, bundle_directory, name):
    """Signed lookups and bytes of the games NAME downloads one by one."""
    directory = bundle_directory / f"{name}.games"
    games = []
    for path in sorted(directory.glob("*.zx")) if directory.is_dir() else []:
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        if path.name != digest + ".zx" or not data.startswith(b"ZX\0\0") or not 8 <= len(data) <= 64 * 1024 * 1024:
            raise ValueError(f"invalid {name} game payload {path.name}")
        lookup = {field: item for field, item in value.items() if field != "signature"}
        lookup["artifacts"] = [dict(variant="module", sha256=digest, size=len(data))]
        lookup["signature"] = key.sign(signing_message(lookup)).hex()
        games.append((lookup, data))
    if len(games) > GAME_LIMIT:
        raise ValueError(f"{name} names more than {GAME_LIMIT} games")
    return games


def game_lookups(directory, value):
    """The stored lookups of a release's games."""
    lookups = []
    main = value["artifacts"][0]["sha256"]
    for path in sorted(directory.glob("*.zx.release-v2.json")):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            continue
        lookup = json.loads(path.read_bytes())
        if lookup.get("sequence") == value["sequence"] and lookup.get("version") == value["version"] and \
                lookup["artifacts"][0]["sha256"] != main:
            lookups.append(lookup)
    return lookups


def stage_node_app(store, name, key_path, key_id, publishers_path, beta=False, *,
                   ledger_path, bundle_directory):
    if not IDENTIFIER.fullmatch(key_id) or key_id in (".", ".."):
        raise ValueError("invalid publisher key ID")
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("publisher key must be Ed25519")
    publishers = json.loads(publishers_path.read_text())
    value, data = node_app_release(name, key, key_id, beta, ledger_path=ledger_path,
                                   bundle_directory=bundle_directory)
    validate_release(value, value["app_id"], publishers)
    games = node_app_games(value, key, bundle_directory, name)
    for lookup, _ in games:
        validate_release(lookup, value["app_id"], publishers)
    directory = store / value["app_id"]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(value, separators=(",", ":")) + "\n").encode()
    with (directory / ".publish.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        write_node_app(directory, value, encoded, data, publishers, games)
    return value


def write_node_app(directory, value, encoded, data, publishers, games=()):
    """Publishes one release of an app the node offers, and its games, into its directory."""
    current = directory / "latest-v2.json"
    if current.exists():
        previous = json.loads(current.read_bytes())
        if previous != value and (value["sequence"] <= previous["sequence"] or
                version_tuple(value) <= version_tuple(previous)):
            raise ValueError(f"{value['app_id']} changed: advance its version and sequence")
    suffix = payload_suffix(data)
    if suffix is None:
        raise ValueError("payload is not a ZX portable executable")
    payload = directory / (value["artifacts"][0]["sha256"] + suffix)
    archive = directory / f"release-{value['sequence']}.json"
    if payload.exists() and payload.read_bytes() != data:
        raise ValueError("immutable payload does not match its hash")
    if archive.exists() and archive.read_bytes() != encoded:
        raise ValueError("release sequence is already occupied")
    for lookup, game in games:
        stored = directory / (lookup["artifacts"][0]["sha256"] + ".zx")
        if stored.exists() and stored.read_bytes() != game:
            raise ValueError("immutable game payload does not match its hash")
        atomic_write(stored, game)
        # An unchanged game keeps its bytes; its lookup names the newest release.
        atomic_write(stored.with_name(stored.name + ".release-v2.json"),
                     (json.dumps(lookup, separators=(",", ":")) + "\n").encode())
    atomic_write(payload, data)
    atomic_write(payload.with_name(payload.name + ".release-v2.json"), encoded)
    atomic_write(archive, encoded)
    atomic_write(current, encoded)
    write_history(directory, value["app_id"], publishers)


def import_node_app(entries, store, publishers, app_id):
    """Node-side merge of one app the node offers, signed and without dependencies."""
    encoded = entries.get(f"{app_id}/latest-v2.json")
    if encoded is None or len(encoded) > 65536:
        raise ValueError("missing or oversized release metadata")
    value = json.loads(encoded)
    validate_release(value, app_id, publishers)
    if value["dependencies"]:
        raise ValueError("an app the node offers has no dependencies")
    artifact = value["artifacts"][0]
    names = [artifact["sha256"] + suffix for _, suffix in SUFFIXES
             if f"{app_id}/{artifact['sha256']}{suffix}" in entries]
    payload = names[0] if len(names) == 1 else ""
    data = entries.get(f"{app_id}/{payload}", b"")
    if artifact["size"] != len(data) or sha256(data).hexdigest() != artifact["sha256"] or \
            payload_suffix(data) is None or not payload.endswith(payload_suffix(data)):
        raise ValueError("payload hash mismatch")
    expected = {f"{app_id}/latest-v2.json", f"{app_id}/{payload}",
                f"{app_id}/{payload}.release-v2.json",
                f"{app_id}/release-{value['sequence']}.json"}
    # Its games: each a signed lookup of this release beside the game's bytes.
    games = []
    for name in sorted(set(entries) - expected):
        if not name.endswith(".zx.release-v2.json"):
            continue
        encoded_lookup = entries[name]
        if len(encoded_lookup) > 65536:
            raise ValueError("oversized game lookup")
        lookup = json.loads(encoded_lookup)
        validate_release(lookup, app_id, publishers)
        game = lookup["artifacts"][0]
        file = f"{app_id}/{game['sha256']}.zx"
        game_bytes = entries.get(file, b"")
        if name != file + ".release-v2.json" or game["sha256"] == artifact["sha256"] or \
                {field: item for field, item in lookup.items() if field not in ("artifacts", "signature")} != \
                {field: item for field, item in value.items() if field not in ("artifacts", "signature")} or \
                len(game_bytes) != game["size"] or sha256(game_bytes).hexdigest() != game["sha256"] or \
                not game_bytes.startswith(b"ZX\0\0"):
            raise ValueError("game lookup does not match this release")
        expected.update((name, file))
        games.append((lookup, game_bytes))
    if len(games) > GAME_LIMIT or set(entries) != expected:
        raise ValueError("archive contains unreferenced content")
    directory = store / app_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / ".publish.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        write_node_app(directory, value, encoded, data, publishers, games)


def publish_node_app(store, name, target, remote_store):
    if not re.fullmatch(r"[a-zA-Z0-9_.@-]+", target) or target.startswith("-"):
        raise ValueError("invalid SSH target")
    if not remote_store.startswith("/") or "\n" in remote_store:
        raise ValueError("Daochi package store must be an absolute path")
    with tempfile.TemporaryDirectory(prefix="inbe-upload-") as staging:
        archive = Path(staging) / "packages.tar"
        directory = store / ("inbe." + name)
        value = json.loads((directory / "latest-v2.json").read_bytes())
        payload = stored_payload(directory, value).name
        games = [lookup["artifacts"][0]["sha256"] + ".zx" for lookup in game_lookups(directory, value)]
        with tarfile.open(archive, "w") as tar:
            for filename in ("latest-v2.json", payload, payload + ".release-v2.json",
                             f"release-{value['sequence']}.json",
                             *(name for game in games for name in (game, game + ".release-v2.json"))):
                path = directory / filename
                tar.add(path, arcname=str(path.relative_to(store)), recursive=False)
        upload(archive, target, remote_store)


def verify_node_app(store, name, origin, open_url=open_public_url):
    """Require the public node to serve the exact signed release of NAME."""
    app_id = "inbe." + name
    expected = json.loads((store / app_id / "latest-v2.json").read_bytes())
    route = origin.rstrip("/") + "/api/v2/packages/" + app_id
    payload = stored_payload(store / app_id, expected).name
    query = "/latest?bucket=0&format=zx" if payload.endswith(".zx") else "/latest?bucket=0"
    with open_url(route + query, timeout=30) as response:
        encoded = response.read(65537)
    if len(encoded) > 65536 or json.loads(encoded) != expected:
        raise ValueError(f"{app_id}: public release metadata differs from the signed publication")
    artifact = expected["artifacts"][0]
    with open_url(route + "/" + payload, timeout=30) as response:
        data = response.read(artifact["size"] + 1)
    if len(data) != artifact["size"] or sha256(data).hexdigest() != artifact["sha256"]:
        raise ValueError(f"{app_id}: public package hash or size differs from the signed publication")
    lookups = game_lookups(store / app_id, expected)
    for lookup in lookups:
        game = lookup["artifacts"][0]
        with open_url(route + "/" + game["sha256"] + ".zx", timeout=60) as response:
            data = response.read(game["size"] + 1)
        if len(data) != game["size"] or sha256(data).hexdigest() != game["sha256"]:
            raise ValueError(f"{app_id}: a public game differs from the signed publication")
    print(f"Verified the public release of {app_id}" + (f" and its {len(lookups)} games" if lookups else ""))


def registered_apps(origin, open_url=open_public_url):
    """The app IDs the node's registry lists as active."""
    with open_url(origin.rstrip("/") + "/api/v1/apps", timeout=30) as response:
        listing = json.loads(response.read(1048577))
    return {app.get("app_id") for app in listing.get("apps", []) if app.get("status") == "active"}


def served_release(origin, app_id, open_url=open_public_url):
    """The newest release the node serves for app_id in either format, or None.

    A new release must advance past it: the node keeps one sequence per app,
    whether its newest release is a .zx one or a legacy .zib one.
    """
    newest = None
    for query in ("/latest?bucket=0&format=zx", "/latest?bucket=0"):
        try:
            with open_url(origin.rstrip("/") + "/api/v2/packages/" + app_id + query,
                          timeout=30) as response:
                encoded = response.read(65537)
        except HTTPError as error:
            if error.code == 404:
                continue
            raise
        if len(encoded) > 65536:
            raise ValueError(f"{app_id}: public release metadata is too large")
        value = json.loads(encoded)
        if newest is None or value["sequence"] > newest["sequence"]:
            newest = value
    return newest


def publish_node_apps(store, key_path, key_id, target, remote_store, origin, publishers_path, *,
                      ledger_path, bundle_directory, open_url=open_public_url):
    """Publishes every app the node offers whose ledger names a newer release.

    Registering an app takes the node operator's key, which stays with the
    operator, so an app the node does not list yet is reported and skipped.
    """
    ledger = json.loads(ledger_path.read_text())
    registered = registered_apps(origin, open_url)
    for name, component in sorted(ledger.get("node_apps", {}).items()):
        app_id = component["id"]
        if app_id not in registered:
            print(f"::warning title=App packages::{app_id} is not registered on the node, so it was not published")
            continue
        served = served_release(origin, app_id, open_url)
        if served is not None and served["sequence"] >= component["sequence"]:
            print(f"{app_id} {served['version']} is already published")
            continue
        stage_node_app(store, name, key_path, key_id, publishers_path,
                       ledger_path=ledger_path, bundle_directory=bundle_directory)
        publish_node_app(store, name, target, remote_store)
        verify_node_app(store, name, origin, open_url)


def add_node_app_arguments(parser):
    parser.add_argument("--node-app", help="stage, and with --ssh-target publish, only this app the node offers")
    parser.add_argument("--node-apps", action="store_true",
                        help="publish every app the node offers whose ledger names a newer release")
    parser.add_argument("--app-ledger", type=Path, help="owning project's node-app version ledger")
    parser.add_argument("--bundle-directory", type=Path, help="owning project's built node-app bundles")
    parser.add_argument("--beta", action="store_true",
                        help="with --node-app: publish it as beta, listed only where beta apps are shown")


def publish_from_arguments(args, parser, project):
    """Runs --node-app or --node-apps for the project; False when neither is given."""
    publishers = args.publishers or project / "apps/publishers.json"
    ledger = args.app_ledger or project / "apps/versions.json"
    bundles = args.bundle_directory or project / "build/node-apps"
    rollout = getattr(args, "rollout", None)
    if args.node_apps:
        if not (args.key and args.key_id and args.ssh_target and args.remote_store and args.verify_origin) or \
                rollout is not None:
            parser.error("--node-apps needs --key, --key-id, --ssh-target, --remote-store and "
                         "--verify-origin, without --rollout")
        publish_node_apps(args.store, args.key, args.key_id, args.ssh_target, args.remote_store,
                          args.verify_origin, publishers, ledger_path=ledger, bundle_directory=bundles)
        return True
    if args.node_app:
        if not args.key or not args.key_id or rollout is not None:
            parser.error("--node-app needs --key and --key-id, without --rollout")
        stage_node_app(args.store, args.node_app, args.key, args.key_id, publishers, args.beta,
                       ledger_path=ledger, bundle_directory=bundles)
        if args.ssh_target:
            if not args.remote_store or not args.verify_origin:
                parser.error("publishing an app the node offers needs --remote-store and --verify-origin")
            publish_node_app(args.store, args.node_app, args.ssh_target, args.remote_store)
            verify_node_app(args.store, args.node_app, args.verify_origin)
        print(f"{args.node_app} release " + ("published" if args.ssh_target else "staged"))
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--key-id")
    parser.add_argument("--ssh-target")
    parser.add_argument("--remote-store")
    parser.add_argument("--verify-origin", help="verify served release metadata and bytes after publishing")
    parser.add_argument("--publishers", type=Path, help="publisher pins the signing key must match")
    add_node_app_arguments(parser)
    args = parser.parse_args()
    try:
        if not publish_from_arguments(args, parser, Path.cwd()):
            parser.error("give --node-app NAME or --node-apps")
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Package publication failed: {error}\n")


if __name__ == "__main__":
    main()
