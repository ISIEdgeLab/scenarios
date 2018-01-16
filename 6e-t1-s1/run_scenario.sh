#!/usr/bin/env bash

source /proj/edgect/scenarios/scenario_functions.sh

MODULES="general_viz click rtp"
echo "Starting: ${MODULES}"
magi_run 6e-t1-s1 "${MODULES}" start

echo "Sleeping"
sleep 300

magi_run 6e-t1-s1 "click" start_flap

sleep 300

magi_run 6e-t1-s1 "${MODULES}" stop





