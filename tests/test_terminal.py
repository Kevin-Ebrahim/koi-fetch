"""Exercise the CLI in a real pseudo-terminal on POSIX systems."""

import os
from pathlib import Path
import select
import signal
import struct
import sys
import tempfile
import time
import unittest

if os.name != 'nt':
    import fcntl
    import pty
    import termios


@unittest.skipIf(os.name == 'nt', 'POSIX pseudo-terminal test')
class TerminalTests(unittest.TestCase):
    def run_terminal(self, args, with_fastfetch):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            if with_fastfetch:
                binary = root / 'fastfetch'
                binary.write_text(f'#!{sys.executable}\nprint("USER_CONFIG_MODULE")\n')
                binary.chmod(0o755)
            pid, fd = pty.fork()
            if pid == 0:
                os.environ['PATH'] = directory
                os.environ['HOME'] = directory
                os.environ['TERM'] = 'xterm-256color'
                os.execv(sys.executable, [sys.executable, '-m', 'koi_fetch', *args])

            def resize(rows, columns):
                fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))

            def read_for(seconds):
                output = b''
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    if select.select([fd], [], [], .1)[0]:
                        try:
                            output += os.read(fd, 131072)
                        except OSError:
                            break
                return output

            try:
                resize(24, 80)
                output = read_for(1.3)
                self.assertIn(b'\x1b[1;1H', output)
                self.assertIn(b'\x1b[24;1H', output)
                self.assertNotIn(b'Make the terminal', output)
                if with_fastfetch:
                    self.assertIn(b'USER_CONFIG_MODULE', output)
                else:
                    self.assertNotIn(b'USER_CONFIG_MODULE', output)
                resize(10, 30)
                os.kill(pid, signal.SIGWINCH)
                output += read_for(.5)
                self.assertIn(b'\x1b[10;1H', output)
                os.write(fd, b'\x03')
                output += read_for(.5)
                _, status = os.waitpid(pid, 0)
                pid = None
                self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                self.assertIn(b'\x1b[?1049l', output)
                self.assertIn(b'\x1b[?25h', output)
            finally:
                if pid is not None:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                os.close(fd)

    def test_fetch_fits_standard_terminal(self):
        self.run_terminal([], True)

    def test_fullscreen_without_fastfetch_or_omarchy(self):
        self.run_terminal(['--fullscreen'], False)
