source ../scenario_functions.sh

MODULES="general_viz rtp iperf"

echo "Starting: ${MODULES}"
magi_run 6e-t1-s1 "${MODULES}" start

echo "Sleeping"
sleep 60

magi_run 6e-t1-s1 "${MODULES}" stop




