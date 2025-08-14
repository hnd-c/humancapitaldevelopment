#!/usr/bin/env python3
"""
Generate pgAdmin Configuration - Create pgAdmin servers.json from current config

This utility generates pgAdmin configuration files based on the current
environment settings, making it easy to connect to the database via pgAdmin.
"""

import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.environments import load_config_for_environment
from config.settings import generate_pgadmin_config


def main():
    """Generate pgAdmin configuration file"""
    parser = argparse.ArgumentParser(description="Generate pgAdmin servers.json configuration")
    parser.add_argument(
        "--environment",
        default="development",
        help="Environment to generate config for (development, staging, production)"
    )
    parser.add_argument(
        "--output",
        default="config/pgadmin_servers.json",
        help="Output path for the pgAdmin configuration file"
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Generate config for Docker environment (use 'postgres' as host)"
    )

    args = parser.parse_args()

    try:
        # Load configuration for the specified environment
        config = load_config_for_environment(args.environment)

        # Override host for Docker if requested
        if args.docker:
            config.database.host = "postgres"

        # Generate pgAdmin configuration
        success = generate_pgadmin_config(config.database, args.output)

        if success:
            print(f"🎉 pgAdmin configuration generated successfully!")
            print(f"📁 File location: {args.output}")
            print("\n📋 Usage instructions:")
            print("1. Copy the generated file to your pgAdmin servers directory")
            print("2. Or import it via pgAdmin: File > Preferences > Storage > File storage")
            print("3. Restart pgAdmin to see the new server connection")
            print("\n🐳 For Docker:")
            print("   - Mount the config file to pgAdmin container")
            print("   - Or copy it to /pgadmin4/servers.json in the container")

            return 0
        else:
            print("❌ Failed to generate pgAdmin configuration")
            return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
