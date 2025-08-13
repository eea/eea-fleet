#!/usr/bin/env python3
"""
Entry point for EEA Fleet Configuration Generator
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    from src.main import main
    main()