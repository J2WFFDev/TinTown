
#!/usr/bin/env python3
"""CLI entry point for the Impact Bridge."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from impact_bridge.bridge import run_bridge


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TinTown Impact Bridge - Steel plate impact detection system"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.debug)
    
    # Validate config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    
    # Run the bridge
    try:
        asyncio.run(run_bridge(str(config_path)))
    except KeyboardInterrupt:
        print("\\nBridge stopped by user")
    except Exception as e:
        print(f"Bridge failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
