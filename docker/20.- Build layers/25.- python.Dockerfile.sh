#!/bin/bash
set -e


# Upgrade system
PACKAGES=()
PACKAGES+=(d2dcn)
PACKAGES+=(opencv-python==4.9.0.80)


# Install all
pip3 install ${PACKAGES[@]}
