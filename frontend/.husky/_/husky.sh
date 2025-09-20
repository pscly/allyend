#!/usr/bin/env sh
if [ -z "$husky_skip_init" ]; then
  if [ "$HUSKY" = "0" ]; then
    return
  fi
  . "$(dirname "$0")/husky.sh"
fi

