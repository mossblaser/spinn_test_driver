/**
 * A SpiNNaker network test tool.
 */


/**
 * The number of cores involved per chip in a given experiment.
 */
#define NUM_CORES 16

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
	uint result_dropped_packets;
	
	// Pointers to the start of configurations/results for packet generators and
	// consumers.
	struct {
		config_source_t *sources;
		config_sink_t   *sinks;
	} core_configs[NUM_CORES];
} config_root_t;


