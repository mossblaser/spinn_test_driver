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
 * The number of the LED to blink.
 */
#define BLINK_LED 1


/**
 * How frequently should the LED blink (microseconds)
 */
#define LED_BLINK_PERIOD 500000u


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
 * The number of cores involved per chip in a given experiment.
 */
#define NUM_CORES 16u


/******************************************************************************
 * Config structures loaded into the shared SDRAM
 ******************************************************************************/

/**
 * Maximum number of source/sink structures per core. Used to statically
 * allocate sufficient memory for these structures in a core's RAM.
 */
#define MAX_SOURCES_PER_CORE 256u
#define MAX_SINKS_PER_CORE   256u

/**
 * A macro which yields the address in SDRAM of a core's config_root. Core 1
 * will have its config root at the base of SDRAM.
 */
#define CONFIG_ROOT_SDRAM_ADDR(core) ( (config_root_t *)((SDRAM_BASE_UNBUF)   \
                                       + (core-1) * ( sizeof(config_root_t)   \
                                                    + sizeof(config_source_t) \
                                                      * MAX_SOURCES_PER_CORE  \
                                                    + sizeof(config_sink_t)   \
                                                      * MAX_SINKS_PER_CORE    \
                                                    )                         \
                                       )                                      \
                                     )


/**
 * The basic configuration for an experiment for a specific core.
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
	
	// Number of config_source entries which immediately follow this structure in
	// SDRAM
	uint num_sources;
	
	// Number of config_sink entries which immediately follow the config_source
	// array in SDRAM. These entries are always maintained in ascending order of
	// routing key to allow efficient searching.
	uint num_sinks;
} config_root_t;


/**
 * Types of packet generation distributions.
 */
typedef enum temporal_dist {
	TEMPORAL_DIST_BERNOULLI = 0,
} temporal_dist_t;


/**
 * A structure describing a desired packet generation scheme for a given key.
 */
typedef struct config_source {
	// The key to be used with these packets
	uint routing_key;
	
	// The temporal distribution to use to decide when to generate these packets
	temporal_dist_t temporal_dist;
	
	union {
		// For bernoulli dist
		float bernoulli_packet_prob;
	} temporal_dist_data;
	
	// (Result) The number of packets generated (though sending may fail)
	uint result_packets_sent;
} config_source_t;


/**
 * A structure which provides a counter for packet arrivals with a given routing
 * key.
 *
 * These entries are always maintained in ascending order of routing key to
 * allow efficient searching.
 */
typedef struct config_sink {
	// The key of packets expected to arrive at this node
	uint routing_key;
	
	// (Result) The number of packets which arrived with this key
	uint result_packets_arrived;
} config_sink_t;




#endif /* SPINN_TEST_DRIVER_H */
