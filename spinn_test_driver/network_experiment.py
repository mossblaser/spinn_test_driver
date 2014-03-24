#!/usr/bin/env python

"""
A wrapper which deals with many of the details of producing and running network
experiments.
"""

import math
import time
import random

from collections import defaultdict, namedtuple

import pacman103.scp as scp

import spinn_route.model
import spinn_route.table_gen

from spinn_test_driver import spinnaker_app

################################################################################
# Traffic patterns
################################################################################

# Bernoulli temporal distribution for packet generation
BernoulliGeneration = namedtuple("BernoulliGeneration", ["probability"])

# Packet consumer which accepts packets instantly
InstantConsumption = namedtuple("InstantConsumption", [])


################################################################################
# Result objects
################################################################################

# Each chip has an associated result tuple
ChipResults = namedtuple("ChipResults", ["router","cores"])

# Contained by the router and cores items respectively in ChipResults
RouterResults = namedtuple("RouterResults", ["dropped_packets","forwarded_packets","num_router_entries"])
CoreResults   = namedtuple("CoreResults",   ["sources", "sinks"])

# Contained by the sources and sinks items respectively in CoreResults
SourceResults = namedtuple("SourceResults", ["packets_generated", "packets_sent"])
SinkResults   = namedtuple("SinkResults",   ["packets_arrived"])


################################################################################
# Experiment object
################################################################################

class ExperimentFailed(Exception):
	"""
	Exception thrown when the experiment being run reports a failiure.
	"""
	def __init__(self, msg, bad_cores):
		Exception.__init__(self, msg)
		self.bad_cores = bad_cores


