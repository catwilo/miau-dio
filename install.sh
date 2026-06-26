#!/usr/bin/env bash
# miau-dio installer: no pip, no external deps. Generates a launcher and
# installs the audio backends from bundled assets.
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"

# 1. Generate the launcher pointing at this repo.
cat > "$BIN/miau-dio" << LAUNCHER
#!/usr/bin/env bash
export PYTHONPATH="$REPO\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m miau_dio "\$@"
LAUNCHER
chmod +x "$BIN/miau-dio"
echo "launcher installed: $BIN/miau-dio"

# 2. Warn if ~/.local/bin is not on PATH.
case ":$PATH:" in
    *":$BIN:"*) ;;
    *) echo "NOTE: add $BIN to your PATH to use 'miau-dio' directly." ;;
esac

# 3. Install audio backends from bundled assets (compiles abc2midi, etc).
echo "installing backends (this may ask for sudo on Debian)..."
"$BIN/miau-dio" setup --profile playback

echo "done. try: miau-dio new \"my first idea\""
