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

    def test_node_keeps_offering_the_newest_three_releases(self):
        values = []
        for sequence in range(1, 5):
            value, data = self.release(sequence)
            self.publish(value, data)
            values.append(value)
            self.assertEqual(self.history(), list(reversed(values))[:3])
        # Every release stays archived; only the offer is limited to three.
        self.assertEqual(len(list((self.store / "inbe.photos").glob("release-*.json"))), 4)

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
        for sequence in range(2, 6):
            self.publish(*self.release(sequence))
        self.assertEqual([value["sequence"] for value in self.history()], [5, 4, 1])
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


if __name__ == "__main__":
    unittest.main()
