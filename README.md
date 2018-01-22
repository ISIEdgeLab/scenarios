## Scenarios

The purpose of scenarios is to reduce the effort required to configure EdgeLab

### Outline

The scenarios directory contains five custom scenarios. Within each of the scenarios directories

* 12e-t2-s0
* 12e-t2-s1
* 2e-t0-s1
* 6e-t1-s1
* 6e-t2-s1

There should be a `config.aal` and a `run_scenario.sh`.  *Note:* in `6e-t2-s1` the `run_scenario.sh` script is in `6e-t1-s1`.

The `config.aal` (agent animation list) contains a set of configuration settings used by [magi](http://docs.deterlab.net/orchestrator/orchestrator-guide/).

The `run_scenario.sh` script will then call magi to start and stop certain modules:

* click
* general_viz
* http
* iperf
* mgen
* rtp
* simple_reorder
* targeted_loss
* tcpdump1

on the nodes specified in the `config.aal` file.  The actions given in `run_scenario.sh` will use the action by the same name in the `AALS/` directory (these are generally named `start.aal` and `stop.aal` for starting and stopping services.  The `agents_and_groups.aal` and `scenario_functions.sh` are middleware that assists in allowing for easy to create scenarios.

There is also the `modify_click/` directory which contains a framework for modifying click in an easy manner.  The [README](https://github.com/ISIEdgeLab/scenarios/blob/adding-click-generics/modify_click/README) gives additional details on using modify_click.

### How to use Scenarios

1. Verify that MAGI is running on all nodes:  
    running: ```magi_status.py -e experiment_id -p project_id```  
    should return: ```01-22 10:07:20.908 root                           INFO     Received reply back from all the required nodes```  
2. ssh to your control node: (`control.experiment.project.isi.deterlab.net`)
3. `cd /proj/edgect/scenarios/{SCENARIO}`
4. `sudo ./run_scenario.sh`

Additional Notes are given on the [wiki](https://edgect.deterlab.net/wiki/ScenarioFramework)
