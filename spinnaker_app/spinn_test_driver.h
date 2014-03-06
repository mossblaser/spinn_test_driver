/**
 * A SpiNNaker network test tool.
 */

#ifndef SPINN_TEST_DRIVER_H
#define SPINN_TEST_DRIVER_H

#include <stdbool.h>


/**
 * The number of the LED to blink.
 */
#define BLINK_LED 1


/******************************************************************************
 * Config structures loaded into the shared SDRAM
 ******************************************************************************/

/**
 * Maximum number of source/sink/router entry structures per core. Used to
 * statically allocate sufficient memory for these structures in a core's RAM.
 */
#define MAX_SOURCES_PER_CORE 256u
#define MAX_SINKS_PER_CORE   256u
#define MAX_ROUTES_PER_CORE  1000u
#define MAX_DIMENSION_SIZE   24u

/**
 * A macro defining the address of the coremap in memory. The first two words
 * after this address define the width and height of the system in chips and
 * after this point represent an array [width][height] of uints containing the
 * core map.
 */
#define CORE_MAP_SDRAM_ADDR ((uint *)(SDRAM_BASE_UNBUF))

/**
 * A macro which yields the address in SDRAM of a core's config_root. Core 1
 * will have its config root at the base of SDRAM after the core map.
 */
#define CONFIG_ROOT_SDRAM_ADDR(core) ( (config_root_t *)((SDRAM_BASE_UNBUF)          \
                                       + ( (MAX_DIMENSION_SIZE*MAX_DIMENSION_SIZE+2) \
                                         * sizeof(uint)                              \
                                         )                                           \
                                       + (core-1) * ( sizeof(config_root_t)          \
                                                    + sizeof(config_source_t)        \
                                                      * MAX_SOURCES_PER_CORE         \
                                                    + sizeof(config_sink_t)          \
                                                      * MAX_SINKS_PER_CORE           \
                                                    + sizeof(config_router_entry_t)  \
                                                      * MAX_ROUTES_PER_CORE          \
                                                    )                                \
                                       )                                             \
                                     )


/**
 * The basic configuration for an experiment for a specific core.
 */
typedef struct config_root{
	// Number of microseconds between experiment ticks
	uint tick_microseconds;
	
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
	
	// The number of router entries to populate for the experiment. Immediately
	// follows the config_sink array in SDRAM.
	uint num_router_entries;
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
	uint result_packets_generated;
	
	// (Result) The number of packets successfuly placed into the network
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


/**
 * A structure which defines routing entries used by the experiment.
 */
typedef struct config_router_entry {
	// Key to match
	uint key;
	
	// Mask for key bits
	uint mask;
	
	// Route bits to forward packets with matching keys
	uint route;
} config_router_entry_t;


#endif /* SPINN_TEST_DRIVER_H */
