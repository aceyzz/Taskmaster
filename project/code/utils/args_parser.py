import sys


def parse_arguments():
    """
    Parse command-line arguments for Taskmaster.
    
    Supports:
        -f <path>, --config <path>, -c <path>: Configuration file path
        -l <level>, --loglevel <level>: Log level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        tuple: (config_path, log_level)
    """
    config_path = "./config_examples/valid.yml"  # Default
    log_level = None
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        # Configuration file argument
        if arg in ("-f", "--config", "-c", "--file"):
            if i + 1 >= len(sys.argv):
                print(f"Error: {arg} requires a file path argument", file=sys.stderr)
                print("Usage: taskmaster [-f <config_file>] [-l <log_level>]", file=sys.stderr)
                sys.exit(1)
            config_path = sys.argv[i + 1]
            i += 2
            
        # Log level argument
        elif arg in ("-l", "--loglevel"):
            if i + 1 >= len(sys.argv):
                print(f"Error: {arg} requires a log level argument", file=sys.stderr)
                print("Valid levels: DEBUG, INFO, WARNING, ERROR", file=sys.stderr)
                sys.exit(1)
            log_level = sys.argv[i + 1].upper()
            if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
                print(f"Error: Invalid log level '{log_level}'", file=sys.stderr)
                print("Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL", file=sys.stderr)
                sys.exit(1)
            i += 2
            
        # Help flag
        elif arg in ("-h", "--help"):
            print("Taskmaster - Job Control Daemon")
            print("\nUsage:")
            print("  taskmaster [-f <config_file>] [-l <log_level>]")
            print("\nOptions:")
            print("  -f, --config, -c <file>   Path to configuration file (default: ./config_examples/valid.yml)")
            print("  -l, --loglevel <level>    Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
            print("  -h, --help                Show this help message")
            print("\nSignals:")
            print("  SIGHUP                    Reload configuration")
            print("  SIGINT (Ctrl+C)           Graceful shutdown")
            sys.exit(0)
            
        # Unknown argument
        else:
            print(f"Error: Unknown argument '{arg}'", file=sys.stderr)
            print("Use -h or --help for usage information", file=sys.stderr)
            sys.exit(1)
    
    return config_path, log_level