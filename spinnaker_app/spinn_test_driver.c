/**
 * A SpiNNaker network test tool.
 */

#include <stdlib.h>

#include "spinnaker.h"
#include "spin1_api.h"

#include "spinn_test_driver.h"

#define MIN(a,b) (((a)<(b)) ? (a) : (b))
#define MAX(a,b) (((a)<(b)) ? (b) : (a))

static volatile uint * const rtr_unbuf = (uint *) RTR_BASE_UNBUF;


/******************************************************************************
 * Chip-wide experiment spec loading.
 ******************************************************************************/

/**
 * The size of the system and the core map.
 */
uint system_width;
uint system_height;
uint core_map[MAX_DIMENSION_SIZE*MAX_DIMENSION_SIZE];

/**
 * A local copy of the experimental configuration for this core.
 */
config_root_t config_root;

/**
 * Core-local versions of the source/sink data structures for this core.
 */
config_source_t       config_sources[MAX_SOURCES_PER_CORE];
config_sink_t         config_sinks[MAX_SINKS_PER_CORE];
config_router_entry_t config_router_entries[MAX_ROUTES_PER_CORE];


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
	// Load the core-map for this core
	uint *core_map_root = CORE_MAP_SDRAM_ADDR;
	system_width  = core_map_root[0];
	system_height = core_map_root[1];
	spin1_memcpy(core_map, &(core_map_root[2]), sizeof(uint)*system_width*system_height);
	
	// Load the config_root for this core
	config_root_t *config_root_sdram_addr = CONFIG_ROOT_SDRAM_ADDR(spin1_get_core_id());
	spin1_memcpy(&config_root, config_root_sdram_addr, sizeof(config_root_t));
	
	// Seed the random number generator
	spin1_srand(config_root.seed);
	
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
	config_router_entry_t *config_router_entries_sdram_addr = (config_router_entry_t *)(
		((uint)config_root_sdram_addr)
		+ sizeof(config_root_t)
		+ sizeof(config_source_t) * config_root.num_sources
		+ sizeof(config_sink_t)   * config_root.num_sinks
	);
	spin1_memcpy( &config_sources
	            , config_sources_sdram_addr
	            , sizeof(config_source_t) * config_root.num_sources
	            );
	spin1_memcpy( &config_sinks
	            , config_sinks_sdram_addr
	            , sizeof(config_sink_t) * config_root.num_sinks
	            );
	spin1_memcpy( &config_router_entries
	            , config_router_entries_sdram_addr
	            , sizeof(config_router_entry_t) * config_root.num_router_entries
	            );
	
	io_printf( IO_BUF, "Loaded root config from 0x%08x with %d sources, %d sinks and %d router entries and %d/%d warmup/experiment cycles.\n"
	         , (uint)config_root_sdram_addr
	         , config_root.num_sources
	         , config_root.num_sinks
	         , config_root.num_router_entries
	         , config_root.warmup_duration
	         , config_root.duration
	         );
}


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
	// Turn on LED until results written
	if (leadAp)
		spin1_led_control(LED_ON(BLINK_LED));
	
	// Copy source results back.
	config_source_t *config_sources_sdram_addr = (config_source_t *)( ((uint)CONFIG_ROOT_SDRAM_ADDR(spin1_get_core_id()))
	                                                                  + sizeof(config_root_t)
	                                                                )
	                                           ;
	spin1_memcpy( config_sources_sdram_addr
	            , &config_sources
	            , sizeof(config_source_t) * config_root.num_sources
	            );
	
	// Copy sink results back.
	config_sink_t *config_sinks_sdram_addr = (config_sink_t *)( ((uint)CONFIG_ROOT_SDRAM_ADDR(spin1_get_core_id()))
	                                                            + sizeof(config_root_t)
	                                                            + sizeof(config_source_t) * config_root.num_sources
	                                                          )
	                                         ;
	spin1_memcpy( config_sinks_sdram_addr
	            , &config_sinks
	            , sizeof(config_sink_t) * config_root.num_sinks
	            );
	
	// Record router counters
	config_root.result_forwarded_packets = rtr_unbuf[FWD_CNTR_CNT];
	config_root.result_dropped_packets   = rtr_unbuf[DRP_CNTR_CNT];
	
	// Copy root config results back last so that the completion_state is only
	// updated when most of the data is coppied back.
	config_root_t *config_root_sdram_addr = CONFIG_ROOT_SDRAM_ADDR(spin1_get_core_id());
	spin1_memcpy(config_root_sdram_addr, &config_root, sizeof(config_root_t));
	
	// Note that routes are not copied back because they aren't changed.
	
	io_printf( IO_BUF, "Stored results back into 0x%08x.\n"
	         , (uint)config_root_sdram_addr
	         );
	
	// Turn off LED on completion.
	if (leadAp)
		spin1_led_control(LED_OFF(BLINK_LED));
}


