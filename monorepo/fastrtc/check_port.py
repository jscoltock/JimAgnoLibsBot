import socket
import psutil
import sys

def find_process_using_port(port: int):
    """Find the process using the specified port.
    
    Args:
        port: The port number to check
        
    Returns:
        Process information if found, None otherwise
    """
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == port:
                    return {
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': proc.info['cmdline']
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def main():
    port = 7860
    try:
        # First check if the port is actually in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("", port))
        sock.close()
        print(f"Port {port} is not in use")
    except OSError:
        print(f"Port {port} is in use")
        process = find_process_using_port(port)
        if process:
            print("\nProcess Information:")
            print(f"PID: {process['pid']}")
            print(f"Name: {process['name']}")
            print(f"Command Line: {' '.join(process['cmdline'])}")
        else:
            print("Could not find process information")

if __name__ == "__main__":
    main() 