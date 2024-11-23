import errno
import socket
import sys
import threading
import time


def handle_request(hostname, record_type, rr_table, connection):
    # Check RR table for record
    record = rr_table.get_record(hostname, record_type)
    if record:
        print(f"Client: Record found for {hostname} ({record_type}):\n {record}")
    else:
        print(f"Record not found for {hostname} ({record_type}). Asking local DNS server...")
        local_dns_address = ("127.0.0.1", 21000)
        # Serialize the query
        transaction_id = rr_table.get_next_transaction_id()
        query = serialize_query(transaction_id, "0000", hostname, record_type)
        connection.send_message(query, local_dns_address)
        response, address = connection.receive_message()

        # Deserialize the response
        if response:
            response_data = deserialize_response(response)
            if response_data["result"] != "Record not found":
                rr_table.add_record(
                    response_data["name"],
                    response_data["type"],  # Use the string as-is
                    response_data["result"],
                    response_data["ttl"],
                    0
                )
                print(f"Client: Record saved for {response_data['name']} ({response_data['type']}).")
            else:
                print(f"Client: {response_data['result']} for {hostname} ({record_type}).")
    rr_table.display_table()


def main():
    rr_table = RRTable()
    connection = UDPConnection()
    try:
        while True:
            input_value = input("Enter the hostname (or type 'quit' to exit) <hostname> <query type>: ").strip()
            if input_value.lower() == "quit":
                break

            # Parse user input
            parts = input_value.split()
            hostname = parts[0]
            record_type = parts[1].upper() if len(parts) > 1 else "A"  # Default to 'A' if not specified

            # Handle the request
            handle_request(hostname, record_type, rr_table, connection)

    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")
    finally:
        connection.close()


def serialize_query(transaction_id, flag, name, query_type):
    """Serializes a DNS query into a string format."""
    return f"{transaction_id},{flag},{name},{query_type}"


def deserialize_response(data):
    """Deserializes a DNS response string into a dictionary."""
    parts = data.split(",")
    return {
        "transaction_id": int(parts[0]),
        "flag": parts[1],
        "name": parts[2],
        "type": parts[3],  # Keep this as a string
        "ttl": int(parts[4]) if parts[4].isdigit() else None,
        "result": parts[5],
    }


class RRTable:
    def __init__(self):
        self.records = {}
        self.record_number = 0
        self.transaction_id = 0
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._decrement_ttl, daemon=True)
        self.thread.start()

    def add_record(self, hostname, record_type, result, ttl, static):
        with self.lock:
            self.records[self.record_number] = {
                "name": hostname,
                "type": record_type,
                "result": result,
                "ttl": ttl,
                "static": static
            }
            self.record_number += 1

    def get_record(self, hostname, record_type=None):
        """
        Retrieves a record based on hostname and optionally record_type.
        """
        with self.lock:
            for record in self.records.values():
                if record["name"] == hostname and (record_type is None or record["type"] == record_type):
                    return record
            return None

    def get_next_transaction_id(self):
        with self.lock:
            self.transaction_id += 1
            return self.transaction_id

    def display_table(self):
        with self.lock:
            print(f"{'record_number':<15}{'name':<20}{'type':<10}{'result':<30}{'ttl':<6}{'static':<6}")
            print('-' * 90)
            for record_id, record in self.records.items():
                ttl = record["ttl"] if record["ttl"] is not None else "None"
                print(f"{record_id:<15}{record['name']:<20}{record['type']:<10}{record['result']:<30}{ttl:<6}{record['static']:<6}")

    def _decrement_ttl(self):
        while True:
            with self.lock:
                for record_id, record in list(self.records.items()):
                    if record["ttl"] and record["ttl"] > 0:
                        record["ttl"] -= 1
                self._remove_expired_records()
            time.sleep(1)

    def _remove_expired_records(self):
        expired_keys = [key for key, record in self.records.items() if record["ttl"] == 0]
        for key in expired_keys:
            del self.records[key]



class DNSTypes:
    name_to_code = {"A": 0b1000, "AAAA": 0b0100, "CNAME": 0b0010, "NS": 0b0001}
    code_to_name = {code: name for name, code in name_to_code.items()}

    @staticmethod
    def get_type_code(type_name: str):
        return DNSTypes.name_to_code.get(type_name)

    @staticmethod
    def get_type_name(type_code: int):
        return DNSTypes.code_to_name.get(type_code)


class UDPConnection:
    def __init__(self, timeout: int = 1):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(timeout)
        self.is_bound = False

    def send_message(self, message: str, address: tuple[str, int]):
        self.socket.sendto(message.encode(), address)

    def receive_message(self):
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
        if self.is_bound:
            print(f"Socket is already bound to address: {self.socket.getsockname()}")
            return
        self.socket.bind(address)
        self.is_bound = True

    def close(self):
        self.socket.close()


if __name__ == "__main__":
    main()
