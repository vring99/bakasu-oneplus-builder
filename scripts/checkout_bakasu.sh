#!/usr/bin/env bash
set -euo pipefail

pin=${1:?BakaSU commit required}
[[ $pin =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid BakaSU commit' >&2; exit 2; }
[[ ! -e KernelSU ]] || { echo 'KernelSU already exists' >&2; exit 2; }
[[ -n ${BAKASU_DEPLOY_KEY:-} ]] || { echo 'Missing BAKASU_DEPLOY_KEY' >&2; exit 2; }

umask 077
auth_dir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/bakasu-ssh.XXXXXXXX")
trap 'rm -f -- "$auth_dir/key" "$auth_dir/known_hosts" "$auth_dir/setup.sh"; rmdir -- "$auth_dir"' EXIT
printf '%s\n' "$BAKASU_DEPLOY_KEY" > "$auth_dir/key"
unset BAKASU_DEPLOY_KEY
printf '%s\n' 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' > "$auth_dir/known_hosts"
printf -v GIT_SSH_COMMAND 'ssh -F /dev/null -o BatchMode=yes -o IdentityAgent=none -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o HostKeyAlgorithms=ssh-ed25519 -o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=%q -i %q' \
    "$auth_dir/known_hosts" "$auth_dir/key"
export GIT_SSH_COMMAND GIT_TERMINAL_PROMPT=0

git clone --branch codex/build-35233 --single-branch git@github.com:vring99/BakaSU.git KernelSU
git -C KernelSU merge-base --is-ancestor "$pin" HEAD
git -C KernelSU show "$pin:kernel/setup.sh" > "$auth_dir/setup.sh"
bash "$auth_dir/setup.sh" "$pin"
[[ $(git -C KernelSU rev-parse HEAD) == "$pin" ]] || {
    echo 'BakaSU checkout does not match the pinned commit' >&2
    exit 1
}
printf 'BakaSU checkout verified: %s\n' "$pin"
