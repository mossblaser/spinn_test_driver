/**
 * A SpiNNaker network test tool.
 */

#include "spin1_api.h"

#include "spinn_test_driver.h"



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
 * Main (system initialisation/world starts here)
 ******************************************************************************/

void
xxx_test(uint _1, uint _2)
{
	// Core 1 on each chip should flash the LEDs
	if (leadAp)
		spin1_led_control(LED_INV(1));
}

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
	
	//spin1_callback_on(USER_EVENT, xxx_test, 2);
	//spin1_trigger_user_event(0,0);
	
	// Set up timer
	spin1_set_timer_tick(TIMER_TICK_PERIOD);
  spin1_callback_on(TIMER_TICK, xxx_test, 3);
	
	spin1_start();
}
