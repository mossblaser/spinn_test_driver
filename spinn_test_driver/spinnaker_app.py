#!/usr/bin/env python

"""
Definitions of the structs used to store experimental parameters and results in
the SpiNNaker-based test driver program.
"""

import os
import struct

from collections import namedtuple

def _union(*member_definitions):
	"""
	Produces a definition for a union of a given set of member definitions for the
	struct module.
	"""
	
	length = max(m.size for m in member_definitions)
	return "%ds"%length


# Values for the enum temporal_dist in config_source_t.
TEMPORAL_DIST_BERNOULLI = 0

# Maximum number of source/sink structures per core. Used to statically allocate
# sufficient memory for these structures in a core's RAM.
MAX_SOURCES_PER_CORE = 256
MAX_SINKS_PER_CORE   = 256
MAX_ROUTES_PER_CORE  = 1000
MAX_DIMENSION_SIZE   = 24

config_root_t = struct.Struct( "<" # Little endian, standard sizes (i.e. 2-byte short, 4-byte int)
                             + "I" # uint   seed
                             + "I" # uint   tick_microseconds
                             + "I" # uint   warmup_duration
                             + "I" # uint   duration
                             + "H" # ushort rtr_drop_e
                             + "H" # ushort rtr_drop_m
                             + "I" # uint   result_dropped_packets
                             + "I" # uint   result_forwarded_packets
                             + "I" # uint   num_sources
                             + "I" # uint   num_sinks
                             + "I" # uint   num_router_entries
                             )
config_root_tuple = namedtuple( "config_root_tuple"
                              , [ "seed"
                                , "tick_microseconds"
                                , "warmup_duration"
                                , "duration"
                                , "rtr_drop_e"
                                , "rtr_drop_m"
                                , "result_dropped_packets"
                                , "result_forwarded_packets"
                                , "num_sources"
                                , "num_sinks"
                                , "num_router_entries"
                                ]
                              )

bernoulli_packet_prob_t = struct.Struct( "<" # Little endian, standard sizes (i.e. 2-byte short, 4-byte int)
                                       + "f" # bernoulli_packet_prob
                                       )
bernoulli_packet_prob_tuple = namedtuple( "bernoulli_packet_prob_tuple"
                                        , [ "bernoulli_packet_prob"
                                          ]
                                        )

config_source_t = struct.Struct( "<" # Little endian, standard sizes (i.e. 2-byte short, 4-byte int)
                               + "I" # uint routing_key
                               + "I" # enum temporal_dist
                               + _union( bernoulli_packet_prob_t # bernoulli_packet_prob
                                       ) # union temporal_dist_data
                               + "I" # uint result_packets_generated
                               + "I" # uint result_packets_sent
                               )
config_source_tuple = namedtuple( "config_source_tuple"
                                , [ "routing_key"
                                  , "temporal_dist"
                                  , "temporal_dist_data"
                                  , "result_packets_generated"
                                  , "result_packets_sent"
                                  ]
                                )

config_sink_t = struct.Struct( "<" # Little endian, standard sizes (i.e. 2-byte short, 4-byte int)
                             + "I" # uint routing_key
                             + "I" # uint result_packets_arrived
                             )
config_sink_tuple = namedtuple( "config_sink_tuple"
                              , [ "routing_key"
                                , "result_packets_arrived"
                                ]
                              )

config_router_entry_t = struct.Struct( "<" # Little endian, standard sizes (i.e. 2-byte short, 4-byte int)
                                     + "I" # uint key
                                     + "I" # uint mask
                                     + "I" # uint route
                                     )
config_router_entry_tuple = namedtuple( "config_router_entry_tuple"
                                      , [ "key"
                                        , "mask"
                                        , "route"
                                        ]
                                      )

def core_map_struct_pack(core_map):
	"""
	Returns the packed struct of the provided coremap which should be a dict
	{ (x,y): coremap, ... }.
	"""
	# Work out size of the system
	width, height = [max(d)+1 for d in zip(*core_map.iterkeys())]
	
	out = struct.pack("II", width, height)
	
	for y in range(width):
		for x in range(width):
			out += struct.pack("I", core_map.get((x,y), 0x00000000))
	
	return out


def core_map_struct_unpack(core_map_packed):
	width_height_packed = core_map_packed[:struct.calcsize("II")]
	core_map_packed     = core_map_packed[struct.calcsize("II"):]
	
	width,height = struct.unpack("II", width_height_packed)
	
	core_map = {}
	
	elem = struct.Struct("I")
	elem_size = elem.calcsize()
	
	for y in range(width):
		for x in range(height):
			core_map[(x,y)] = elem.unpack(core_map_packed[:elem_size])[0]
			core_map_packed = core_map_packed[elem_size:]
	
	return core_map


SDRAM_BASE_UNBUF = 0x70000000

def core_map_sdram_addr():
	"""
	Return the address of the coremap in SDRAM.
	"""
	return SDRAM_BASE_UNBUF

def config_root_sdram_addr(core):
	"""
	Given a core number, return the address in SDRAM where the configuration data
	will be loaded.
	"""
	return ( SDRAM_BASE_UNBUF
	       + ( (MAX_DIMENSION_SIZE*MAX_DIMENSION_SIZE+2)
	         * struct.calcsize("I")
	         )
	       + (core-1) * ( config_root_t.size
	                    + config_source_t.size
	                      * MAX_SOURCES_PER_CORE
	                    + config_sink_t.size
	                      * MAX_SINKS_PER_CORE
	                    + config_router_entry_t.size
	                      * MAX_ROUTES_PER_CORE
	                    )
	       )


# The path of the compiled SpiNNaker app APLX file.
SPINNAKER_APP_APLX = os.path.join(os.path.dirname(__file__), "..", "spinnaker_app/spinn_test_driver.aplx")
