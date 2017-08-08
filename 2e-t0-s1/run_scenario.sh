source /proj/edgect/scenarios/scenario_functions.sh

# Available modules: rtp iperf targeted_loss simple_reorder tcpdump1
TRAFFIC="rtp"
IMPAIRMENT="simple_reorder"

# Start a tcpdump.
echo "Starting tcpdump"
magi_run 2e-t0-s1 tcpdump1 start

# Start some traffic.
echo "Starting: ${TRAFFIC}"
magi_run 2e-t0-s1 "${TRAFFIC}" start

echo "Traffic started. Sleeping."
sleep 30

# Create an impairment.
echo "Starting impairment"
magi_run 2e-t0-s1 "${IMPAIRMENT}" start 

echo "Sleeping"
sleep 60

echo "Stopping impairment"
magi_run 2e-t0-s1 "${IMPAIRMENT}" stop

echo "Sleeping"
sleep 30

magi_run 2e-t0-s1 "${TRAFFIC}" stop
