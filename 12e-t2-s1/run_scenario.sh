source /proj/edgect/scenarios/scenario_functions.sh

# Available traffic modules: rtp iperf targeted_loss simple_reorder
TRAFFIC="iperf"

# Available impairments: targeted_loss simple_reorder
IMPAIRMENT="targeted_loss simple_reorder"

echo "Starting hooks for visulization. See https://edgect.deterlab.net/wiki/VisualizationHowTo"
magi_run 12e-t2-s1 "general_viz" start

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
magi_run 12e-t2-s1 "general_viz" stop
