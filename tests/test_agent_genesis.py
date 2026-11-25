"""Regression tests for refusing setup on an unverified chain."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flopaz import agent, rpc  # noqa: E402


class AgentGenesisGateTest(unittest.TestCase):
    def test_setup_stops_before_cli_and_agent_side_effects(self):
        network = {"label": "Testnet"}
        with (
            patch.object(agent.config, "network", return_value=network),
            patch.object(agent.ui, "step"),
            patch.object(agent.ui, "info"),
            patch.object(agent.ui, "err") as error,
            patch.object(agent, "_prereqs", return_value=True),
            patch.object(agent.rpc, "verify_genesis", return_value=False) as verify,
            patch.object(agent, "_cli") as cli,
            patch.object(agent, "load_state") as load_state,
            patch.object(agent, "_keystore") as keystore,
            patch.object(agent, "_faucet") as faucet,
            patch.object(agent, "_limits") as limits,
            patch.object(agent, "_install_hermes") as install_hermes,
        ):
            agent.setup("testnet")

        verify.assert_called_once_with(network, "testnet")
        error.assert_called_once()
        cli.assert_not_called()
        load_state.assert_not_called()
        keystore.assert_not_called()
        faucet.assert_not_called()
        limits.assert_not_called()
        install_hermes.assert_not_called()


class RpcGenesisVerificationTest(unittest.TestCase):
    EXPECTED = "0x" + "ab" * 32
    NETWORK = {"expected_genesis": EXPECTED, "verified": True}

    def test_unreachable_rpc_fails_verification(self):
        with (
            patch.object(rpc, "call", side_effect=rpc.RpcError("offline")),
            patch.object(rpc.ui, "allow_public_hash"),
            patch.object(rpc.ui, "err"),
        ):
            self.assertFalse(rpc.verify_genesis(self.NETWORK, "testnet"))

    def test_genesis_mismatch_fails_verification(self):
        live = "0x" + "cd" * 32
        with (
            patch.object(rpc, "call", return_value=live),
            patch.object(rpc.ui, "allow_public_hash"),
            patch.object(rpc.ui, "err"),
        ):
            self.assertFalse(rpc.verify_genesis(self.NETWORK, "testnet"))

    def test_matching_genesis_passes_verification(self):
        with (
            patch.object(rpc, "call", return_value=self.EXPECTED),
            patch.object(rpc.ui, "allow_public_hash"),
            patch.object(rpc.ui, "ok"),
        ):
            self.assertTrue(rpc.verify_genesis(self.NETWORK, "testnet"))


if __name__ == "__main__":
    unittest.main()