/******************************************************************************
 * Router config/state access functions
 ******************************************************************************/

// The original state of the rotuer configuration before the experiment was
// started.
uint rtr_control_orig_state;


/**
 * Load the routing tables and router parameters as required by the current
 * experiment. The existing router parameters are stored into the
 * rtr_control_orig_state to be restored by cleanup_router at the end of the
 * experiment.
 */
void
setup_router(void)
{
	// Install the router entries
	for (int i = 0; i < config_root.num_router_entries; i++) {
		if (!spin1_set_mc_table_entry( i
		                             , config_router_entries[i].key
		                             , config_router_entries[i].mask
		                             , config_router_entries[i].route
		                             )) {
			io_printf( IO_BUF, "Could not load routing table entry %d with key 0x%08x"
			         , i
			         , config_router_entries[i].key
			         );
			config_root.completion_state = COMPLETION_STATE_FAILIURE;
		}
	}
	
	// Only one core should configure the router
	if (leadAp) {
		// Store the current router configuration
		rtr_control_orig_state = rtr_unbuf[RTR_CONTROL];
		
		// Set up the packet drop timeout
		rtr_unbuf[RTR_CONTROL] = (rtr_unbuf[RTR_CONTROL] & ~0x00FF8000u)
		                       | (config_root.rtr_drop_e<<4 | config_root.rtr_drop_m) << 16
		                       | 1<<15 // Re-initialise counters
		                       ;
		
		// Configure forwarded packets counter
		rtr_unbuf[FWD_CNTR_CFG] = (0x1<< 0) // Type = nn
		                        | (0x1<< 4) // ER = 0 (non-emergency-routed packets)
		                        | (  0<< 8) // M = 0 (match emergency flag on incoming packets)
		                        | (0x3<<10) // Def = Match default and non-default routed packets
		                        | (0x3<<12) // PL = Match packets with and without payloads
		                        | (0x3<<14) // Loc = Match local and external packets
		                        | ( (0x1F<<19) // Match all external links
		                          | (   0<<18) // Don't match monitor packets
		                          | (   1<<17) // Match packets to local non-monitor cores
		                          | (   0<<16) // Don't match dropped packets
		                          ) // Dest = Which destinations should be matched
		                        | (  0<<30) // E = Don't enable interrupt on event
		                        ;
		
		// Configure dropped packets counter
		rtr_unbuf[DRP_CNTR_CFG] = (0x1<< 0) // Type = nn
		                        | (0x1<< 4) // ER = 0 (non-emergency-routed packets)
		                        | (  0<< 8) // M = 0 (match emergency flag on incoming packets)
		                        | (0x3<<10) // Def = Match default and non-default routed packets
		                        | (0x3<<12) // PL = Match packets with and without payloads
		                        | (0x3<<14) // Loc = Match local and external packets
		                        | ( (0x00<<19) // Don't match external links
		                          | (   0<<18) // Don't match monitor packets
		                          | (   0<<17) // Don't match packets to local non-monitor cores
		                          | (   1<<16) // Match dropped packets
		                          ) // Dest = Which destinations should be matched
		                        | (  0<<30) // E = Don't enable interrupt on event
		                        ;
	}
	
	// Allow change to make it into the router
	spin1_delay_us(10000);
}


/**
 * Restore the router's settings prior to ending the experiment.
 */
