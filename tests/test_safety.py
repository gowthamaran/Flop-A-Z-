"""Safety tests — run with:  .venv/bin/python -m unittest discover tests"""

import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flopaz import config, system, ui  # noqa: E402


class AllowlistTest(unittest.TestCase):
    def test_official(self):
        for u in ("https://testnet.flop.network/", "wss://testnet.flop.network/",
                  "https://explorer.devnet.flop.network/x.tar.gz",
                  "https://github.com/flop-labs/network",
                  "https://hermes-agent.nousresearch.com/install.sh"):
            self.assertTrue(config.is_official(u), u)

    def test_rejected(self):
        for u in ("http://flop.network/", "https://flop.network.attacker.com/",
                  "https://evil-flop.network.io/", "https://github.com/someone/flop-labs"):
            self.assertFalse(config.is_official(u), u)


class RedactionTest(unittest.TestCase):
    def test_hex_key(self):
        self.assertNotIn("ab" * 32, ui.redact("0x" + "ab" * 32))

    def test_public_hash_kept(self):
        g = "0x" + "cd" * 32
        ui.allow_public_hash(g)
        self.assertIn(g, ui.redact(g))

    def test_phrase(self):
        phrase = " ".join(["apple"] * 12)
        self.assertNotIn(phrase, ui.redact(phrase))

    def test_password_line(self):
        self.assertNotIn("hunter2", ui.redact("password=hunter2"))


class ExtractTest(unittest.TestCase):
    def test_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            arc = Path(d) / "evil.tar.gz"
            with tarfile.open(arc, "w:gz") as t:
                ti = tarfile.TarInfo("../../escape")
                ti.size = 1
                t.addfile(ti, io.BytesIO(b"x"))
            with self.assertRaises(RuntimeError):
                system.safe_extract(arc, Path(d) / "out")


class TemplateTest(unittest.TestCase):
    def test_templates_parse_and_never_echo_secrets(self):
        cmds = config.load()["flop_cli"]["commands"]
        for key, tmpl in cmds.items():
            self.assertTrue(tmpl.startswith("flop "), key)
            self.assertNotIn("--show-secret", tmpl, key)
            self.assertNotIn("--signer", tmpl, key)

    def test_networks_json_valid(self):
        data = json.loads(config.NETWORKS_FILE.read_text())
        for net in ("testnet", "devnet"):
            self.assertTrue(config.is_official(data[net]["rpc_ws"]))


if __name__ == "__main__":
    unittest.main()
