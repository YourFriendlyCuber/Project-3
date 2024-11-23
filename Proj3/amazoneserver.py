import errno
import socket
import sys


def listen(rr_table, connection):
    try:
        print("Amazone DNS server is ready to receive queries.")
        while True:
            # Wait for a query from the Local DNS server
            data, local_dns_address = connection.receive_message()
            query = deserialize_query(data)
            print(f"AmazoneServer: Received query for {query['name']} ({query['type']}) from {local_dns_address}")

            # Check the RR table for the requested record
            record = rr_table.get_record(query["name"], query["type"])
            if record:
                print(f"AmazoneServer: Record found for {query['name']} ({query['type']}): {record['result']}")
                response = serialize_response(
                    query["transaction_id"], "0001", record["name"], record["type"], record["ttl"], record["result"]
                )
            else:
                print(f"AmazoneServer: Record not found for {query['name']} ({query['type']}).")
                response = serialize_response(query["transaction_id"], "0001", query["name"], query["type"], None, "Record not found")

            # Send the response back to the Local DNS server
            connection.send_message(response, local_dns_address)
            rr_table.display_table()

    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")
    finally:
        connection.close()


def main():
    rr_table = RRTable()
    connection = UDPConnection()

    # Add initial records
    rr_table.add_record("shop.amazone.com", "A", "3.33.147.88", None, 1)
    rr_table.add_record("cloud.amazone.com", "A", "15.197.140.28", None, 1)
    rr_table.add_record("cdn.amazone.com", "CNAME", "cloud.amazone.com", None, 1)
    rr_table.add_record("dns.amazone.com", "NS", "127.0.0.1", None, 1)

    amazone_dns_address = ("127.0.0.1", 22000)
    connection.bind(amazone_dns_address)
    listen(rr_table, connection)


def serialize_response(transaction_id, flag, name, record_type, ttl, result):
    """Serializes a DNS response into a string."""
    ttl_field = str(ttl) if ttl is not None else "None"
    return f"{transaction_id},{flag},{name},{record_type},{ttl_field},{result}"


def deserialize_query(data):
    """Deserializes a DNS query string into a dictionary."""
    parts = data.split(",")
    return {
        "transaction_id": int(parts[0]),
        "flag": parts[1],
        "name": parts[2],
        "type": parts[3],  # Keep this as a string
    }


class RRTable:
    def __init__(self):
        self.records = {}
        self.record_number = 0

    def add_record(self, hostname, record_type, result, ttl, static):
        self.records[self.record_number] = {
            "record_number": self.record_number,
            "name": hostname,
            "type": record_type,
            "result": result,
            "ttl": ttl,
            "static": static,
        }
        self.record_number += 1

    def get_record(self, hostname, record_type):
        """Retrieve a record by hostname and type."""
        for record in self.records.values():
            if record["name"] == hostname and record["type"] == record_type:
                return record
        return None

    def display_table(self):
        print(f"{'record_number':<15}{'name':<20}{'type':<10}{'result':<30}{'ttl':<6}{'static':<6}")
        print('-' * 90)
        for record_id, record in self.records.items():
            ttl = record["ttl"] if record["ttl"] is not None else "None"
            print(
                f"{record_id:<15}{record['name']:<20}{record['type']:<10}{record['result']:<30}{ttl:<6}{record['static']:<6}"
            )


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
