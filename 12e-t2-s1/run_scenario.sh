source /proj/edgect/scenarios/scenario_functions.sh

# Available traffic modules: rtp iperf targeted_loss simple_reorder
TRAFFIC="iperf targeted_loss simple_reorder"

# Available impairments: targeted_loss simple_reorder
IMPAIRMENT="targeted_loss simple_reorder"

echo "Starting: ${TRAFFIC}"
magi_run 12e-t2-s1 "${TRAFFIC}" start

echo "Sleeping"
sleep 30

echo "Starting: ${IMPAIRMENT}"
magi_run 12e-t2-s1 "${IMPAIRMENT}" start

echo "Sleeping"
sleep 60

magi_run 12e-t2-s1 "${IMPAIRMENT}" stop
magi_run 12e-t2-s1 "${TRAFFIC}" stop
