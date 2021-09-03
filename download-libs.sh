#!/bin/sh

set -ex

export ASSETS=snektalk/assets
rm -rf $ASSETS/lib
mkdir -p $ASSETS/lib

rm -rf node_modules
mkdir node_modules
npm install monaco-editor
cp -r node_modules/monaco-editor/min/vs/ $ASSETS/lib/vs/
rm -rf node_modules
rm package-lock.json

wget https://requirejs.org/docs/release/2.3.6/minified/require.js
mv require.js $ASSETS/lib/require.min.js

wget https://cdn.jsdelivr.net/npm/split-grid@1.0.9/dist/split-grid.min.js
mv split-grid.min.js $ASSETS/lib/split-grid.min.js

wget https://raw.githubusercontent.com/ccampbell/mousetrap/master/mousetrap.min.js
mv mousetrap.min.js $ASSETS/lib/mousetrap.min.js
