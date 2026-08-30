"""Regression tests for Paramiko transport liveness detection."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from dpdispatcher.contexts.ssh_context import SSHSession


class TestSSHSessionLiveness(unittest.TestCase):
    """Ensure dead transports are never reported as healthy."""

    @staticmethod
    def _session(transport: MagicMock) -> SSHSession:
        session = SSHSession.__new__(SSHSession)
        session.ssh = MagicMock()
        session.ssh.get_transport.return_value = transport
        return session

    def test_inactive_transport_is_not_reported_alive(self) -> None:
        """An already inactive transport should trigger reconnection."""
        transport = MagicMock()
        transport.is_active.return_value = False

        session = self._session(transport)

        self.assertFalse(session._check_alive())
        transport.send_ignore.assert_not_called()

    def test_transport_dying_during_probe_is_not_reported_alive(self) -> None:
        """A transport that dies during the probe should be detected."""
        transport = MagicMock()
        transport.is_active.side_effect = [True, False]

        session = self._session(transport)

        self.assertFalse(session._check_alive())
        transport.send_ignore.assert_called_once_with()

    def test_active_transport_is_reported_alive(self) -> None:
        """An active transport that survives the probe remains healthy."""
        transport = MagicMock()
        transport.is_active.return_value = True

        session = self._session(transport)

        self.assertTrue(session._check_alive())
        transport.send_ignore.assert_called_once_with()
