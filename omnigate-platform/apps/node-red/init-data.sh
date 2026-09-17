#!/bin/sh
set -eu

DATA_DIR=${NODE_RED_DATA_DIR:-/data}
DEFAULTS_DIR=${NODE_RED_DEFAULTS_DIR:-/opt/omnigate-defaults}
NODE_RED_BIN=${NODE_RED_BIN:-node-red}

seed_file()
{
    source=$1
    target=$2
    if [ ! -e "$target" ]; then
        temporary="${target}.seed.$$"
        cp "$source" "$temporary"
        chmod 0600 "$temporary"
        mv "$temporary" "$target"
    fi
}

mkdir -p "$DATA_DIR"
seed_file "$DEFAULTS_DIR/settings.js" "$DATA_DIR/settings.js"
seed_file "$DEFAULTS_DIR/flows.json" "$DATA_DIR/flows.json"

# /data is the writable named volume.  Defaults are copied only on first boot;
# subsequent editor deployments and credential updates survive restarts.
exec "$NODE_RED_BIN" --userDir "$DATA_DIR" --settings "$DATA_DIR/settings.js" "$DATA_DIR/flows.json"
