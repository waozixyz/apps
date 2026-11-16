"""Sign, publish and offer the releases of apps the node offers, offline."""
from hashlib import sha256
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("node_release", ROOT / "scripts/node_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class NodeAppHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.store = self.directory / "packages"
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(serialization.Encoding.Raw,
                                                   serialization.PublicFormat.Raw).hex()
        self.publishers = [dict(key_id="test", public_key=public, app_ids=[], app_prefixes=["inbe."])]

    def release(self, sequence, key=None, signature=b"ZX\0\0", host_api=2):
        data = signature + b"photos-" + str(sequence).encode()
        value = dict(app_id="inbe.photos", sequence=sequence, version=f"1.0.{sequence}",
                     runtime="kryon-app-v1", host_api=host_api, module_api=2, data_schema=0, key_id="test",
                     artifacts=[dict(variant="module", sha256=sha256(data).hexdigest(), size=len(data))],
                     dependencies=[])
        value["signature"] = (key or self.key).sign(release.signing_message(value)).hex()
        value["channel"] = "beta"
        return value, data

    def publish(self, value, data, suffix=None, wasm=None):
        encoded = json.dumps(value).encode()
        payload = value["artifacts"][0]["sha256"] + (suffix or release.payload_suffix(data))
        entries = {"inbe.photos/latest-v2.json": encoded, f"inbe.photos/{payload}": data,
                   f"inbe.photos/{payload}.release-v2.json": encoded,
                   f"inbe.photos/release-{value['sequence']}.json": encoded}
        if wasm is not None:
            entries.update(self.wasm_entries(value, wasm))
        release.import_node_app(entries, self.store, self.publishers, "inbe.photos")

    def wasm_entries(self, value, module, key=None):
        """The archive entries of a release's signed WebAssembly variant."""
        variant = {field: item for field, item in value.items() if field != "signature"}
        variant["artifacts"] = [dict(variant="module", sha256=sha256(module).hexdigest(), size=len(module))]
        variant["signature"] = (key or self.key).sign(release.signing_message(variant)).hex()
        encoded = json.dumps(variant).encode()
        name = "inbe.photos/" + variant["artifacts"][0]["sha256"] + ".wasm"
        return {f"inbe.photos/release-{value['sequence']}.wasm.json": encoded, name: module,
                name + ".release-v2.json": encoded}

    @staticmethod
    def revision(number):
        return b"ZX\0\0" + number.to_bytes(4, "little")

    def history(self):
        return json.loads((self.store / "inbe.photos" / "history-v2.json").read_bytes())["versions"]

    def test_signed_artifact_sizes_use_checked_integer_range(self):
        for size in (64 * 1024 * 1024 + 1, release.PACKAGE_MAXIMUM_BYTES):
            value, _ = self.release(1)
            value['artifacts'][0]['size'] = size
            value['signature'] = self.key.sign(release.signing_message(value)).hex()
            release.validate_release(value, 'inbe.photos', self.publishers)
        for size in (False, 7, 2**63 - 1, 2**64, 12.5):
            value, _ = self.release(1)
            value['artifacts'][0]['size'] = size
            value['signature'] = self.key.sign(release.signing_message(value)).hex()
            with self.subTest(size=size), self.assertRaises(ValueError):
                release.validate_release(value, 'inbe.photos', self.publishers)

    def test_public_payload_verification_streams_and_rejects_damage(self):
        data = b'ZX\0\0' + b'payload' * 20000
        descriptor = dict(size=len(data), sha256=sha256(data).hexdigest())

        class Chunked(BytesIO):
            def read(self, size=-1):
                if not 0 < size <= 65536:
                    raise AssertionError('Unbounded payload read')
                return super().read(size)

        self.assertTrue(release.verify_payload(Chunked(data), descriptor))
        for damaged in (data[:-1], data + b'x', data[:-1] + b'x'):
            self.assertFalse(release.verify_payload(Chunked(damaged), descriptor))
        for size in (False, 7, 2**63):
            self.assertFalse(release.verify_payload(Chunked(data), descriptor | dict(size=size)))

    def test_local_payload_reads_require_exact_checked_size(self):
        path = self.directory / 'app.zx'
        path.write_bytes(b'ZX\0\0payload')
        self.assertEqual(release.read_bundle(path), path.read_bytes())
        path.write_bytes(b'not an executable')
        with self.assertRaises(ValueError):
            release.read_bundle(path)
        path.write_bytes(b'ZX')
        with self.assertRaises(ValueError):
            release.read_bundle(path)

    def test_node_keeps_the_newest_ten_releases(self):
        values = []
        for sequence in range(1, 13):
            value, data = self.release(sequence)
            self.publish(value, data)
            values.append(value)
            self.assertEqual(self.history(), list(reversed(values))[:10])
        # Every release stays archived; only the history is limited to ten.
        self.assertEqual(len(list((self.store / "inbe.photos").glob("release-*.json"))), 12)

    def test_history_lists_only_trusted_releases_with_their_bundle(self):
        for sequence in range(1, 4):
            self.publish(*self.release(sequence))
        directory = self.store / "inbe.photos"
        forged, _ = self.release(9, key=Ed25519PrivateKey.generate())
        (directory / "release-9.json").write_text(json.dumps(forged))
        (directory / (self.history()[2]["artifacts"][0]["sha256"] + ".zx")).unlink()
        pins = self.directory / "publishers.json"
        pins.write_text(json.dumps(self.publishers))
        release.write_histories(self.store, pins)
        self.assertEqual([value["sequence"] for value in self.history()], [3, 2])

    def test_hosts_from_before_the_zx_format_keep_their_last_release(self):
        legacy, data = self.release(1, signature=b"ZIB\0")
        self.publish(legacy, data)
        for sequence in range(2, 13):
            self.publish(*self.release(sequence))
        self.assertEqual([value["sequence"] for value in self.history()], [12, 11, 10, 9, 8, 7, 6, 5, 4, 1])
        directory = self.store / "inbe.photos"
        self.assertTrue((directory / (legacy["artifacts"][0]["sha256"] + ".zib")).is_file())
        latest = json.loads((directory / "latest-v2.json").read_bytes())
        self.assertTrue((directory / (latest["artifacts"][0]["sha256"] + ".zx")).is_file())

    def test_history_keeps_the_newest_release_of_every_revision_and_interface(self):
        # Released hosts run ZX revision 26 on host interface 43; hosts from
        # interface 44 run revision 28, and only one release has a web variant.
        released, data = self.release(1, signature=self.revision(26), host_api=43)
        self.publish(released, data)
        web, data = self.release(2, signature=self.revision(28), host_api=44)
        self.publish(web, data, wasm=b"\0asm\x01\0\0\0photos-2")
        for sequence in range(3, 16):
            self.publish(*self.release(sequence, signature=self.revision(28), host_api=44))
        self.assertEqual([value["sequence"] for value in self.history()], [15, 14, 13, 12, 11, 10, 9, 8, 2, 1])
        directory = self.store / "inbe.photos"
        self.assertEqual(len(list(directory.glob("release-*.json"))), 16)
        self.assertTrue((directory / "release-2.wasm.json").is_file())
        # A release mistakenly built with revision 28 for interface 43 is its
        # own group; it never displaces the released hosts' last release.
        self.publish(*self.release(16, signature=self.revision(28), host_api=43))
        self.assertEqual([value["sequence"] for value in self.history()], [16, 15, 14, 13, 12, 11, 10, 9, 2, 1])

    def test_history_never_exceeds_what_the_node_reads(self):
        for sequence in range(1, release.HISTORY_LIMIT + 3):
            self.publish(*self.release(sequence, signature=self.revision(28), host_api=sequence))
        history = self.history()
        self.assertEqual(len(history), release.HISTORY_LIMIT)
        self.assertEqual(history[0]["sequence"], release.HISTORY_LIMIT + 2)

    def test_a_web_variant_must_sign_this_release_and_its_module(self):
        value, data = self.release(1, signature=self.revision(28))
        module = b"\0asm\x01\0\0\0photos-1"
        encoded = json.dumps(value).encode()
        payload = value["artifacts"][0]["sha256"] + ".zx"
        entries = {"inbe.photos/latest-v2.json": encoded, f"inbe.photos/{payload}": data,
                   f"inbe.photos/{payload}.release-v2.json": encoded, "inbe.photos/release-1.json": encoded}
        other, _ = self.release(1, signature=self.revision(28), host_api=3)
        damaged = self.wasm_entries(value, module)
        name = next(name for name in damaged if name.endswith(".wasm"))
        damaged[name] = b"\0asm\x01\0\0\0photos-X"
        for variant in (self.wasm_entries(value, module, key=Ed25519PrivateKey.generate()),
                        self.wasm_entries(other, module), damaged,
                        self.wasm_entries(value, b"ZX\0\0not webassembly")):
            with self.subTest(variant=sorted(variant)), self.assertRaises(ValueError):
                release.import_node_app(entries | variant, self.directory / "refused", self.publishers,
                                        "inbe.photos")
        self.assertFalse((self.directory / "refused").exists())
        # A variant without its release's .zx has nothing it was lowered from.
        legacy, legacy_data = self.release(2, signature=b"ZIB\0")
        with self.assertRaises(ValueError):
            self.publish(legacy, legacy_data, wasm=module)
        self.publish(value, data, wasm=module)
        # A sequence keeps the one variant it was published with.
        with self.assertRaisesRegex(ValueError, "another WebAssembly variant"):
            self.publish(value, data, wasm=module + b"!")
        self.publish(value, data, wasm=module)

    def test_payload_must_match_its_name(self):
        value, data = self.release(1)
        with self.assertRaises(ValueError):
            self.publish(value, data, ".zib")
        legacy, legacy_data = self.release(2, signature=b"ZIB\0")
        with self.assertRaises(ValueError):
            self.publish(legacy, legacy_data, ".zx")
        unknown, unknown_data = self.release(3, signature=b"ZIR\0")
        with self.assertRaises(ValueError):
            self.publish(unknown, unknown_data, ".zx")

    def test_only_registered_apps_with_a_newer_release_are_published(self):
        ledger = self.directory / "versions.json"
        ledger.write_text(json.dumps(dict(host_api=2, module_api=2, node_apps=dict(
            photos=dict(id="inbe.photos", title="Photos", version="1.0.2", sequence=2, beta=True),
            chess=dict(id="inbe.chess", title="Chess", version="1.0.1", sequence=2),
            radio=dict(id="inbe.radio", title="Radio", version="1.0.0", sequence=1)))))
        served = {"inbe.photos": self.release(1)[0], "inbe.chess": dict(self.release(2)[0], app_id="inbe.chess")}

        def open_url(url, timeout):
            if url == "https://node.example/api/v1/apps":
                return BytesIO(json.dumps(dict(apps=[dict(app_id="inbe.photos", status="active"),
                                                     dict(app_id="inbe.chess", status="active"),
                                                     dict(app_id="inbe.radio", status="suspended")])).encode())
            app_id = url.split("/api/v2/packages/")[1].split("/")[0]
            # Today's node serves these apps only as legacy .zib releases.
            if url.endswith("/latest?bucket=0&format=zx"):
                raise HTTPError(url, 404, "Not Found", {}, None)
            self.assertTrue(url.endswith("/latest?bucket=0"))
            return BytesIO(json.dumps(served[app_id]).encode())

        published = []
        with patch.object(release, "stage_node_app") as stage, \
                patch.object(release, "publish_node_app", side_effect=lambda store, name, *_: published.append(name)), \
                patch.object(release, "verify_node_app"):
            release.publish_node_apps(self.store, Path("publisher.pem"), "test", "uploader@node.example",
                                      "/srv/packages", "https://node.example/", self.directory / "publishers.json",
                                      ledger_path=ledger, bundle_directory=self.directory / "node-apps",
                                      open_url=open_url)
        self.assertEqual(published, ["photos"])
        self.assertEqual(stage.call_args.args[1], "photos")

    def test_the_ledger_zx_revision_must_match_each_payload(self):
        bundles = self.directory / "node-apps"
        bundles.mkdir()
        ledger = self.directory / "versions.json"
        entry = dict(id="inbe.photos", title="Photos", version="1.0.1", sequence=1)
        for revision, ledger_value, component_value, accepted in (
                (28, 28, None, True), (26, 28, None, False), (28, None, None, True),
                (26, 28, 26, True), (28, 28, 26, False), (28, "28", None, False), (28, 0, None, False)):
            (bundles / "photos.zx").write_bytes(self.revision(revision) + b"photos")
            versions = dict(host_api=44, module_api=2, node_apps=dict(photos=dict(entry)))
            if ledger_value is not None:
                versions["zx_revision"] = ledger_value
            if component_value is not None:
                versions["node_apps"]["photos"]["zx_revision"] = component_value
            ledger.write_text(json.dumps(versions))
            with self.subTest(revision=revision, ledger=ledger_value, component=component_value):
                if accepted:
                    release.node_app_release("photos", self.key, "test", ledger_path=ledger, bundle_directory=bundles)
                else:
                    with self.assertRaises(ValueError):
                        release.node_app_release("photos", self.key, "test", ledger_path=ledger,
                                                 bundle_directory=bundles)

    def test_a_release_publishes_its_signed_webassembly_variant(self):
        import tarfile
        bundles = self.directory / "build"
        bundles.mkdir()
        (bundles / "photos.zx").write_bytes(self.revision(28) + b"photos")
        module = b"\0asm\x01\0\0\0photos lowered"
        (bundles / "photos.wasm").write_bytes(module)
        ledger = self.directory / "versions.json"
        ledger.write_text(json.dumps(dict(host_api=44, module_api=2, zx_revision=28, node_apps=dict(
            photos=dict(id="inbe.photos", title="Photos", version="1.0.1", sequence=1, beta=True)))))
        key_path = self.directory / "key.pem"
        key_path.write_bytes(self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()))
        publishers_path = self.directory / "publishers.json"
        publishers_path.write_text(json.dumps(self.publishers))
        staged = self.directory / "staged"
        value = release.stage_node_app(staged, "photos", key_path, "test", publishers_path,
                                       ledger_path=ledger, bundle_directory=bundles)
        uploaded = {}

        def upload(archive, target, remote_store):
            with tarfile.open(archive) as tar:
                uploaded.update({member.name: tar.extractfile(member).read() for member in tar.getmembers()})
        with patch.object(release, "upload", upload):
            release.publish_node_app(staged, "photos", "node", "/store")
        self.assertEqual(len(uploaded), 7)
        release.import_node_app(uploaded, self.store, self.publishers, "inbe.photos")
        node = self.store / "inbe.photos"
        variant = json.loads((node / "release-1.wasm.json").read_bytes())
        release.validate_release(variant, "inbe.photos", self.publishers)
        self.assertTrue(release.same_release(variant, value))
        self.assertEqual(variant["channel"], "beta")
        self.assertEqual(variant["artifacts"][0], dict(variant="module", sha256=sha256(module).hexdigest(),
                                                       size=len(module)))
        self.assertEqual((node / (variant["artifacts"][0]["sha256"] + ".wasm")).read_bytes(), module)
        # The release and its history still name the .zx; web hosts ask for the variant.
        self.assertEqual(json.loads((node / "latest-v2.json").read_bytes()), value)
        self.assertEqual([entry["artifacts"] for entry in self.history()], [value["artifacts"]])

        def open_url(url, timeout):
            name = url.rsplit("/", 1)[1]
            if name.startswith("latest"):
                name = "release-1.wasm.json" if name.endswith("format=wasm") else "latest-v2.json"
            return BytesIO((node / name).read_bytes())
        release.verify_node_app(staged, "photos", "https://node.test", open_url)
        (node / (variant["artifacts"][0]["sha256"] + ".wasm")).write_bytes(module[:-1] + b"!")
        with self.assertRaises(ValueError):
            release.verify_node_app(staged, "photos", "https://node.test", open_url)
        # A file that is not a WebAssembly module never signs.
        (bundles / "photos.wasm").write_bytes(b"ZX\0\0photos")
        with self.assertRaises(ValueError):
            release.stage_node_app(self.directory / "other", "photos", key_path, "test", publishers_path,
                                   ledger_path=ledger, bundle_directory=bundles)

    def test_ledger_beta_apps_are_signed_for_the_beta_channel(self):
        bundles = self.directory / "node-apps"
        bundles.mkdir()
        (bundles / "photos.zx").write_bytes(b"ZX\0\0photos")
        ledger = self.directory / "versions.json"
        ledger.write_text(json.dumps(dict(host_api=2, module_api=2, node_apps=dict(
            photos=dict(id="inbe.photos", title="Photos", version="1.0.1", sequence=1, beta=True)))))
        value, _ = release.node_app_release("photos", self.key, "test", ledger_path=ledger,
                                            bundle_directory=bundles)
        self.assertEqual(value["channel"], "beta")
        release.validate_release(value, "inbe.photos", self.publishers)


    def test_a_collection_publishes_its_games_to_download_one_by_one(self):
        import tarfile
        bundles = self.directory / "build"
        (bundles / "arcade.games").mkdir(parents=True)
        (bundles / "arcade.zx").write_bytes(b"ZX\0\0arcade")
        games = [b"ZX\0\0shovey", b"ZX\0\0editor"]
        for game in games:
            (bundles / "arcade.games" / (sha256(game).hexdigest() + ".zx")).write_bytes(game)
        ledger = self.directory / "versions.json"
        ledger.write_text(json.dumps(dict(host_api=31, module_api=2, node_apps=dict(
            arcade=dict(id="inbe.arcade", title="Arcade", version="1.0.0", sequence=7)))))
        key_path = self.directory / "key.pem"
        key_path.write_bytes(self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()))
        publishers_path = self.directory / "publishers.json"
        publishers_path.write_text(json.dumps(self.publishers))
        staged = self.directory / "staged"
        value = release.stage_node_app(staged, "arcade", key_path, "test", publishers_path,
                                       ledger_path=ledger, bundle_directory=bundles)
        uploaded = {}

        def upload(archive, target, remote_store):
            with tarfile.open(archive) as tar:
                uploaded.update({member.name: tar.extractfile(member).read() for member in tar.getmembers()})
        with patch.object(release, "upload", upload):
            release.publish_node_app(staged, "arcade", "node", "/store")
        self.assertEqual(len(uploaded), 4 + 2 * len(games))
        # A game whose bytes the release does not sign never imports.
        tampered = dict(uploaded)
        tampered[f"inbe.arcade/{sha256(games[0]).hexdigest()}.zx"] = b"ZX\0\0other!"
        with self.assertRaises(ValueError):
            release.import_node_app(tampered, self.directory / "other", self.publishers, "inbe.arcade")
        release.import_node_app(uploaded, self.store, self.publishers, "inbe.arcade")
        node = self.store / "inbe.arcade"
        for game in games:
            digest = sha256(game).hexdigest()
            self.assertEqual((node / (digest + ".zx")).read_bytes(), game)
            lookup = json.loads((node / (digest + ".zx.release-v2.json")).read_bytes())
            self.assertEqual((lookup["sequence"], lookup["artifacts"][0]["sha256"]), (value["sequence"], digest))
        # The latest release and the history name only the collection itself.
        self.assertEqual(json.loads((node / "latest-v2.json").read_bytes()), value)
        versions = json.loads((node / "history-v2.json").read_bytes())["versions"]
        self.assertEqual([entry["artifacts"] for entry in versions], [value["artifacts"]])

        def open_url(url, timeout):
            name = url.rsplit("/", 1)[1]
            return BytesIO((node / ("latest-v2.json" if name.startswith("latest") else name)).read_bytes())
        release.verify_node_app(staged, "arcade", "https://node.test", open_url)
        (node / (sha256(games[1]).hexdigest() + ".zx")).write_bytes(b"ZX\0\0stale!")
        with self.assertRaises(ValueError):
            release.verify_node_app(staged, "arcade", "https://node.test", open_url)


