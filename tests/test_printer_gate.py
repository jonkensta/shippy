"""Tests for the wait-for-a-label-printer gate."""

import unittest

from shippy import printer_gate


class FakeConsole:
    """Records what the gate would have printed."""

    def __init__(self):
        self.lines = []

    def __call__(self, text="", **_kwargs):
        self.lines.append(text)


def scripted(values):
    """A callable returning the given values in order, then the last forever."""
    values = list(values)

    def call(*_args):
        return values.pop(0) if len(values) > 1 else values[0]

    return call


class WaitForPrinterTests(unittest.TestCase):
    """wait_for_printer()."""

    def test_printer_already_ready_is_silent(self):
        say = FakeConsole()
        ready = printer_gate.wait_for_printer(
            find_printers=lambda: ["BOB"],
            wait_for_continue=lambda _t: self.fail("should not wait"),
            say=say,
        )
        self.assertTrue(ready)
        self.assertEqual(say.lines, [])

    def test_continues_by_itself_when_printer_appears(self):
        say = FakeConsole()
        waits = []

        def wait(timeout_s):
            waits.append(timeout_s)
            return False

        ready = printer_gate.wait_for_printer(
            find_printers=scripted([[], [], ["BETTY"]]),
            wait_for_continue=wait,
            say=say,
            interval_s=2.0,
        )
        self.assertTrue(ready)
        self.assertEqual(waits, [2.0, 2.0])
        self.assertTrue(any("NO LABEL PRINTER FOUND" in line for line in say.lines))
        self.assertIn("Label printer ready: BETTY", say.lines[-1])

    def test_enter_continues_without_printer(self):
        say = FakeConsole()
        ready = printer_gate.wait_for_printer(
            find_printers=lambda: [],
            wait_for_continue=scripted([False, True]),
            say=say,
        )
        self.assertFalse(ready)
        self.assertIn("Continuing without a label printer", say.lines[-1])
        self.assertTrue(any("to-print" in line for line in say.lines))

    def test_ctrl_c_propagates(self):
        def interrupt(_timeout_s):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            printer_gate.wait_for_printer(
                find_printers=lambda: [],
                wait_for_continue=interrupt,
                say=FakeConsole(),
            )


class UsablePrinterNamesTests(unittest.TestCase):
    """usable_printer_names()."""

    def test_discovery_failure_counts_as_no_printer(self):
        original = printer_gate.discover

        def broken():
            raise OSError("WMI unavailable")

        printer_gate.discover = broken
        try:
            with self.assertLogs(printer_gate.logger.name, "ERROR"):
                self.assertEqual(printer_gate.usable_printer_names(), [])
        finally:
            printer_gate.discover = original


if __name__ == "__main__":
    unittest.main()
