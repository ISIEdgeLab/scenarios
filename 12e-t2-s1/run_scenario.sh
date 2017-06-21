source ../scenario_functions.sh

# Available modules: rtp iperf targeted_loss simple_reorder
MODULES="iperf targeted_loss simple_reorder"

echo "Starting: ${MODULES}"
magi_run 12e-t2-s1 "${MODULES}" start

echo "Sleeping"
sleep 60

magi_run 12e-t2-s1 "${MODULES}" stop