class ExactNodeAppIdTest(unittest.TestCase):
    """A game publishes under its own exact ID once a publisher pin names it."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.key = Ed25519PrivateKey.generate()
        public = self.key.public_key().public_bytes(serialization.Encoding.Raw,
                                                   serialization.PublicFormat.Raw).hex()
        self.publishers = [dict(key_id="test", public_key=public, app_ids=[], app_prefixes=["inbe."],
                                node_app_ids=["xyz.waozi.wurm"])]
        self.publishers_path = self.directory / "publishers.json"
        self.publishers_path.write_text(json.dumps(self.publishers))
        self.key_path = self.directory / "key.pem"
        self.key_path.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,
                                                         serialization.PrivateFormat.PKCS8,
                                                         serialization.NoEncryption()))
        self.bundles = self.directory / "build"
        self.bundles.mkdir()
        for name in ("wurm", "other", "photos"):
            (self.bundles / f"{name}.zx").write_bytes(b"ZX\0\0" + name.encode())
        self.ledger = self.directory / "versions.json"
        self.ledger.write_text(json.dumps(dict(host_api=31, module_api=2, node_apps=dict(
            wurm=dict(id="xyz.waozi.wurm", title="Wurm", version="0.2.28", sequence=28),
            other=dict(id="xyz.waozi.other", title="Other", version="1.0.0", sequence=1),
            photos=dict(id="inbe.photos", title="Photos", version="1.0.1", sequence=1)))))
        self.staged = self.directory / "staged"
        self.node = self.directory / "node"

    def stage(self, name, publishers_path=None):
        return release.stage_node_app(self.staged, name, self.key_path, "test",
                                      publishers_path or self.publishers_path,
                                      ledger_path=self.ledger, bundle_directory=self.bundles)

    def receive(self, archive, target, remote_store):
        """The node's receiver: the archive names one app, imported with the node's pins."""
        import tarfile
        with tarfile.open(archive) as tar:
            entries = {member.name: tar.extractfile(member).read() for member in tar.getmembers()}
        (app_id,) = {name.split("/")[0] for name in entries}
        release.import_node_app(entries, self.node, self.publishers, app_id)

    def open_url(self, url, timeout):
        if url == "https://node.test/api/v1/apps":
            return BytesIO(json.dumps(dict(apps=[dict(app_id="xyz.waozi.wurm", status="active"),
                                                 dict(app_id="xyz.waozi.other", status="active")])).encode())
        app_id, name = url.split("/api/v2/packages/")[1].split("/")
        path = self.node / app_id / ("latest-v2.json" if name.startswith("latest") else name)
        if not path.is_file():
            raise HTTPError(url, 404, "Not Found", {}, None)
        return BytesIO(path.read_bytes())

    def test_a_configured_exact_id_signs_stages_imports_and_verifies(self):
        ledger = json.loads(self.ledger.read_text())
        del ledger["node_apps"]["other"], ledger["node_apps"]["photos"]
        self.ledger.write_text(json.dumps(ledger))
        with patch.object(release, "upload", self.receive):
            release.publish_node_apps(self.staged, self.key_path, "test", "uploader@node.test", "/srv/packages",
                                      "https://node.test", self.publishers_path, ledger_path=self.ledger,
                                      bundle_directory=self.bundles, open_url=self.open_url)
        staged = json.loads((self.staged / "xyz.waozi.wurm" / "latest-v2.json").read_bytes())
        self.assertEqual((staged["app_id"], staged["version"], staged["sequence"]), ("xyz.waozi.wurm", "0.2.28", 28))
        release.validate_release(staged, "xyz.waozi.wurm", self.publishers)
        served = self.node / "xyz.waozi.wurm"
        self.assertEqual(json.loads((served / "latest-v2.json").read_bytes()), staged)
        self.assertEqual((served / (staged["artifacts"][0]["sha256"] + ".zx")).read_bytes(), b"ZX\0\0wurm")
        self.assertEqual(json.loads((served / "history-v2.json").read_bytes())["versions"], [staged])
        release.write_histories(self.node, self.publishers_path)
        self.assertEqual(json.loads((served / "history-v2.json").read_bytes())["versions"], [staged])
        # Publishing again finds the release served and skips it.
        with patch.object(release, "stage_node_app") as stage:
            release.publish_node_apps(self.staged, self.key_path, "test", "uploader@node.test", "/srv/packages",
                                      "https://node.test", self.publishers_path, ledger_path=self.ledger,
                                      bundle_directory=self.bundles, open_url=self.open_url)
        stage.assert_not_called()
        # Verification reads the node's bytes, so a changed payload fails it.
        (served / (staged["artifacts"][0]["sha256"] + ".zx")).write_bytes(b"ZX\0\0wurn")
        with self.assertRaises(ValueError):
            release.verify_node_app(self.staged, "wurm", "https://node.test", self.open_url, app_id="xyz.waozi.wurm")

    def test_an_unconfigured_exact_id_is_refused(self):
        self.assertFalse(release.node_app_id("xyz.waozi.other", self.publishers))
        self.assertIsNone(release.trusted_pin(self.publishers, "test", "xyz.waozi.other"))
        with self.assertRaises(ValueError):
            self.stage("other")
        self.assertFalse((self.staged / "xyz.waozi.other").exists())
        # A release signed for it anyway never imports on the node.
        data = b"ZX\0\0other"
        value = dict(app_id="xyz.waozi.other", sequence=1, version="1.0.0", runtime="kryon-app-v1", host_api=31,
                     module_api=2, data_schema=0, key_id="test",
                     artifacts=[dict(variant="module", sha256=sha256(data).hexdigest(), size=len(data))],
                     dependencies=[])
        value["signature"] = self.key.sign(release.signing_message(value)).hex()
        encoded = json.dumps(value).encode()
        payload = value["artifacts"][0]["sha256"] + ".zx"
        entries = {"xyz.waozi.other/latest-v2.json": encoded, f"xyz.waozi.other/{payload}": data,
                   f"xyz.waozi.other/{payload}.release-v2.json": encoded,
                   "xyz.waozi.other/release-1.json": encoded}
        with self.assertRaises(ValueError):
            release.import_node_app(entries, self.node, self.publishers, "xyz.waozi.other")
        self.assertFalse((self.node / "xyz.waozi.other").exists())
        # Naming it to the node is not enough: the pin itself must name it.
        other_pin = dict(self.publishers[0], key_id="other", node_app_ids=["xyz.waozi.other"])
        self.assertIsNone(release.trusted_pin([self.publishers[0], other_pin], "test", "xyz.waozi.other"))
        with self.assertRaises(ValueError):
            release.import_node_app(entries, self.node, [self.publishers[0], other_pin], "xyz.waozi.other")

    def test_exact_ids_stay_outside_inbe_and_match_their_ledger_name(self):
        pins = [dict(self.publishers[0], node_app_ids=["inbe", "inbe.habits", "inbe.chess", "wurm", "xyz.wurm",
                                                       "xyz.waozi.Wurm", "xyz..wurm", "xyz.waozi.wurm"])]
        self.assertEqual([app_id for app_id in pins[0]["node_app_ids"] if release.node_app_id(app_id, pins)],
                         ["inbe.chess", "xyz.waozi.wurm"])
        self.assertIsNone(release.trusted_pin([dict(pins[0], app_prefixes=[])], "test", "inbe.chess"))
        ledger = json.loads(self.ledger.read_text())
        ledger["node_apps"]["chess"] = dict(ledger["node_apps"]["wurm"])
        self.ledger.write_text(json.dumps(ledger))
        (self.bundles / "chess.zx").write_bytes(b"ZX\0\0chess")
        with self.assertRaisesRegex(ValueError, "not an app the node offers"):
            self.stage("chess")

    def test_inbe_apps_publish_as_before(self):
        self.assertTrue(release.node_app_id("inbe.photos"))
        self.assertFalse(release.node_app_id("inbe.habits", self.publishers))
        self.assertFalse(release.node_app_id("xyz.waozi.wurm"))
        legacy = self.directory / "legacy.json"
        legacy.write_text(json.dumps([{field: item for field, item in self.publishers[0].items()
                                       if field != "node_app_ids"}]))
        value = self.stage("photos", legacy)
        self.assertEqual(value["app_id"], "inbe.photos")
        self.assertTrue((self.staged / "inbe.photos" / "latest-v2.json").is_file())
        with self.assertRaises(ValueError):
            self.stage("wurm", legacy)


if __name__ == "__main__":
    unittest.main()