void
cleanup_router(void)
{
	// Only one core should restore the router config.
	if (leadAp) {
		// Restore router configuration (and reinitialise timers to clear deadlocks)
		rtr_unbuf[RTR_CONTROL] = rtr_control_orig_state | 1<<15;
		spin1_delay_us(10000);
		
		// Set the timer reset bit back to the original value again
		rtr_unbuf[RTR_CONTROL] = rtr_control_orig_state;
		spin1_delay_us(10000);
	}
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
volatile bool simulation_warmup = true;


/******************************************************************************
 * Traffic Generation
 ******************************************************************************/


void
generate_packet(uint source_index)
{
	if (!simulation_warmup)
		config_sources[source_index].result_packets_generated ++;
	
	if (spin1_send_mc_packet(config_sources[source_index].routing_key, 0u, false)) {
		if (!simulation_warmup)
			config_sources[source_index].result_packets_sent ++;
	} else {
		io_printf(IO_BUF, "Could not generate packet with key 0x%08x at time %d (%s).\n"
		         , config_sources[source_index].routing_key
		         , simulation_ticks
		         , simulation_warmup ? "warmup" : "post-warmup"
		         );
		config_root.completion_state = COMPLETION_STATE_FAILIURE;
	}
}


/**
 * Traffic generation and experiment management.
 */
void
on_timer_tick(uint _1, uint _2)
{
	// Experiment management
	if (simulation_warmup && simulation_ticks == 0) {
		// Start of warmup
		io_printf(IO_BUF, "Warmup starting...\n");
	}
	
	// Start of warmup, start of experiment
	if (simulation_warmup && simulation_ticks >= config_root.warmup_duration) {
		simulation_ticks = 0u;
		simulation_warmup = false;
		io_printf(IO_BUF, "Warmup ended, starting main experiment...\n");
		
		// Reset and enable counters
		if (leadAp)
			rtr_unbuf[RTR_DGEN] |=  (FWD_CNTR_BIT | DRP_CNTR_BIT)
			                     | ((FWD_CNTR_BIT | DRP_CNTR_BIT)<<16)
			                     ;
	}
	
	// End of experiment
	if (!simulation_warmup && simulation_ticks >= config_root.duration) {
		// Disable counters
		if (leadAp)
			rtr_unbuf[RTR_DGEN] &= ~(FWD_CNTR_BIT | DRP_CNTR_BIT);
		
		if (config_root.completion_state != COMPLETION_STATE_FAILIURE)
			config_root.completion_state = COMPLETION_STATE_SUCCESS;
		
		spin1_stop();
		return;
	}
	
	simulation_ticks ++;
	
	// Show current status using LEDs
	if (leadAp) {
		// Drive with 1/16% brightness in warmup
		if (simulation_warmup)
			spin1_led_control((simulation_ticks%16 == 0) ? LED_ON(BLINK_LED) : LED_OFF(BLINK_LED));
		else
			spin1_led_control(LED_ON(BLINK_LED));
	}
	
	
	// Generate traffic
	for (int i = 0; i < config_root.num_sources; i++) {
		switch (config_sources[i].temporal_dist) {
			case TEMPORAL_DIST_BERNOULLI:
				if (((float)rand() / (float)RAND_MAX) < config_sources[i].temporal_dist_data.bernoulli_packet_prob) {
					generate_packet(i);
				}
				break;
			
			default:
				// Unrecognised temporal distribution do nothing...
				io_printf(IO_BUF, "Unrecognised traffic distribution '%d' for source with key 0x%08x.\n"
				         , config_sources[i].temporal_dist
				         , config_sources[i].routing_key
				         );
				config_root.completion_state = COMPLETION_STATE_FAILIURE;
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
	// During warmup and upon completion, no results need be recorded.
	if (simulation_warmup || simulation_ticks >= config_root.duration)
		return;
	
	// Binary search variables
	uint min    = 0;
	uint max    = config_root.num_sinks-1;
	uint cursor = min + ((max-min)/2);
	
	while (min < max && config_sinks[cursor].routing_key != key) {
		if (key < config_sinks[cursor].routing_key) {
			max = cursor - 1;
		} else {
			min = cursor + 1;
		}
		cursor = min + ((max-min)/2);
	}
	
	// Increment the counter if a match was found
	if (config_sinks[cursor].routing_key == key) {
		config_sinks[cursor].result_packets_arrived++;
	} else {
		io_printf(IO_BUF, "Got unexpected packet with routing key = 0x%08x.\n", key);
		config_root.completion_state = COMPLETION_STATE_FAILIURE;
	}
}


/******************************************************************************
 * Main (system initialisation/world starts here)
 ******************************************************************************/

void
c_main()
{
	// Copy this core's experimental configuration from SDRAM
	load_config();
	
	// Set up the core map
	spin1_application_core_map( system_width, system_height
	                          , (uint (*)[system_height])&core_map[0]
	                          );
	
	// Accept packets freely from the network
	spin1_callback_on(MC_PACKET_RECEIVED, on_mc_packet_received, -1);
	
	// Set up timer
	spin1_set_timer_tick(config_root.tick_microseconds);
	spin1_callback_on(TIMER_TICK, on_timer_tick, 3);
	
	setup_router();
	
	// Report that we're ready
	io_printf(IO_BUF, "Waiting for spin1_start barrier...\n");
	
	// Run the experiment
	spin1_start();
	
	cleanup_router();
	
	store_results();
}
