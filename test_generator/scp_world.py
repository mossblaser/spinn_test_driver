#!/usr/bin/env python
"""
Test of using the pacman103 SCP library to load/run the experiment.
"""

import pacman103.scp as scp
import time


# Connect to SpiNNaker
conn = scp.SCPConnection("192.168.240.7")
print "Connected to board with software '%s'"%(conn.version().desc)

# Get the types for the config structs
from spinn_test_driver_structs import *

# Routing table generation
from spinn_route import model, routers, table_gen


# A 2x2 chip board
chips = model.make_rectangular_board(2,2)
# Remove monitor cores
for router, cores in chips.itervalues():
	del cores[0]

# Connect from (0,0,1) to all (non-monitor) cores on every chip.
routing_key = 0xDEADBEEF
routes, unrouted_sinks = routers.dimension_order_route(
	chips[(0,0)][1][1],
	sum((c[1] for c in chips.itervalues()), []),
	chips
)

# Since our network doesn't have any faults, this should work perfectly
assert(len(unrouted_sinks) == 0)

# Add the routes to the routers
route = model.Route(routing_key)
for node_sequence in routes:
	model.add_route(route, node_sequence)


load_ybug_commands = ""
dump_ybug_commands = ""


# Configuration data blobs with keys (x,y,core)
configs = {}

warmup   = 2.0
duration = 3.0
tick_period = 1000

# Set up the experiment structs and routing tables
for chip_y in range(2):
	for chip_x in range(2):
		load_ybug_commands += "sp %d %d 0\n"%(chip_x, chip_y)
		dump_ybug_commands += "sp %d %d 0\n"%(chip_x, chip_y)
		
		num_router_entries, router_entries = table_gen.spin1_table_gen(chips[(chip_x,chip_y)][0])
		
		for core in [c.core_id for c in chips[(chip_x,chip_y)][1]]:
			config_root = config_root_t.pack( tick_period # tick_microseconds
			                                , (1000000.0/tick_period) * warmup # Warmup duration
			                                , (1000000.0/tick_period) * duration # Experiment duration
			                                , 0 # rtr_drop_e
			                                , 1 # rtr_drop_m
			                                , 0 # result_dropped_packets
			                                , 0 # result_forwarded_packets
			                                , int((chip_x,chip_y,core) == (0,0,1)) # num_sources
			                                , 1 # num_sinks
			                                , num_router_entries if core==1 else 0 # num_router_entries
			                                )
			if (chip_x,chip_y,core) == (0,0,1):
				config_sources = config_source_t.pack( routing_key # Routing key
				                                     , TEMPORAL_DIST_BERNOULLI # Temporal dist
				                                     , bernoulli_packet_prob_t.pack(1.0) # bernoulli prob
				                                     , 0 # result_packets_generated
				                                     , 0 # result_packets_sent
				                                     )
			else:
				config_sources = ""
			config_sinks = config_sink_t.pack( routing_key # Routing key
			                                 , 0 # result_packets_arrived
			                                 )
			
			# Dump the configuration to a file
			config = config_root + config_sources + config_sinks
			if core == 1:
				config += router_entries
			
			configs[(chip_x, chip_y, core)] = config


# Write the configs into DRAM
for coords, config in configs.iteritems():
	x,y,core = coords
	conn.selected_cpu_coords = coords
	conn.write_mem(config_root_sdram_addr(core), scp.TYPE_BYTE, config)


# Load and run the application on all cores
for (x,y) in chips.iterkeys():
	# Apps must be started via the monitor processor
	conn.selected_cpu_coords = (x,y,0)
	
	# Load the APLX into memory
	conn.write_mem( 0x67800000
	              , scp.TYPE_WORD
	              , open("spinnaker_app/spinn_test_driver.aplx","rb").read()
	              )
	# Cause the APLX to be loaded into ITCM and executed on all cores
	core_mask = sum(1<<c.core_id for c in chips[(x,y)][1])
	conn.reset_aplx(core_mask, 16)

# Allow experiment to run
time.sleep(warmup + duration + 2.0)

# Read the results back from DRAM
num_diff = 0
for coords, config in configs.iteritems():
	x,y,core = coords
	conn.selected_cpu_coords = coords
	read_config = conn.read_mem(config_root_sdram_addr(core), scp.TYPE_BYTE, len(config))
	if read_config != config:
		num_diff+=1
print "%d cores wrote some results"%num_diff
