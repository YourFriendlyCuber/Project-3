import errno
import socket
import sys
import threading
import time


def listen(rr_table, connection):
    try:
        print("Local DNS server is ready to receive queries.")
        while True:
            # Receive a query from the client
            data, client_address = connection.receive_message()
            query = deserialize_query(data)
            print(f"LocalServer: Received query for {query['name']} from {client_address}")

            # Check the RR table for the requested record
            record = rr_table.get_record(query["name"])
            if record:
                print(f"LocalServer: Record found for {query['name']}: {record['result']}")
                response = serialize_response(
                    query["transaction_id"], "0001", record["name"], record["type"], record["ttl"], record["result"]
                )
            else:
                # Forward query to the authoritative DNS server
                print(f"LocalServer: Record not found for {query['name']}. Forwarding to authoritative DNS server...")
                amazone_dns_address = ("127.0.0.1", 22000)
                connection.send_message(data, amazone_dns_address)
                amazone_response, _ = connection.receive_message()

                response_data = deserialize_response(amazone_response)
                if response_data["result"] != "Record not found":
                    rr_table.add_record(
                        response_data["name"],
                        DNSTypes.get_type_name(response_data["type"]),
                        response_data["result"],
                        response_data["ttl"],
                        0,
                    )
                response = amazone_response

            # Send the response back to the client
            connection.send_message(response, client_address)
            rr_table.display_table()

    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")
    finally:
        connection.close()


def main():
    rr_table = RRTable()
    connection = UDPConnection()

    # Add initial records
    rr_table.add_record("www.csusm.edu", "A", "144.37.5.45", None, 1)
    rr_table.add_record("my.csusm.edu", "A", "144.37.5.150", None, 1)
    rr_table.add_record("amazone.com", "NS", "dns.amazone.com", None, 1)
    rr_table.add_record("dns.amazone.com", "A", "127.0.0.1", None, 1)

    local_dns_address = ("127.0.0.1", 21000)
    connection.bind(local_dns_address)
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
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._decrement_ttl, daemon=True)
        self.thread.start()

    def add_record(self, hostname, record_type, result, ttl, static):
        with self.lock:
            self.records[self.record_number] = {
                "record_number": self.record_number,
                "name": hostname,
                "type": record_type,
                "result": result,
                "ttl": ttl,
                "static": static,
            }
            self.record_number += 1

    def get_record(self, hostname):
        with self.lock:
            for record in self.records.values():
                if record["name"] == hostname:
                    return record
            return None

    def display_table(self):
        with self.lock:
            print(f"{'record_number':<15}{'name':<20}{'type':<10}{'result':<30}{'ttl':<6}{'static':<6}")
            print('-' * 90)
            for record_id, record in self.records.items():
                name = record['name'] or "N/A"
                record_type = record['type'] or "N/A"
                result = record['result'] or "N/A"
                ttl = record['ttl'] if record['ttl'] is not None else "None"
                static = record['static'] or "N/A"
                print(
                    f"{record_id:<15}{name:<20}{record_type:<10}{result:<30}{ttl:<6}{static:<6}"
                )

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
