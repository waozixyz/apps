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

    def release(self, sequence, key=None, signature=b"ZX\0\0"):
        data = signature + b"photos-" + str(sequence).encode()
        value = dict(app_id="inbe.photos", sequence=sequence, version=f"1.0.{sequence}",
                     runtime="kryon-app-v1", host_api=2, module_api=2, data_schema=0, key_id="test",
                     artifacts=[dict(variant="module", sha256=sha256(data).hexdigest(), size=len(data))],
                     dependencies=[])
        value["signature"] = (key or self.key).sign(release.signing_message(value)).hex()
        value["channel"] = "beta"
        return value, data

    def publish(self, value, data, suffix=None):
        encoded = json.dumps(value).encode()
        payload = value["artifacts"][0]["sha256"] + (suffix or release.payload_suffix(data))
        entries = {"inbe.photos/latest-v2.json": encoded, f"inbe.photos/{payload}": data,
                   f"inbe.photos/{payload}.release-v2.json": encoded,
                   f"inbe.photos/release-{value['sequence']}.json": encoded}
        release.import_node_app(entries, self.store, self.publishers, "inbe.photos")

    def history(self):
        return json.loads((self.store / "inbe.photos" / "history-v2.json").read_bytes())["versions"]

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
