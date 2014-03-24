#!/usr/bin/env python

"""
Utility functions for producing result files from experimental runs.
"""

from collections import defaultdict

def tsv(column_names, rows):
	"""
	Produces TSV formatted data files given a set of column
	names and an iterable of rows of column data. If a row is None, a blank line
	is inserted.
	"""
	# Add the column headings
	out = "%s\n"%("\t".join(map(str,column_names)))
	
	# Add the data
	for row in rows:
		if row is None:
			out += "\n"
		else:
			out += "%s\n"%("\t".join(map(str,row)))
	
	return out.rstrip("\n")


def global_results(variable_fields_names, data):
	"""
	Produces TSV formatted, GNUplot compatible data files given a set of results.
	For each result, a single row will be produced containing system-wide
	information.
	
	variable_fields_names is a list which maps the index of the free
	variable columns to a name string.
	
	data is an iterable which contains one tuple for each experemental run. The
	tuple is of the form (var0,var1,...,varN, results) where var0-N are arbitary
	values representing the free-variable values for a given run of the
	experiment. The final value in the tuple must be the results object to be
	produced.
	"""
	
	column_names = list(variable_fields_names) + [ "total_dropped"
	                                             , "total_forwarded"
	                                             , "total_generated"
	                                             , "total_sent"
	                                             , "total_arrived"
	                                             , "num_chips"
	                                             , "num_cores"
	                                             , "num_sources"
	                                             , "num_sinks"
	                                             , "num_router_entries"
	                                             ]
	
	rows = []
	for datum in data:
		assert len(datum) == len(variable_fields_names) + 1\
		     , "Must have the same number of variables as variable field names."
		
		free_variables = datum[:-1]
		results        = datum[-1]
		
		# Calculate system-wide information
		total_dropped      = sum(chip.router.dropped_packets   for chip in results.itervalues())
		total_forwarded    = sum(chip.router.forwarded_packets for chip in results.itervalues())
		
		total_generated    = sum(sum(sum(source.packets_generated for source in core.sources.itervalues())
		                             for core in chip.cores.itervalues())
		                         for chip in results.itervalues())
		total_sent         = sum(sum(sum(source.packets_sent for source in core.sources.itervalues())
		                             for core in chip.cores.itervalues())
		                         for chip in results.itervalues())
		
		total_arrived      = sum(sum(sum(sink.packets_arrived for sink in core.sinks.itervalues())
		                             for core in chip.cores.itervalues())
		                         for chip in results.itervalues())
		
		num_cores          = sum(len(chip.cores) for chip in results.itervalues())
		num_chips          = len(results)
		
		num_sources        = sum(sum(len(core.sources)
		                             for core in chip.cores.itervalues())
		                         for chip in results.itervalues())
		num_sinks          = sum(sum(len(core.sinks)
		                             for core in chip.cores.itervalues())
		                         for chip in results.itervalues())
		
		num_router_entries = sum(chip.router.num_router_entries for chip in results.itervalues())
		
		rows.append(list(free_variables) + [ total_dropped
		                                   , total_forwarded
		                                   , total_generated
		                                   , total_sent
		                                   , total_arrived
		                                   , num_cores
		                                   , num_chips
		                                   , num_sources
		                                   , num_sinks
		                                   , num_router_entries
		                                   ])
	
	return tsv(column_names, rows)


def per_chip_results( variable_fields_names, data
                    , square_off = True
                    , sentinel = 0
                    , gnuplot_comaptible = True
                    ):
	"""
	Produces TSV formatted, GNUplot compatible data files given a set of results.
	For each result, a row will be printed for each chip.
	
	variable_fields_names is a list which maps the index of the free
	variable columns to a name string.
	
	data is an iterable which contains one tuple for each experemental run. The
	tuple is of the form (var0,var1,...,varN, results) where var0-N are arbitary
	values representing the free-variable values for a given run of the
	experiment. The final value in the tuple must be the results object to be
	produced.
	
	square_off will insert extra rows corresponding to chips which don't exist
	within the rectangular boundary of the system, e.g. for 48-node baord systems.
	
	sentinel is the sentinel value which will be used in place of result values
	for chips which don't exist when square_off is used.
	
	gnuplot_comaptible will add empty lines between rows of chips.
	"""
	
	column_names = list(variable_fields_names) + [ "x"
	                                             , "y"
	                                             , "dropped"
	                                             , "forwarded"
	                                             , "total_generated"
	                                             , "total_sent"
	                                             , "total_arrived"
	                                             , "num_cores"
	                                             , "num_sources"
	                                             , "num_sinks"
	                                             , "num_router_entries"
	                                             ]
	
	rows = []
	for datum in data:
		assert len(datum) == len(variable_fields_names) + 1\
		     , "Must have the same number of variables as variable field names."
		
		free_variables = datum[:-1]
		results        = datum[-1]
		
		max_x = max(x for (x,y) in results)
		max_y = max(y for (x,y) in results)
		
		for y in range(max_y + 1):
			for x in range(max_x + 1):
				if square_off or (x,y) in results:
					chip = results[(x,y)]
					
					# Calculate chip-wide information
					dropped            = chip.router.dropped_packets
					forwarded          = chip.router.forwarded_packets
					
					total_generated    = sum(sum(source.packets_generated for source in core.sources.itervalues())
					                         for core in chip.cores.itervalues())
					total_sent         = sum(sum(source.packets_sent for source in core.sources.itervalues())
					                         for core in chip.cores.itervalues())
					
					total_arrived      = sum(sum(sink.packets_arrived for sink in core.sinks.itervalues())
					                         for core in chip.cores.itervalues())
					
					num_cores          = len(chip.cores)
					
					num_sources        = sum(len(core.sources)
					                         for core in chip.cores.itervalues())
					num_sinks          = sum(len(core.sinks)
					                         for core in chip.cores.itervalues())
					
					num_router_entries = chip.router.num_router_entries
				else:
					dropped         = sentinel
					forwarded       = sentinel
					total_generated = sentinel
					total_sent      = sentinel
					total_arrived   = sentinel
					num_cores       = sentinel
					num_sources     = sentinel
					num_sinks       = sentinel
					
				
				if square_off or (x,y) in results:
					rows.append(list(free_variables) + [ x
					                                   , y
					                                   , dropped
					                                   , forwarded
					                                   , total_generated
					                                   , total_sent
					                                   , total_arrived
					                                   , num_cores
					                                   , num_sources
					                                   , num_sinks
					                                   , num_router_entries
					                                   ])
			
			# Add blank lines after each row for gnuplot compatibility
			if gnuplot_comaptible:
				rows.append(None)
	
	return tsv(column_names, rows)