class NetworkExperiment(object):
	"""
	A particular network experiment.
	"""
	
	def __init__(self, chips):
		"""
		Takes a dict {coord: (router, [core,...]),...}, i.e. a spinn_route network
		model.
		"""
		self.chips = chips
		
		# Dictionaries which map cores to a dictionary {Route:gen/con spec,...}
		self.core_generators = defaultdict(dict)
		self.core_consumers  = defaultdict(dict)
		
		# The number of microseconds each tick lasts. Value can be set in seconds
		# using the tick_period property.
		self._tick_period = 1000
		
		# Exponent and mantissa of a SpiNNaker router timeout. The encoded value can
		# be set using the router_timeout property.
		self._router_timeout_e = 5
		self._router_timeout_m = 0
		
		# Experiment warmup and duration in seconds. Access via the property returns
		# the actual warmup/duration used given the currently selected timer tick interval.
		self._warmup   = 1.0
		self._duration = 2.0
		
		# The next routing key to use
		self._next_routing_key = 0
	
	
	@property
	def tick_period(self):
		"""
		The duration of an experiment tick in seconds.
		"""
		return self._tick_period / 1000000.0
	
	
	@tick_period.setter
	def tick_period(self, period):
		"""
		The duration of an experiment tick in seconds.
		"""
		period_usec = int(period * 1000000.0)
		assert period_usec > 0, "Tick period must be at least 1 usec."
		
		self._tick_period = period_usec
	
	
	@property
	def router_timeout(self):
		"""
		The router timeout (wait1) before dropping packets in router cycles.
		"""
		e = self._router_timeout_e
		m = self._router_timeout_m
		
		if e <= 4:
			return (m + 16 - 2**(4-e)) * 2**e
		else:
			return (m + 16           ) * 2**e
	
	
	@router_timeout.setter
	def router_timeout(self, value):
		"""
		The router timeout (wait1) before dropping packets in router cycles.
		"""
		# Hard-coded solutions for e <= 4, a more general solution exists after that
		if value == 0:
			e = m = 0
		elif value < 16:
			e = 0
			m = value
		elif value < 48:
			e = 1
			m = (value/2)-8
		elif value < 112:
			e = 2
			m = (value/4)-12
		elif value < 240:
			e = 3
			m = (value/8)-14
		elif value < 512:
			e = 4
			m = (value/16)-15
		else:
			e = max(0, int(math.log(value,2)) - 4)
			m = (value / (1<<e)) - 16
		
		# Clamp the exponent and mantissa to allowed 4-bit ranges
		e = max(0, min(15, e))
		m = max(0, min(15, m))
		
		# Test that the value is represented exactly
		if e <= 4:
			calc_value = (m + 16 - 2**(4-e)) * 2**e
		else:
			calc_value = (m + 16           ) * 2**e
		
		if calc_value != value:
			raise ValueError("A timeout of %d cannot be used. You could use %d instead..."%(value, calc_value))
		
		self._router_timeout_e = e
		self._router_timeout_m = m
	
	
	@property
	def warmup(self):
		"""
		The duration of the network warmup period (seconds). This value reflects the
		actual warmup time with the currently selected tick_period.
		"""
		return int(self._warmup/self.tick_period) * self.tick_period
	
	
	@property
	def duration(self):
		"""
		The duration of the data-collection period (seconds). This value reflects the
		actual warmup time with the currently selected tick_period.
		"""
		return int(self._duration/self.tick_period) * self.tick_period
	
	
	@warmup.setter
	def warmup(self, warmup):
		"""
		The duration of the network warmup period (seconds)
		"""
		self._warmup = warmup
	
	
	@duration.setter
	def duration(self, duration):
		"""
		The duration of the data-collection period (seconds)
		"""
		self._duration = duration
	
	
	def add_stream(self, source_, destinations, routing_algorithms_):
		"""
		Add a stream of packets from a source core to a set of destinations routed
		by the supplied list of routing algorithms from spinn_route (with latter
		routers picking up unrouted paths from the ones before them). Assigns
		sequential routing keys to the streams.
		
		Returns the routing key used by the stream.
		"""
		source, gen = source_
		
		# Route from the soruce to all destinations.
		unrouted_dests = [d for (d,c) in destinations]
		routing_algorithms = routing_algorithms_[:]
		node_sequences = []
		while unrouted_dests:
			if not routing_algorithms:
				raise Exception("Some destinations could not be routed with the routers provided!")
			node_sequences_, unrouted_dests = routing_algorithms.pop(0)(
				source,
				unrouted_dests,
				self.chips
			)
			node_sequences.extend(node_sequences_)
		
		# Add the route to the model
		route = spinn_route.model.Route(self._next_routing_key)
		self._next_routing_key += 1
		for node_sequence in node_sequences:
			spinn_route.model.add_route(route, node_sequence)
		
		# Note down where the traffic generators/consumers live
		self.core_generators[source][route] = gen
		for dest, con in destinations:
			self.core_consumers[dest][route] = con
		
		return route.key
	
	
	def _load_coremaps(self, conn):
		"""
		Generate the coremap for the system and write it to every chip.
		"""
		# Calculate coremap
		core_map = {}
		for coord, chip in self.chips.iteritems():
			core_map[coord] = sum(1<<c.core_id for c in chip.cores.itervalues())
		data = spinnaker_app.core_map_struct_pack(core_map)
		addr = spinnaker_app.core_map_sdram_addr()
		
		# Load onto system
		for (x,y), chip in self.chips.iteritems():
			conn.selected_cpu_coords = (x,y,0)
			conn.write_mem(addr, scp.TYPE_BYTE, data)
	
	
	def _load_configs(self, conn):
		"""
		Pack and load the configuration data for all chips/cores on the system.
		"""
		for (x,y), chip in self.chips.iteritems():
			# Select the chip to load the data into
			conn.selected_cpu_coords = (x,y,0)
			
			# Generate the chip's routing table (only loaded by a single core)
			num_router_entries, router_entries = \
				spinn_route.table_gen.spin1_table_gen(chip.router)
			
			# Ensure we don't have too many routing entries
			if num_router_entries > spinnaker_app.MAX_ROUTES_PER_CORE:
				raise Exception("Too many router entries on a single core: %d (max %d)"%(
					num_router_entries, spinnaker_app.MAX_ROUTES_PER_CORE
				))
			
			for index, core in enumerate(chip.cores.itervalues()):
				# Arbitarily choose one core to load the routing tables
				loads_router_enties = index == 0
				
				# Ensure we don't have too many sources/sinks
				if len(self.core_generators[core]) > spinnaker_app.MAX_SOURCES_PER_CORE:
					raise Exception("Too many sources on a single core: %d (max %d)"%(
						len(self.core_generators[core]), spinnaker_app.MAX_SOURCES_PER_CORE
					))
				if len(self.core_consumers[core]) > spinnaker_app.MAX_SINKS_PER_CORE:
					raise Exception("Too many sinks on a single core: %d (max %d)"%(
						len(self.core_consumers[core]), spinnaker_app.MAX_SINKS_PER_CORE
					))
				
				# The root block of the configuration 
				config_root = spinnaker_app.config_root_t.pack(*spinnaker_app.config_root_tuple(
					completion_state         = spinnaker_app.COMPLETION_STATE_RUNNING,
					seed                     = random.getrandbits(32),
					tick_microseconds        = self._tick_period,
					warmup_duration          = int(self._warmup/self.tick_period),
					duration                 = int(self._duration/self.tick_period),
					rtr_drop_e               = self._router_timeout_e,
					rtr_drop_m               = self._router_timeout_m,
					result_dropped_packets   = 0,
					result_forwarded_packets = 0,
					num_sources              = len(self.core_generators[core]),
					num_sinks                = len(self.core_consumers[core]),
					num_router_entries       = num_router_entries if loads_router_enties else 0,
				))
				
				# Define the packet sources
				config_sources = ""
				for route, gen in self.core_generators[core].iteritems():
					# Encode packet generator data
					if type(gen) is BernoulliGeneration:
						temporal_dist = spinnaker_app.TEMPORAL_DIST_BERNOULLI
						temporal_dist_data = spinnaker_app.bernoulli_packet_prob_t.pack(
							*spinnaker_app.bernoulli_packet_prob_tuple(
								bernoulli_packet_prob = gen.probability
							)
						)
					else:
						raise Exception("Unknown packet generator %s."%repr(gen))
					
					# Encode this source
					config_sources += spinnaker_app.config_source_t.pack(*spinnaker_app.config_source_tuple(
						routing_key              = route.key,
						temporal_dist            = temporal_dist,
						temporal_dist_data       = temporal_dist_data,
						result_packets_generated = 0,
						result_packets_sent      = 0,
					))
				
				# Define the packet sinks (which must be supplied in ascending order of
				# routing key)
				config_sinks = ""
				for route in sorted(self.core_consumers[core]):
					con = self.core_consumers[core][route]
					
					# Encode packet generator data
					if type(con) is not InstantConsumption:
						raise Exception("Unknown packet consumer %s."%repr(con))
					
					# Encode this sink
					config_sinks += spinnaker_app.config_sink_t.pack(*spinnaker_app.config_sink_tuple(
						routing_key            = route.key,
						result_packets_arrived = 0,
					))
				
				# Put all the configuration blocks together
				config = config_root + config_sources + config_sinks
				
				if loads_router_enties:
					config += router_entries
				
				# Load this core's configuration
				addr = spinnaker_app.config_root_sdram_addr(core.core_id)
				data = config
				conn.write_mem(addr, scp.TYPE_BYTE, data)
	
	
	def _run_app(self, conn):
		"""
		Run the application on the machine and block until the experiment is
		complete.
		"""
		# Load the spinnaker app onto all cores
		for (x,y), chip in self.chips.iteritems():
			# Apps must be started via the monitor processor
			conn.selected_cpu_coords = (x,y,0)
			
			# Load the APLX into memory
			# XXX: Shouldn't this be defined in the SCP module...
			conn.write_mem( 0x67800000
			              , scp.TYPE_WORD
			              , open(spinnaker_app.SPINNAKER_APP_APLX,"rb").read()
			              )
		
		# Start the app on all cores
		for (x,y), chip in self.chips.iteritems():
			# Apps must be started via the monitor processor
			conn.selected_cpu_coords = (x,y,0)
			# Cause the APLX to be loaded into ITCM and executed on all cores
			core_mask = sum(1<<core_id for core_id in chip.cores.iterkeys())
			conn.reset_aplx(core_mask, 16)
		
		# Wait until when the experiment is expected to have finished.
		time.sleep(self.warmup + self.duration + 0.1)
		
		# Explicitly check cores until every core reports completion, create a list
		# of bad cores.
		bad_cores = []
		for (x,y), chip in self.chips.iteritems():
			conn.selected_cpu_coords = (x,y,0)
			for core_id, core in chip.cores.iteritems():
				timeout = 10
				while True:
					addr = spinnaker_app.config_root_sdram_addr(core_id)
					data = conn.read_mem(addr, scp.TYPE_BYTE, spinnaker_app.completion_state_t.size)
					completion_state = spinnaker_app.completion_state_t.unpack(data)[0]
					
					if completion_state == spinnaker_app.COMPLETION_STATE_RUNNING:
						# Wait a bit longer before timing out
						time.sleep(0.1)
						timeout -= 1
						if timeout <= 0:
							bad_cores.append(core)
							break
					elif completion_state == spinnaker_app.COMPLETION_STATE_SUCCESS:
						# Move onto the next chip
						break
					else:
						# Something failed!
						bad_cores.append(core)
						break
		
		# If any cores failed, throw an exception
		if bad_cores:
			raise ExperimentFailed("%d cores reported failiure or timed out while executing the experiment."%len(bad_cores), bad_cores)
	
	
	def _collect_results(self, conn):
		"""
		Collect and collate the results from the system into a Results object.
		"""
		results = {}
		
		for (x,y), chip in self.chips.iteritems():
			# Select the chip to download the data from
			conn.selected_cpu_coords = (x,y,0)
			
			router_results = None
			core_results = {}
			
			for index, core in enumerate(chip.cores.itervalues()):
				# Arbitarily choose one core to load the router results from (since
				# they're all identical)
				downloads_router_results = index == 0
				
				# Download the data from this core
				addr = spinnaker_app.config_root_sdram_addr(core.core_id)
				data = conn.read_mem(addr, scp.TYPE_BYTE,
					spinnaker_app.config_root_t.size
					+ spinnaker_app.config_source_t.size * len(self.core_generators[core])
					+ spinnaker_app.config_sink_t.size   * len(self.core_consumers[core])
				)
				
				# Pull out the root block
				config_root = spinnaker_app.config_root_tuple(
					*spinnaker_app.config_root_t.unpack(data[:spinnaker_app.config_root_t.size])
				)
				data = data[spinnaker_app.config_root_t.size:]
				
				# Pull out the sources blocks
				config_sources = []
				for _ in self.core_generators[core]:
					config_sources.append(spinnaker_app.config_source_tuple(
						*spinnaker_app.config_source_t.unpack(data[:spinnaker_app.config_source_t.size])
					))
					data = data[spinnaker_app.config_source_t.size:]
				
				# Pull out the sinks blocks
				config_sinks = []
				for _ in self.core_consumers[core]:
					config_sinks.append(spinnaker_app.config_sink_tuple(
						*spinnaker_app.config_sink_t.unpack(data[:spinnaker_app.config_sink_t.size])
					))
					data = data[spinnaker_app.config_sink_t.size:]
				
				# Should have now processed all the data
				assert data == ""
				
				# Extract the router results
				if downloads_router_results:
					router_results = RouterResults( forwarded_packets  = config_root.result_forwarded_packets
					                              , dropped_packets    = config_root.result_dropped_packets
					                              , num_router_entries = config_root.num_router_entries
					                              )
				sources = {}
				sinks   = {}
				
				# Extract the core's results
				for source in config_sources:
					sources[source.routing_key] = SourceResults( packets_generated = source.result_packets_generated
					                                           , packets_sent      = source.result_packets_sent
					                                           )
				for sink in config_sinks:
					sinks[sink.routing_key] = SinkResults(packets_arrived = sink.result_packets_arrived)
				
				core_results[core.core_id] = CoreResults( sources = sources
				                                        , sinks   = sinks
				                                        )
			
			results[(x,y)] = ChipResults(router = router_results, cores = core_results)
		
		return results
	
	
	def run(self, hostname):
		"""
		Run the experiment on the selected (booted) SpiNNaker board.
		
		Returns a Results object once simulation has completed.
		"""
		# Connect to the board
		conn = scp.SCPConnection(hostname)
		conn.version()
		
		# Run the experiment, fetch the results
		self._load_coremaps(conn)
		self._load_configs(conn)
		self._run_app(conn)
		return self._collect_results(conn)


