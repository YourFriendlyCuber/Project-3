import errno
import socket
import sys
import threading
import time
import json


def handle_request(hostname, rr_table, connection):
    # Check RR table for record
    record = rr_table.get_record(hostname)
    if record:
        print(f"Client: Record found for {hostname}:\n {record}")
    # If not found, ask the local DNS server, then save the record if valid
    else:
        print(f"record not found for {hostname}. Asking local DNS server...")
        local_dns_address = ("127.0.0.1", 21000)
        connection.send_message(hostname, local_dns_address)
        response, address = connection.receive_message()
        responseunpack = json.loads(response)
        if(response != "Record Not Found"):
            rr_table.add_record(responseunpack[0], responseunpack[1], responseunpack[2], responseunpack[3], responseunpack[4])
    rr_table.display_table()

def main():
    rr_table = RRTable()
    connection = UDPConnection()
    try:
        while True:
            input_value = input("Enter the hostname (or type 'quit' to exit) ")
            if input_value.lower() == "quit":
                break

            hostname = input_value
            query_code = DNSTypes.get_type_code("A")
            
            handle_request(hostname, rr_table, connection)

    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")
    finally:
        connection.close()
        pass


def serialize():
    # Consider creating a serialize function
    # This can help prepare data to send through the socket
    pass


def deserialize():
    # Consider creating a deserialize function
    # This can help prepare data that is received from the socket
    pass


class RRTable:
    def __init__(self):
        self.records = {
            
        }
        self.record_number = 0
        # Start the background thread
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.__decrement_ttl, daemon=True)
        self.thread.start()
    
    def add_record(self, hostname, record_type, result, ttl, static):
        with self.lock:
            self.records[self.record_number] = {
                "name": hostname,
                "type": record_type,
                "result": result,
                "ttl": ttl,
                "static" : static
            }
            self.record_number += 1

    def get_record(self, hostname):
        with self.lock:
            for record_id, record in self.records.items():
                if(record["name"] == hostname):
                    return record
        return None

    def display_table(self):
        with self.lock:
            # Display the table in the following format (include the column names):
            # record_number,name,type,result,ttl,static
            #print(f"{'record_number':<15}{'name':<20}{'type':<10}{'result':<30}{'ttl':<6}{'static':<6}")
            #print('-' * 90)
            
            for record_id, record in self.records.items():
                 #print(f"{record_id:<15}{record['name']:<20}{record['type']:<10}{record['result']:<30}{record['ttl']:<6}{record['static']:<6}")
                 thing = str(record_id) + "," + str(record['name']) + "," + str(record['type']) + "," + str(record['result']) + "," + str(record['ttl']) + "," + str(record['static'])
                 print(thing)

    def __decrement_ttl(self):
        while True:
            with self.lock:
                # Decrement ttl
                for record_id, record in self.records.items():
                    if record['ttl'] > 0:
                        record['ttl'] -= 1
                self.__remove_expired_records()
            time.sleep(1)

    def __remove_expired_records(self):
        # This method is only called within a locked context
        # Remove expired records
        expired_keys = [key for key, record in self.records.items() if record['ttl'] != "None" and record['ttl'] <= 0]
        for key in expired_keys:
            del self.records[key]
        # Update record numbers
        new_record_number = 0
        new_records = {}
        
        for key, record in sorted(self.records.items()):
            record['record_number'] = new_record_number
            new_records[new_record_number] = record
            new_record_number += 1
        
        self.records = new_records
        self.record_number = new_record_number


class DNSTypes:
    """
    A class to manage DNS query types and their corresponding codes.

    Examples:
    >>> DNSTypes.get_type_code('A')
    8
    >>> DNSTypes.get_type_name(0b0100)
    'AAAA'
    """

    name_to_code = {
        "A": 0b1000,
        "AAAA": 0b0100,
        "CNAME": 0b0010,
        "NS": 0b0001,
    }

    code_to_name = {code: name for name, code in name_to_code.items()}

    @staticmethod
    def get_type_code(type_name: str):
        """Gets the code for the given DNS query type name, or None"""
        return DNSTypes.name_to_code.get(type_name, None)

    @staticmethod
    def get_type_name(type_code: int):
        """Gets the DNS query type name for the given code, or None"""
        return DNSTypes.code_to_name.get(type_code, None)


class UDPConnection:
    """A class to handle UDP socket communication, capable of acting as both a client and a server."""

    def __init__(self, timeout: int = 1):
        """Initializes the UDPConnection instance with a timeout. Defaults to 1."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(timeout)
        self.is_bound = False

    def send_message(self, message: str, address: tuple[str, int]):
        """Sends a message to the specified address."""
        self.socket.sendto(message.encode(), address)

    def receive_message(self):
        """
        Receives a message from the socket.

        Returns:
            tuple (data, address): The received message and the address it came from.

        Raises:
            KeyboardInterrupt: If the program is interrupted manually.
        """
        while True:
            try:
                data, address = self.socket.recvfrom(4096)
                return data.decode(), address
            except socket.timeout:
                continue
            except OSError as e:
                if e.errno == errno.ECONNRESET:
                    print("Error: Unable to reach the other socket. It might not be up and running.")
                else:
                    print(f"Socket error: {e}")
                self.close()
                sys.exit(1)
            except KeyboardInterrupt:
                raise

    def bind(self, address: tuple[str, int]):
        """Binds the socket to the given address. This means it will be a server."""
        if self.is_bound:
            print(f"Socket is already bound to address: {self.socket.getsockname()}")
            return
        self.socket.bind(address)
        self.is_bound = True

    def close(self):
        """Closes the UDP socket."""
        self.socket.close()


if __name__ == "__main__":
    main()

