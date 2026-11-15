"""The reclaimed build filesystem, not the small root reserve, holds swap."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BUILDERS = ("Build Kernel OnePlus.yml", "build-kernel-original-make.yml")
BASH = os.environ.get("BAKASU_TEST_BASH", "bash")


class SwapWorkspaceTests(unittest.TestCase):
    def test_swap_succeeds_when_root_has_less_than_three_gigabytes(self):
        scripts = []
        for name in BUILDERS:
            workflow = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
            job = next(iter(workflow["jobs"].values()))
            step = next(s for s in job["steps"] if s.get("name") == "Create and Enable 3G Swap")
            scripts.append(step["run"])
            stubs = '''
sudo() {
    if [ "$1" = swapoff ]; then return 0; fi
    if [ "${@: -1}" != "$GITHUB_WORKSPACE/.build-swapfile" ]; then
        echo 'No space left on root filesystem' >&2
        return 73
    fi
    printf '%s\\n' "$1"
}
free() { return 0; }
'''
            with self.subTest(builder=name), tempfile.TemporaryDirectory(prefix="swap space ") as directory:
                result = subprocess.run([BASH, "-e", "-c", stubs + step["run"]],
                    env=dict(os.environ, GITHUB_WORKSPACE=Path(directory).as_posix()),
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["fallocate", "chmod", "mkswap", "swapon"])
        self.assertEqual(scripts[0], scripts[1])


if __name__ == "__main__":
    unittest.main()