def per_core_results(variable_fields_names, data):
	"""
	Produces TSV formatted, GNUplot compatible data files given a set of results.
	For each result, a row will be printed for each core.
	
	variable_fields_names is a list which maps the index of the free
	variable columns to a name string.
	
	data is an iterable which contains one tuple for each experemental run. The
	tuple is of the form (var0,var1,...,varN, results) where var0-N are arbitary
	values representing the free-variable values for a given run of the
	experiment. The final value in the tuple must be the results object to be
	produced.
	"""
	
	column_names = list(variable_fields_names) + [ "x"
	                                             , "y"
	                                             , "core_id"
	                                             , "total_generated"
	                                             , "total_sent"
	                                             , "total_arrived"
	                                             , "num_sources"
	                                             , "num_sinks"
	                                             ]
	
	rows = []
	for datum in data:
		assert len(datum) == len(variable_fields_names) + 1\
		     , "Must have the same number of variables as variable field names."
		
		free_variables = datum[:-1]
		results        = datum[-1]
		
		for (x,y), chip in results.iteritems():
			for core_id, core in chip.cores.iteritems():
				chip = results[(x,y)]
				
				# Calculate chip-wide information
				total_generated    = sum(source.packets_generated for source in core.sources.itervalues())
				total_sent         = sum(source.packets_sent for source in core.sources.itervalues())
				
				total_arrived      = sum(sink.packets_arrived for sink in core.sinks.itervalues())
				
				num_sources        = len(core.sources)
				num_sinks          = len(core.sinks)
				
				rows.append(list(free_variables) + [ x
				                                   , y
				                                   , core_id
				                                   , total_generated
				                                   , total_sent
				                                   , total_arrived
				                                   , num_sources
				                                   , num_sinks
				                                   ])
	
	return tsv(column_names, rows)


def per_stream_results(variable_fields_names, data):
	"""
	Produces TSV formatted, GNUplot compatible data files given a set of results.
	For each result, a row will be printed for each stream (i.e. routing key).
	
	variable_fields_names is a list which maps the index of the free
	variable columns to a name string.
	
	data is an iterable which contains one tuple for each experemental run. The
	tuple is of the form (var0,var1,...,varN, results) where var0-N are arbitary
	values representing the free-variable values for a given run of the
	experiment. The final value in the tuple must be the results object to be
	produced.
	"""
	
	column_names = list(variable_fields_names) + [ "routing_key"
	                                             , "total_generated"
	                                             , "total_sent"
	                                             , "total_arrived"
	                                             , "num_sources"
	                                             , "num_sinks"
	                                             ]
	
	rows = []
	for datum in data:
		assert len(datum) == len(variable_fields_names) + 1\
		     , "Must have the same number of variables as variable field names."
		
		free_variables = datum[:-1]
		results        = datum[-1]
		
		# Extract the set of streams {route: (sources, sinks),...}
		streams = defaultdict(lambda: ([],[]))
		for (x,y), chip in results.iteritems():
			for core_id, core in chip.cores.iteritems():
				for route, source in core.sources.iteritems():
					streams[route][0].append(source)
				for route, sinks in core.sinks.iteritems():
					streams[route][1].append(sinks)
		
		
		for route, (sources, sinks) in streams.iteritems():
				# Calculate chip-wide information
				total_generated    = sum(source.packets_generated for source in sources)
				total_sent         = sum(source.packets_sent for source in sources)
				
				total_arrived      = sum(sink.packets_arrived for sink in sinks)
				
				num_sources        = len(sources)
				num_sinks          = len(sinks)
				
				rows.append(list(free_variables) + [ route
				                                   , total_generated
				                                   , total_sent
				                                   , total_arrived
				                                   , num_sources
				                                   , num_sinks
				                                   ])
	
	return tsv(column_names, rows)
