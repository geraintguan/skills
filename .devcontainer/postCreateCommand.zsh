#!/usr/bin/zsh

set -euxo pipefail

echo "Running in $(pwd)"

echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
mise activate zsh

mise settings add idiomatic_version_file_enable_tools node

mise trust -a
mise install
