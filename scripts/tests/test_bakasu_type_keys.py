"""Keep external SUSFS repair scoped to the selected native Pro release."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows"
GKI = (WF / "build.yml").exists()
BUILDERS = ("build.yml", "build-make.yml") if GKI else (
    "Build Kernel OnePlus.yml", "build-kernel-original-make.yml")
BASH = os.environ.get("BAKASU_TEST_BASH", "bash")


def steps(name):
    workflow = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    return next(iter(workflow["jobs"].values()))["steps"]


class NativeTypeKeysWorkflowTests(unittest.TestCase):
    def test_version_feature_gate_and_order(self):
        for name in BUILDERS:
            source = steps(name)
            index = next(i for i, step in enumerate(source)
                         if step.get("id") == "bakasu_susfs_type_keys")
            step = source[index]
            expected = ("inputs.ksu_variant == 'BakaSU Pro' && "
                        "inputs.bakasu_version == '35285' && inputs.enable_susfs") if GKI else (
                        "inputs.BAKASU_VERSION == '35285' && env.KERNEL_VERSION != '6.18'")
            self.assertEqual(step["if"], expected, name)
            before = "\n".join(s.get("run", "") for s in source[:index])
            self.assertIn("checkout does not match pinned commit", before)
            self.assertIn("kernel_patches/fs/*", before)
            self.assertTrue(any(s.get("id") == "bakasu_susfs_setup" for s in source[:index]))
            self.assertTrue(any("Build Kernel" in s.get("name", "") or
                                s.get("id") == "android17_build" for s in source[index + 1:]))

    def test_repair_uses_only_pinned_native_script_and_external_file(self):
        for name in BUILDERS:
            step = next(s for s in steps(name) if s.get("id") == "bakasu_susfs_type_keys")
            run = step["run"]
            self.assertEqual(run.count('python3 "$KSU_SOURCE/scripts/susfs_type_keys.py"'), 2)
            self.assertIn('/common/fs/susfs.c" --check', run)
            for forbidden in ("security/selinux", "|| true", "curl ", "cp ", "sed ", "git apply"):
                self.assertNotIn(forbidden, run)
            result = subprocess.run([BASH, "-n", "-c", run], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_script_status_propagates_and_check_is_required(self):
        stub = '''
python3() {
    printf '%s\\n' "$*" >> "$TEST_CALLS"
    case "$*" in
        *--check) return "$TEST_CHECK_STATUS" ;;
        *) return "$TEST_APPLY_STATUS" ;;
    esac
}
'''
        for name in BUILDERS:
            run = next(s["run"] for s in steps(name) if s.get("id") == "bakasu_susfs_type_keys")
            for apply, check in ((0, 0), (9, 0), (0, 7)):
                with self.subTest(builder=name, apply=apply, check=check), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    platform = root if GKI else root / "kernel_workspace/kernel_platform"
                    config = platform / "common/arch/arm64/configs/gki_defconfig"
                    config.parent.mkdir(parents=True)
                    config.write_text("CONFIG_KSU_SUSFS=y\n", encoding="utf-8")
                    calls = root / "calls"
                    env = dict(os.environ, KERNEL_ROOT=root.as_posix(), GITHUB_WORKSPACE=root.as_posix(),
                               TEST_CALLS=calls.as_posix(), TEST_APPLY_STATUS=str(apply),
                               TEST_CHECK_STATUS=str(check))
                    result = subprocess.run([BASH, "-e", "-c", stub + run], env=env,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, apply or check, result.stdout + result.stderr)
                    actual = calls.read_text().splitlines()
                    self.assertEqual(len(actual), 1 if apply else 2)
                    expected = f"{platform.as_posix()}/KernelSU/scripts/susfs_type_keys.py --file {platform.as_posix()}/common/fs/susfs.c"
                    self.assertEqual(actual[0], expected)
                    if not apply:
                        self.assertEqual(actual[1], expected + " --check")

    @unittest.skipIf(GKI, "GKI has an explicit workflow SUSFS gate")
    def test_disabled_susfs_does_not_invoke_native_script(self):
        for name in BUILDERS:
            run = next(s["run"] for s in steps(name) if s.get("id") == "bakasu_susfs_type_keys")
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root / "kernel_workspace/kernel_platform/common/arch/arm64/configs/gki_defconfig"
                config.parent.mkdir(parents=True)
                config.write_text("# CONFIG_KSU_SUSFS is not set\n", encoding="utf-8")
                result = subprocess.run([BASH, "-e", "-c", 'python3() { return 99; }\n' + run],
                                        env=dict(os.environ, GITHUB_WORKSPACE=root.as_posix()),
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("SUSFS_TYPE_KEYS=disabled", result.stdout)
