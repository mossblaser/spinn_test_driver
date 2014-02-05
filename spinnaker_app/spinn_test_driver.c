/**
 * A SpiNNaker network test tool.
 */

#include <stdlib.h>

#include "spinnaker.h"
#include "spin1_api.h"

#include "spinn_test_driver.h"

#define MIN(a,b) (((a)<(b)) ? (a) : (b))
#define MAX(a,b) (((a)<(b)) ? (b) : (a))


/******************************************************************************
 * Coremap Generation
 ******************************************************************************/

/**
 * Set up the core map for the currently selected system in the header.
 */
static void init_core_map(void);

// A bitmap which specifies NUM_CORES application processors as members of the
// coremap.
#define ALL_CORE_MASK (((1u<<NUM_CORES)-1u) << 1)

#ifndef SHAPE_HEXAGONAL
	// Define a core map of the given size with all cores active.
	uint core_map[SYSTEM_WIDTH][SYSTEM_HEIGHT];
	
	/**
	 * Initialises the core_map with the appropriate bit mask
	 */
	static void
	init_core_map(void)
	{
		for (int y = 0; y < SYSTEM_HEIGHT; y++)
			for (int x = 0; x < SYSTEM_WIDTH; x++)
				core_map[x][y] = ALL_CORE_MASK;
	}
#else
	// Define a core map for a 48-node board (note that this is "upside down"
	// as Y increases downward unlike most figures showing a 48-node board.
	uint core_map[SYSTEM_WIDTH][SYSTEM_HEIGHT] = {
		{ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, 0,             0,             0,             0            },
		{ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, 0,             0,             0            },
		{ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, 0,             0            },
		{ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, 0            },
		{ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK},
		{0,             ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK},
		{0,             0,             ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK},
		{0,             0,             0,             ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK, ALL_CORE_MASK},
	};
	
	/**
	 * Does nothing since the core_map is preinitialised appropriately.
	 */
	static void
	init_core_map(void)
	{
		// Nothing to do.
	}
#endif


/******************************************************************************
 * Chip-wide experiment spec loading.
 ******************************************************************************/

/**
 * A local copy of the experimental configuration for this core.
 */
config_root_t config_root;

/**
 * Core-local versions of the source/sink data structures for this core.
 */
config_source_t config_sources[MAX_SOURCES_PER_CORE];
config_sink_t   config_sinks[MAX_SINKS_PER_CORE];


/**
 * A function which will load the configuration (for this core only) from the
 * shared SDRAM into the core-local variables above.
 *
 * Note that this is currently implemented the slow way using memcpy rather than
 * DMA to simplify programing as the penalty for the one-off copy is not too
 * significant.
 */
