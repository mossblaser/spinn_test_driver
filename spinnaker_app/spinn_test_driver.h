/**
 * A SpiNNaker network test tool.
 */

#ifndef SPINN_TEST_DRIVER_H
#define SPINN_TEST_DRIVER_H

/**
 * The timer period to use (microseconds)
 */
#define TIMER_TICK_PERIOD 500000u


/**
 * Size/shape of the system (used to generate the core map)
 */
// Uncomment if using one 48-node board
//#define SHAPE_HEXAGONAL

#ifndef SHAPE_HEXAGONAL
// Size of the system (in chips)
#define SYSTEM_WIDTH  2
#define SYSTEM_HEIGHT 2
#else
// Size is fixed for hexagonal systems. Do not change.
#define SYSTEM_WIDTH  12
#define SYSTEM_HEIGHT 12
#endif



/**
 * The number of cores involved per chip in a given experiment.
 */
#define NUM_CORES 16u


/**
 * A key used to denote a terminating entry in an array of config_source or
 * config_sink.
 */
#define CONFIG_TERMINAL_KEY 0xFFFFFFFFu


typedef enum temporal_dist {
	TEMPORAL_DIST_UNIFORM,
} temporal_dist_t;



/******************************************************************************
 * Config structures loaded into the shared system RAM.
 ******************************************************************************/

/**
 * A structure describing a desired packet generation scheme. These are stored
 * in an array terminated by an entry with the key CONFIG_TERMINAL_KEY.
 */
typedef struct config_source {
	// The key to be used with these packets
	uint routing_key;
	
	// The temporal distribution to use to decide when to generate these packets
	temporal_dist_t temporal_dist;
	
	// (Result) The number of packets generated & sent
	uint result_packets_sent;
} config_source_t;


/**
 * A structure which provides a counter for packet arrivals with a given routing
 * key.
 */
typedef struct config_sink {
	// The key of packets expected to arrive at this node
	uint routing_key;
	
	// (Result) The number of packets which arrived with this key
	uint result_packets_arrived;
} config_sink_t;


/**
 * The structure at the start of the config loaded onto each core.
 */
typedef struct config_root{
	// Number of timer ticks to complete before statistics are recorded from the
	// network.
	uint warmup_duration;
	
	// Number of timer ticks after the warmup the experiment should run for.
	uint duration;
	
	// Router packet drop delay (exponent & mantissa) during the experiment.
	ushort rtr_drop_e;
	ushort rtr_drop_m;
	
	// (Result) Number of packets dropped at this core
	uint result_dropped_packets;
	
	// (Result) Number of packets forwarded by this core
	uint result_forwarded_packets;
	
	// Pointers to the start of configurations/results for packet generators and
	// consumers.
	struct {
		config_source_t *sources;
		config_sink_t   *sinks;
	} core_configs[NUM_CORES];
} config_root_t;


#endif /* SPINN_TEST_DRIVER_H */
