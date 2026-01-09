#!/bin/bash
set -e -o pipefail
. ~/.bashrc

export RCUTILS_CONSOLE_OUTPUT_FORMAT="{message}"
export RCUTILS_COLORIZED_OUTPUT=1

SSH_ADDRESS=unifi
# SSH_ADDRESS=pe1
# SSH_ADDRESS=pe2
SOURCE_DIR="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"/
DESTINATION_DIR="${SSH_ADDRESS}:~/raspberrypi_zenoh_redundant_mesh/"

rsync -av --checksum --progress --exclude='*cache*' --exclude='.*' --exclude='hero_workspace' --include='***' $SOURCE_DIR $DESTINATION_DIR
