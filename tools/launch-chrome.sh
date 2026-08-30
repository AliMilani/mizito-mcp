#!/usr/bin/env bash
# Launch an ISOLATED Chrome (separate profile) with CDP open on 9333.
# Does not touch your everyday Chrome profile or its cookies.
PROFILE="${MIZITO_CHROME_PROFILE:-$HOME/.cache/mizito-mcp/chrome-profile}"
mkdir -p "$PROFILE"

# GNOME/Wayland session: Xwayland needs mutter's own xauth cookie.
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${XAUTHORITY:-}" ]; then
  XAUTHORITY="$(ls -t "$XDG_RUNTIME_DIR"/.mutter-Xwaylandauth.* 2>/dev/null | head -1)"
  [ -n "$XAUTHORITY" ] && export XAUTHORITY
fi

exec "${CHROME:-google-chrome}" \
  --user-data-dir="$PROFILE" \
  --remote-debugging-port=9333 \
  --remote-allow-origins=http://127.0.0.1:9333 \
  --no-first-run --no-default-browser-check \
  --disable-features=Translate,OptimizationHints \
  --window-size=1500,950 \
  "https://office.mizito.ir/#/ws/projects/all"
