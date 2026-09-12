#!/usr/bin/env bash
# miau-dio installer: symlink the launcher, then install audio backends.
#
# PHILOSOPHY (toolkit standard): SYMLINK, never copy. The installed
# `miau-dio` is a symlink to bin/miau-dio in this repo; a `git pull`
# updates it with no reinstall. Backends (abc2midi, timidity, sox) are
# external binaries handled by `miau-dio setup`, unaffected by this.
#
# Usage:
#   bash install.sh          install/update
#   bash install.sh verify   verify only (no changes)

set -euo pipefail

_self="$0"
case "$_self" in */*) ;; *) _self="$(command -v "$_self")" ;; esac
if _real="$(readlink -f "$_self" 2>/dev/null)" && [ -n "$_real" ]; then
    _self="$_real"
else
    while [ -L "$_self" ]; do
        _link="$(readlink "$_self")"
        case "$_link" in /*) _self="$_link" ;; *) _self="$(dirname "$_self")/$_link" ;; esac
    done
fi
REPO="$(cd "$(dirname "$_self")" && pwd -P)"
LAUNCHER="$REPO/bin/miau-dio"

[ -f "$LAUNCHER" ] || { echo "[ERROR] launcher not found: $LAUNCHER" >&2; exit 1; }
[ -x "$LAUNCHER" ] || chmod +x "$LAUNCHER"

if [ -n "${PREFIX:-}" ] && [ -d "${PREFIX}/bin" ]; then
    BINDIR="${PREFIX}/bin"
elif [ -d "$HOME/.local/bin" ] || mkdir -p "$HOME/.local/bin" 2>/dev/null; then
    BINDIR="$HOME/.local/bin"
else
    echo "[ERROR] no writable bin dir found" >&2
    exit 1
fi

if [ "${1:-}" = verify ]; then
    found="$(command -v miau-dio 2>/dev/null || true)"
    [ -n "$found" ] || { echo "[WARN] miau-dio not in PATH" >&2; exit 1; }
    [ -L "$found" ] || { echo "[WARN] miau-dio is not a symlink -> $found" >&2; exit 1; }
    [ "$(readlink -f "$found")" = "$LAUNCHER" ] || { echo "[WARN] wrong target -> $found" >&2; exit 1; }
    echo "[OK]    miau-dio -> $found"
    exit 0
fi

ln -sfn "$LAUNCHER" "$BINDIR/miau-dio"
echo "[OK]    linked $BINDIR/miau-dio -> $LAUNCHER"

# Clear a stale copy in ~/.local/bin when BINDIR is elsewhere.
if [ "$BINDIR" != "$HOME/.local/bin" ] && [ -e "$HOME/.local/bin/miau-dio" ] && [ ! -L "$HOME/.local/bin/miau-dio" ]; then
    rm -f "$HOME/.local/bin/miau-dio"
    echo "[OK]    removed stale copy $HOME/.local/bin/miau-dio"
fi

case ":$PATH:" in
    *":$BINDIR:"*) ;;
    *) echo "[WARN]  add $BINDIR to your PATH to use 'miau-dio'" >&2 ;;
esac

echo "installing backends (may ask for sudo on Debian)..."
"$BINDIR/miau-dio" setup --profile playback

echo "done. try: miau-dio new \"my first idea\""
