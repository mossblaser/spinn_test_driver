#!/usr/bin/env python

"""
A simple random connectivity experiment.
"""

import random

import spinn_route.model
import spinn_route.routers

from spinn_test_driver import network_experiment
from spinn_test_driver import result_dump

# Use a 2x2 network of SpiNNaker chips (Without the monitor cores)
chips = spinn_route.model.make_rectangular_board(2,2)
for chip in chips.itervalues():
	del chip.cores[0]
experiment = network_experiment.NetworkExperiment(chips)

# Select the set of routing algorithms to use for all connections
routing_algorithms = [spinn_route.routers.dimension_order_route]

# Get a list of all non-monitor cores in the system
all_cores = sum((chip.cores.values() for chip in experiment.chips.itervalues()), [])

# Create random connections from some cores
num_potential_sources_per_core = 5
source_probability     = 1.0
connection_probability = 0.1
sources = 0
dests = 0
for source_core in all_cores:
	for _ in range(num_potential_sources_per_core):
		if random.random() < source_probability:
			# Select some random destinations
			dest_cores = [c for c in all_cores if random.random() < connection_probability]
			
			# Generate a packet with a 50% probability
			gen = network_experiment.BernoulliGeneration(0.1)
			
			# Consume packets as quickly as possible
			con = network_experiment.InstantConsumption()
			
			# Add the stream
			experiment.add_stream( (source_core, gen)
			                     , zip(dest_cores, [con]*len(dest_cores))
			                     , routing_algorithms
			                     )
			sources += 1
			dests   += len(dest_cores)

if sources != 0:
	fanout = float(dests)/float(sources)
else:
	fanout = 0.0


# Set the period between ticks
experiment.tick_period = 0.001

# Set the router timeout
experiment.router_timeout = 512

# Experiment runtime
experiment.warmup   = 1.0
experiment.duration = 1.0

# Run the experiment
results = experiment.run("192.168.240.7")

# Generate some basic stats
print result_dump.global_results([], [(results,)])

