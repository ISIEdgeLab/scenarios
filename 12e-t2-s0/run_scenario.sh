#!/usr/bin/env bash

source /proj/edgect/scenarios/scenario_functions.sh

# Available modules: general_viz rtp iperf
MODULES="general_viz iperf"

echo "Starting: ${MODULES}"
magi_run 12e-t2-s0 "${MODULES}" start

echo "Sleeping"
sleep 60

magi_run 12e-t2-s0 "${MODULES}" stop