void
load_config(void)
{
	// Load the config_root for this core
	config_root_t *config_root_sdram_addr = CONFIG_ROOT_SDRAM_ADDR(spin1_get_core_id());
	spin1_memcpy(&config_root, config_root_sdram_addr, sizeof(config_root_t));
	
	// Calculate the address of the source & sink arrays and copy them across.
	config_source_t *config_sources_sdram_addr = (config_source_t *)(
		((uint)config_root_sdram_addr)
		+ sizeof(config_root_t)
	);
	config_sink_t *config_sinks_sdram_addr = (config_sink_t *)(
		((uint)config_root_sdram_addr)
		+ sizeof(config_root_t)
		+ sizeof(config_source_t) * config_root.num_sources
	);
	spin1_memcpy( &config_sources
	            , config_sources_sdram_addr
	            , sizeof(config_source_t) * config_root.num_sources
	            );
	spin1_memcpy( &config_sinks
	            , config_sinks_sdram_addr
	            , sizeof(config_sink_t) *  config_root.num_sinks
	            );
	
	io_printf( IO_BUF, "Loaded root config from 0x%08x with %d sources and %d sinks\n"
	         , (uint)config_root_sdram_addr
	         , config_root.num_sources
	         , config_root.num_sinks
	         );


/**
 * A function which will store a copy of the results in SDRAM, overwriting the
 * original configuration.
 *
 * Note that this is currently implemented the slow way using memcpy rather than
 * DMA to simplify programing as the penalty for the one-off copy is not too
 * significant.
 */
void
store_results(void)
{
	// TODO: Read counters
	
	config_root_t *config_root_sdram_addr = CONFIG_ROOT_SDRAM_ADDR(spin1_get_core_id());
	spin1_memcpy( config_sinks_sdram_addr
	            , &config_sinks
	            , sizeof(config_root)
	              + sizeof(config_source_t) * config_root.num_sources
	              + sizeof(config_sink_t)   * config_root.num_sinks
	            );
	
	io_printf( IO_BUF, "Stored results back into 0x%08x for %d sources and %d sinks\n"
	         , (uint)config_root_sdram_addr
	         , config_root.num_sources
	         , config_root.num_sinks
	         );
}


/******************************************************************************
 * Experiment State
 ******************************************************************************/

/**
 * The number of timer ticks the experiment has been running.
 */
uint simulation_ticks = 0u;

/**
 * Is the simulation currently warming up?
 */
bool simulation_warmup = TRUE;


/******************************************************************************
 * Traffic Generation
 ******************************************************************************/


static void
generate_packet(uint routing_key)
{
	if (!spin1_send_mc_packet(routing_key, 0u, false)) {
		io_printf(io_buf, "Could not generate packet with key 0x%08x at time %d (%s).\n"
		         , config_sources[i].routing_key
		         , simulation_ticks
		         , simulation_warmup ? "warmup" : "post-warmup"
		         );
	}
}


/**
 * Traffic generation and experiment management.
 */
void
on_timer_tick(uint _1, uint _2)
{
	// Experiment management
	if (simulation_warmup && simulation_ticks >= config_root.warmup_duration) {
		simulation_ticks = 0u;
		simulation_warmup = FALSE;
	} else if (!simulation_warmup && simulation_ticks >= config_root.duration) {
		spin1_stop();
	}
	
	// Show current status using LEDs
	if (leadAp) {
		bool led_on = simulation_ticks % (LED_BLINK_PERIOD/TIMER_TICK_PERIOD);
		
		// Drive with 50% brightness in warmup
		if (simulation_warmup)
			spin1_led_control((led_on && simulation_ticks%2) ? LED_ON(BLINK_LED) : LED_OFF(BLINK_LED));
		else
			spin1_led_control(led_on ? LED_ON(BLINK_LED) : LED_OFF(BLINK_LED));
	}
	
	
	// Generate traffic
	for (int i = 0; i < config_root.num_sources; i++) {
		switch (config_sources[i].temporal_dist) {
			case TEMPORAL_DIST_BERNOULLI:
				if (((float)rand() / (float)RAND_MAX) < config_sources[i].temporal_dist_data.bernoulli_packet_prob) {
					generate_packet(config_sources[i].routing_key);
					config_sources[i].result_packets_sent();
				}
				break;
			
			default:
				// Unrecognised temporal distribution do nothing...
				io_printf(IO_BUF, "Unrecognised traffic distribution '%d' for source with key 0x%08x.\n"
				         , config_sources[i].temporal_dist
				         , config_sources[i].routing_key
				         );
				break;
		}
	}
}



/******************************************************************************
 * Traffic Consumption
 ******************************************************************************/

/**
 * Callback for multicast packet arrival. Simply count the arrival of the packet
 * in the sinks table.
 *
 * Binary searches the list of sinks to find the entry corresponding to the
 * given key.
 */
void
on_mc_packet_received(uint key, uint payload)
{
	// During warmup, no results need be recorded.
	if (simulation_warmup)
		return;
	
	// Binary search variables
	uint min    = 0;
	uint max    = config_root.num_sinks-1;
	uint cursor = min + ((max-min)/2);
	
	while (min < max && config_sinks[cursor].key != key) {
		if (key < config_sinks[cursor].key) {
			max = cursor - 1;
		} else {
			min = cursor + 1;
		}
		cursor = min + ((max-min)/2);
	}
	
	// Increment the counter if a match was found
	if (config_sinks[cursor].key == key) {
		config_sinks[cursor].result_packets_arrived++
	} else {
		io_printf(IO_BUF, "Got unexpected packet with routing key = 0x%08x.\n", key)
	}
}


/******************************************************************************
 * Main (system initialisation/world starts here)
 ******************************************************************************/

void
c_main()
{
	// Check that enough (application) cores are working...
	if (sv->num_cpus - 1 < NUM_CORES) {
		io_printf(IO_STD, "Insufficient working application cores (%d), need at least %d.\n"
		         , sv->num_cpus - 1
		         , NUM_CORES
		         );
	}
	
	// Load up the core map
	init_core_map();
	spin1_application_core_map(SYSTEM_WIDTH, SYSTEM_HEIGHT, core_map);
	
	// Set up timer
	spin1_set_timer_tick(TIMER_TICK_PERIOD);
	spin1_callback_on(TIMER_TICK, on_timer_tick, 3);
	
	// Accept packets freely from the network
	spin1_callback_on(MC_PACKET_RECEIVED, on_mc_packet_received, -1);
	
	// Load this core's experimental configuration from SDRAM
	load_config();
	
	spin1_start();
	
	store_results();
}
