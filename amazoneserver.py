import errno
import socket
import sys
import json

def listen(rr_table, connection):
    try:
        while True:
            # Wait for query
            request, connection_addr = connection.receive_message()
            #print(f"Amazoneserver: Recieved Request for {request} from {connection_addr}")
            # Check RR table for record
            record = rr_table.get_record(request)
            if record:
                #print(f"AmazoneServer: Record found for {request}")
                response = [record['name'], record['type'], record['result'], 60, 0]
                responsepack = json.dumps(response)
                connection.send_message(responsepack, connection_addr)
            
            # If not found, add "Record not found" in the DNS response
            # Else, return record in DNS response
            else:
                #print(f"record not found")
                response = "Record Not Found"
                connection.send_message(response, connection_addr)
            # The format of the DNS query and response is in the project description

            # Display RR table
            rr_table.display_table()
    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")
    finally:
        connection.close()
        pass

def main():
    rr_table = RRTable()
    connection = UDPConnection()
    # Add initial records
    # These can be found in the test cases diagram
    rr_table.add_record("shop.amazone.com", "A", "3.33.147.88", "None", 1)
    rr_table.add_record("cloud.amazone.com", "A", "15.197.140.28", "None", 1)
    amazone_dns_address = ("127.0.0.1", 22000)
    # Bind address to UDP socket
    connection.bind(amazone_dns_address)
    #print("amazone server ready to recieve")
    listen(rr_table, connection)


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

    def add_record(self, hostname, record_type, result, ttl, static):
        self.records[self.record_number] = {
                "name": hostname,
                "type": record_type,
                "result": result,
                "ttl": ttl,
                "static" : static
            }
        self.record_number += 1

    def get_record(self, hostname):
        for record_id, record in self.records.items():
            if(record["name"] == hostname):
                return record
        return None

    def display_table(self):
        # Display the table in the following format (include the column names):
            # record_number,name,type,result,ttl,static
            #print(f"{'record_number':<15}{'name':<20}{'type':<10}{'result':<30}{'ttl':<6}{'static':<6}")
            #print('-' * 90)
            print("record_no,name,type,result,ttl,static")
            for record_id, record in self.records.items():
                 #print(f"{record_id:<15}{record['name']:<20}{record['type']:<10}{record['result']:<30}{record['ttl']:<6}{record['static']:<6}")
                 thing = str(record_id) + "," + str(record['name']) + "," + str(record['type']) + "," + str(record['result']) + "," + str(record['ttl']) + "," + str(record['static'])
                 print(thing)


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
