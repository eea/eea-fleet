#!/usr/bin/env python3
"""
EEA Fleet Configuration Generator - Main Application

Simplified terminal interface using consolidated core and screens modules.
"""

import os
import sys
import logging
from pathlib import Path
from textual.app import App

# Import consolidated modules
from . import core
from .styles import MAIN_CSS
from .screens import create_main_screen


class EEAFleetApp(App):
    """Simplified EEA Fleet Configuration Generator application."""
    
    CSS = MAIN_CSS
    TITLE = "EEA Fleet Configuration Generator"
    SUB_TITLE = "Simplified Fleet Configuration Tool"
    
    def on_mount(self) -> None:
        """Initialize the application with simplified setup."""
        # Load settings and initialize directories
        core.load_settings()
        core.initialize_directories()
        
        # Show main screen
        self.push_screen(create_main_screen())


def setup_logging():
    """Setup simplified logging without conflicting with core module."""
    debug_enabled = os.environ.get('EEA_DEBUG', 'false').lower() in ('true', '1', 'yes')
    
    # Only setup console logging for the main app, core module handles file logging
    level = logging.DEBUG if debug_enabled else logging.INFO
    
    # Get the root logger and configure it for console only
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers to avoid conflicts
    root_logger.handlers.clear()
    
    # Only add console handler - core module handles debug.log
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(console_handler)
    
    if debug_enabled:
        print("Debug logging enabled. Core module handles debug.log")
    else:
        print("Debug logging disabled. Set EEA_DEBUG=true to enable.")


def main():
    """Main entry point."""
    setup_logging()
    
    try:
        app = EEAFleetApp()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Application error: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()