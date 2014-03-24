#!/usr/bin/env python

"""
A simple random connectivity experiment.
"""

import random

import spinn_route.model
import spinn_route.routers

from spinn_test_driver import network_experiment

# Use a 2x2 network of SpiNNaker chips (Without the monitor cores)
chips = spinn_route.model.make_rectangular_board(2,2)
for chip in chips.itervalues():
	del chip.cores[0]
experiment = network_experiment.NetworkExperiment(chips)

# Select the set of routing algorithms to use for all connections
routing_algorithms = [spinn_route.routers.dimension_order_route]

# Get a list of all non-monitor cores in the system
all_cores = sum((chip.cores.values() for chip in experiment.chips.itervalues()), [])

## Create random connections from some cores
#num_potential_sources_per_core = 1
#source_probability     = 0.5
#connection_probability = 0.0
#for source_core in all_cores:
#	for _ in range(num_potential_sources_per_core):
#		if random.random() < source_probability:
#			# Select some random destinations
#			dest_cores = [c for c in all_cores if random.random() < connection_probability]
#			
#			# Generate a packet with a 50% probability
#			gen = network_experiment.BernoulliGeneration(1.0)
#			
#			# Consume packets as quickly as possible
#			con = network_experiment.InstantConsumption()
#			
#			# Add the stream
#			experiment.add_stream( (source_core, gen)
#			                     , zip(dest_cores, [con]*len(dest_cores))
#			                     , routing_algorithms
#			                     )

# Create connections from every core to the corresponding core in every chip
sources = 0
dests   = 0
for chip in chips.itervalues():
	for core_id, source_core in chip.cores.iteritems():
		# Select every other core
		dest_cores = sum((c.cores.values() for c in chips.itervalues()), [])
		
		gen = network_experiment.BernoulliGeneration(0.10)
		con = network_experiment.InstantConsumption()
		
		# Add the stream
		sources += 1
		dests   += len(dest_cores)
		experiment.add_stream( (source_core, gen)
		                     , zip(dest_cores, [con]*len(dest_cores))
		                     , routing_algorithms
		                     )

fanout = float(dests)/float(sources)


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
total_dropped   = sum(chip.router.dropped_packets   for chip in results.itervalues())
total_forwarded = sum(chip.router.forwarded_packets for chip in results.itervalues())

total_generated = sum(sum(sum(source.packets_generated for source in core.sources.itervalues())
                          for core in chip.cores.itervalues())
                      for chip in results.itervalues())
total_sent      = sum(sum(sum(source.packets_sent for source in core.sources.itervalues())
                          for core in chip.cores.itervalues())
                      for chip in results.itervalues())

total_arrived   = sum(sum(sum(sink.packets_arrived for sink in core.sinks.itervalues())
                          for core in chip.cores.itervalues())
                      for chip in results.itervalues())

print "Total dropped:  ", total_dropped
print "Total forwarded:", total_forwarded
print "Total generated:", total_generated
print "Total sent:     ", total_sent
print "Total arrived:  ", total_arrived
print
print "Intended Fanout:", fanout
print "Actual Fanout:  ", float(total_arrived)/float(total_sent)
