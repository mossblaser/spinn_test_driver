#!/usr/bin/env python

"""
A wrapper which deals with many of the details of producing and running network
experiments.
"""

import math


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
		
		# The number of microseconds each tick lasts. Value can be set in seconds
		# using the tick_period property.
		self._tick_period = 1000
		
		# Exponent and mantissa of a SpiNNaker router timeout. The encoded value can
		# be set using the router_timeout property.
		self._router_timeout_e = 5
		self._router_timeout_m = 0
		
		# Experiment duration in ticks. Set in seconds by the warmup and duration
		# properties.
		self._warmup   = 1
		self._duration = 1
	
	
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
		
		# Re-scale the warmup/duration now that the duration of a tick has changed
		warmup   = self.warmup
		duration = self.duration
		
		self._tick_period = period_usec
		
		self.warmup   = warmup
		self.duration = duration
	
	
	@property
	def router_timeout(self):
		e = self._router_timeout_e
		m = self._router_timeout_m
		
		if e <= 4:
			return (m + 16 - 2**(4-e)) * 2**e
		else:
			return (m + 16           ) * 2**e
	
	
	@router_timeout.setter
	def router_timeout(self, value):
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
		return self._warmup * self.tick_period
	
	
	@property
	def duration(self):
		return self._duration * self.tick_period
	
	
	@warmup.setter
	def warmup(self, warmup):
		warmup_ticks = int(warmup / self.tick_period)
		assert warmup_ticks >= 0, "Warmup must be at least a positive number of ticks."
		self._warmup = warmup_ticks
	
	
	@duration.setter
	def duration(self, duration):
		duration_ticks = int(duration / self.tick_period)
		assert duration_ticks >= 0, "Duration must be at least a positive number of ticks."
		self._duration = duration_ticks


if __name__=="__main__":
	experiment = NetworkExperiment([])
	for e in range(0, 16):
		for m in range(0, 16):
			expected = (m+16-(2**(4-e) if e <= 4 else 0))*2**e
			experiment.router_timeout = expected
			assert experiment.router_timeout == expected \
			     , "%d == %d for e=%d,m=%d"%(experiment.router_timeout, expected, e,m)
