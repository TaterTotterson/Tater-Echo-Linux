import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


LIB = Path(__file__).resolve().parent / "linux" / "techo5-lib.sh"


class Prefer5Test(unittest.TestCase):
    def run_prefer5(self, frequency, signal):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / "bin"
            binaries.mkdir()
            calls = root / "wpa-calls"
            state = root / "state"

            self.write_command(
                binaries / "iw",
                """
                cat <<EOF
                Connected to 00:11:22:33:44:55
                \tfreq: $TEST_FREQUENCY
                \tsignal: $TEST_SIGNAL dBm
                EOF
                """,
            )
            self.write_command(
                binaries / "wpa_cli",
                """
                while [ "$#" -gt 0 ]; do
                    case "$1" in
                        -p|-i) shift 2 ;;
                        *) break ;;
                    esac
                done
                command=$1
                shift || true
                printf '%s %s\n' "$command" "$*" >> "$TATER_TEST_CALLS"
                case "$command" in
                    list_networks)
                        printf 'network id\tssid\tbssid\tflags\n0\tTestNet\tany\t[CURRENT]\n'
                        ;;
                    status)
                        printf 'ssid=TestNet\nwpa_state=COMPLETED\n'
                        ;;
                    scan_results)
                        printf 'bssid / frequency / signal level / flags / ssid\n'
                        printf '00:11:22:33:44:66\t5240\t-40\t[WPA2-PSK-CCMP][ESS]\tTestNet\n'
                        printf '00:11:22:33:44:55\t2437\t%s\t[WPA2-PSK-CCMP][ESS]\tTestNet\n' "$TEST_SIGNAL"
                        ;;
                esac
                """,
            )
            self.write_command(binaries / "sleep", ":")
            self.write_command(
                binaries / "cut",
                """
                case "$*" in
                    */proc/uptime*) echo 1000 ;;
                    *) exec /usr/bin/cut "$@" ;;
                esac
                """,
            )

            script = textwrap.dedent(
                f"""
                set -eu
                log() {{ :; }}
                . {self.shell_quote(str(LIB))}
                T5_PREFER5_RUNTIME_DIR={self.shell_quote(str(state))}
                export T5_PREFER5_RUNTIME_DIR
                t5_wifi_prefer5
                """
            )
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": str(binaries) + os.pathsep + environment["PATH"],
                    "TATER_TEST_CALLS": str(calls),
                    "TEST_FREQUENCY": str(frequency),
                    "TEST_SIGNAL": str(signal),
                }
            )
            subprocess.run(["/bin/sh", "-c", script], check=True, env=environment)
            return calls.read_text() if calls.exists() else ""

    @staticmethod
    def write_command(path, body):
        path.write_text("#!/bin/sh\n" + textwrap.dedent(body).lstrip())
        path.chmod(0o755)

    @staticmethod
    def shell_quote(value):
        return "'" + value.replace("'", "'\\''") + "'"

    def test_healthy_2g_link_is_not_disturbed(self):
        self.assertEqual("", self.run_prefer5(2437, -55))

    def test_weak_2g_link_can_still_try_strong_5g(self):
        calls = self.run_prefer5(2437, -75)
        self.assertIn("set_network 0 freq_list 5240", calls)
        self.assertGreaterEqual(calls.count("reassociate "), 2)


if __name__ == "__main__":
    unittest.main()
