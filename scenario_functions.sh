#!/usr/bin/env bash

### DEFAULTS ###
# Topdir
TOPDIR=/users/gbartlet/edgect/github/scenarios

# The place to look for overrides if env SCENARIO_OVERRIDES is undefined.
if [ x = x${SCENARIO_OVERRIDES} ]; then
	SCENARIO_OVERRIDES=${HOME}/.edgect_scenarios/
else
	echo "Will look for scenario overrides in ${SCENARIO_OVERRIDES}."
fi
if [[ -e ${SCENARIO_OVERRIDES} ]]; then
	if [[ ! -d ${SCENARIO_OVERRIDES} ]]; then
		echo "Scenario overrides (${SCENARIO_OVERRIDES}) is not a directory. Ignoring overrides."
		# XXX Hack to essentially set scenario overrides to none.
		SCENARIO_OVERRIDES="/"
	fi
else
	mkdir -p ${SCENARIO_OVERRIDES}
fi

if [ x = x${MAGI_CONTROL} ]; then
	MAGI_CONTROL="localhost"
fi

# Default agents_and_groups.aal file
if [[ -f ${SCENARIO_OVERRIDES}/agents_and_groups.aal ]]; then
	echo "Using override for agents_and_groups.aal file." 
	AGENTS_AND_GROUPS_AAL=${SCENARIO_OVERRIDES}/agents_and_groups.aal
else
	AGENTS_AND_GROUPS_AAL=${TOPDIR}/agents_and_groups.aal
fi

# Default magi orchestrator to use.
MAGI=`which magi_orchestrator.py`
#MAGI=/proj/edgect/magi/current/magi_orchestrator.py
if [ x = x${MAGI} ]; then
	echo "ERROR: No magi_orchestrator.py found. Is Magi installed?"
	exit	
fi

# Default path to config, start, stop AAL scripts
# In this directory, we look for a directory which shares the module name. In this directory we expect 
# two (config, start) or possibly three scripts (config, start, stop).
# For now we're not doing overrides for these files.
AAL_MODULE_SCRIPTS=${TOPDIR}/AALS/

### FUNCTIONS ###
# Given scenario name, get (full path) scenario AAL config. There may be overrides.
function scenario_config {
	if [ "$#" -ne 1 ]; then
		echo "ERROR: Did not get scenario name."
		return ""
	fi
	if [[ -f ${SCENARIO_OVERRIDES}/$1/config.aal ]]; then
		return ${SCENARIO_OVERRIDES}/$1/config.aal
	fi
	if [[ -f ${TOPDIR}/$1/config.aal ]]; then
		return ${TOPDIR}/$1/config.aal
	fi
	echo "ERROR: Did not find config.aal for scenario $1"
	return ""
}

# Get list of traffic generation modules available for this scenario.
# For now, this is parsed from a hand-written file. 

# Test if a given traffic generation module is available in this scenario.

# Create the appropriate event streams AAL file to call.
function magi_run {
	if [ "$#" -ne 3 ]; then
		echo "ERROR: Did not get all arguments needed to run magi command"
		exit
	fi

	echo "Scenario: $1"
	echo "Modules: $2"
	echo "Action: $3"
	action=$3
	
	tmp_eventstream_file=$(mktemp /tmp/event_stream_${action}.XXXXXX)
	
	# Get the files and the event streams
	aals=""
	event_streams=""
	for module in $2; do
		if [[ -f ${AAL_MODULE_SCRIPTS}/${module}/${action}.aal ]]; then
			aals="${aals} -f ${AAL_MODULE_SCRIPTS}/${module}/${action}.aal "	
			event_streams="${event_streams}, ${module}_${action}"
		else
			echo "WARN: Did not find an AAL file for ${module}/${action}.aal in ${AAL_MODULE_SCRIPTS}"
		fi
	done
	event_streams=`echo ${event_streams} | sed 's/, //'`
	echo "streamstarts:  [${event_streams}]" > $tmp_eventstream_file
	echo "eventstreams:" >> $tmp_eventstream_file
	echo Event streams: $event_streams
	#echo AAL Files: ${aals}
	
	if [[ -f ${SCENARIO_OVERRIDES}/${1}/config.aal ]]; then
		echo "Using override for ${1}/config.aal file."
		SCENARIO_CONFIG=${SCENARIO_OVERRIDES}/${1}/config.aal
	else
		SCENARIO_CONFIG=${TOPDIR}/${1}/config.aal
	fi
	if [[ ! -f ${SCENARIO_CONFIG} ]]; then
		echo "Could not find configuration for scenario ${1}"
		exit
	fi

	echo $MAGI -c ${MAGI_CONTROL} -f ${SCENARIO_CONFIG} -f ${AGENTS_AND_GROUPS_AAL} -f $tmp_eventstream_file ${aals}
	$MAGI -c ${MAGI_CONTROL} -f ${SCENARIO_CONFIG} -f ${AGENTS_AND_GROUPS_AAL} -f $tmp_eventstream_file ${aals}
	#rm $tmp_eventstream_file
}
