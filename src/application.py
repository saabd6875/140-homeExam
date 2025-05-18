import socket 
import sys 
import time
import struct
import argparse
from datetime import datetime


# ---constants and configurations

PACKET_SIZE = 1000 #total size of each packet in bytes
TIMEOUT = 0.4  # 400 ms timeout
HEADER_SIZE = 8  # fixed header size in bytes
TRANSFERRED_DATA_SIZE = PACKET_SIZE - HEADER_SIZE #max data per packet
WINDOW_SIZE = 3  # sliding window size (client)
MAX_SERVER_WINDOW = 15  # max window size server accpts 

# some flag data
SYN = 1 << 3 # value 8 = 1000
ACK = 1 << 2 # value 4 = 0100
FIN = 1 << 1 # value 2 = 0010

# the header is 8 bytes: this gives 2 bytes to (seq, ack, flags, win)
header_format = '!HHHH' # Network byte order, four unsigned shorts 

#some utility / important functions 


""" 
Discription: 
constructs a packet by packing a header and attching optional data 
arguments:
seq- sequence number
ack- acknowledgment number
flags - bitwise combination of SYN, ACK, FIN
win- advertised window size 
data- bytes of file content (default is empty)
Returns: 
- the full binary packet 
"""
def create_packet(seq, ack, flags, win, data=b''):
    header = struct.pack(header_format, seq, ack, flags, win)
    return header + data


"""
Discription: 
unacks a binary header into individual fields
arguments: 
header: first 8 bytes of the packet 
Returns:
- tuple: (seq, ack, flags, win)
"""
def parse_header(header):
    return struct.unpack(header_format, header)

"""
Discription:
parses the entire packet into header fields and data
arguments: 
packet: full binary packet
Returns: 
- tuple: (seq, ack, flags, win, data)
"""
def parse_packet(packet):
    header = packet[:HEADER_SIZE]
    data = packet[HEADER_SIZE:]
    seq, ack, flags, win = parse_header(header)
    return seq, ack, flags, win, data


"""
Discription:
extraacts individual SYN, ACK, and FIN flags from a flag byte
Arguments:
flags: integer represeing combined flag
Returns: 
- tuple: ( syn, ack, fin) as either 0 or flag value 
"""
def parse_flags(flags):
    syn = flags & SYN
    ack = flags & ACK
    fin = flags & FIN
    return syn, ack , fin


#this is for returning the current time in specified format 
def timestamp():
    return datetime.now().strftime('%H:%M:%S.%f')
 


# Discription: creates and returns a UDP socket with timeout set
def createSocket(): 
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(TIMEOUT)
    return s


# client mode  - sending a file 

"""
Discription: handles the full client-side file sending process including->
- connection establishment 
- reliable data transfer
- and connection teardown 

Arguments:
- filename: file to be sent 
- server_ip: destination ip
- server_port: destination port

Input/output parameters:
- uses a sliding window wih retransmission on timeout- Go-Back-N logic

Returns: none

Exceptions:
- handles FileNotFounError if the file does not exist 
- handles socket.timeout during handsahke and data transfer
"""


def send_file(filename, server_ip, server_port):
    global WINDOW_SIZE
    sock = createSocket()
    


    # three way handshake - connection establishment phase

    print("\nConnection establishing:\n")
    sock.sendto(create_packet(1, 0, SYN, WINDOW_SIZE), (server_ip,server_port))
    print("SYN packet is sent")

    try:
        data, _ = sock.recvfrom(PACKET_SIZE)
        _, ack, flags, server_window , payload = parse_packet(data)

        if payload == b"REJECT":
            print("Server rejected connection: window size too large.")
            sock.close()
            return

        syn, ack_flag, _ = parse_flags(flags)
        if syn and ack_flag:
            print("SYN-ACK packet is received")

            #checking if server allows the requested window size
            if WINDOW_SIZE > server_window:
                print(f"Client window size {WINDOW_SIZE} exceeds server max window {server_window}. Aborting.")
                sock.close()
                return
            else:
                WINDOW_SIZE = min(WINDOW_SIZE, server_window)    
            sock.sendto(create_packet(2, ack, ACK, WINDOW_SIZE),(server_ip,server_port))
            print("ACK packet is sent")
            print("Connection established ready")
        else:
            print(f"unexpected flags in SYN-ACK: flags= {flags}")
            return
    except socket.timeout:
        print("Timeout waiting for SYN-ACK")
        return
    
    #Data transfer 
    print("Data transfer:\n")
    seq = 1
    window = []
    sent_time = {}
    packets = {}

    try:
        with open(filename, 'rb') as f:
            eof = False # end of file 
            while not eof or window:
                while len(window) < WINDOW_SIZE and not eof:
                    data = f.read(TRANSFERRED_DATA_SIZE)
                    if not data:
                        eof = True
                        break
                    pkt = create_packet(seq, 0, 0, 0, data)
                    packets[seq] = pkt 
                    sock.sendto(pkt, (server_ip,server_port))
                    window.append(seq)
                    sent_time[seq] = time.time()
                    print( f"{timestamp()} -- packet with seq = {seq} is sent, sliding window = {window}")
                    seq += 1

                try:
                    ack_pkt, _ = sock.recvfrom(PACKET_SIZE)
                    _ , ack_num, flags, _ , _ = parse_packet(ack_pkt)
                    _, ack_flag, _ = parse_flags(flags)
                    if ack_flag:
                        acked_seq = ack_num - 1
                        if acked_seq in window:
                            print(f"{timestamp()} -- ACK for packet = {acked_seq} is recieved")
                            while window and window[0] <= acked_seq:
                                window.pop(0)
                except socket.timeout:
                    # Go-Back- N styke: retransmit all unacknowldged packets in the window
                    print(f"{timestamp()} -- RTO occurred")
                    for s in window:
                        if time.time() - sent_time[s] > TIMEOUT:
                            print(f"{timestamp()} -- retransmitting packet with seq ={s}")
                            sock.sendto(packets[s],(server_ip,server_port))
                            sent_time[s] = time.time()
    except FileNotFoundError:
        print(f"ERROR: file '{filename}' not found.")
        sock.close()
        return                  

            
    print("DATA TRANSFER FINISHED\n")
    print("File sent successfully.")
    #connection teardown -- sending FIN
    
    print("Connection teardown \n")
    sock.sendto(create_packet(seq, 0, FIN, 0),(server_ip, server_port))
    print("fin packet sent \n")
    try:
        fin_ack, _= sock.recvfrom(PACKET_SIZE)
        _,_,flags, _, _ = parse_packet(fin_ack)
        _, ack_flag, _ = parse_flags(flags)
        if ack_flag:
            print("FIN PACKET IS RECIEVED ")
    except socket.timeout:
        print("Timeout waiting for FIN ACK")
    print ("connection closes")
    
    sock.close()
    
    
# --- server : receive files
"""
discription: 
handles the server logic for receiving a file 
handshake, receiving packets with sequence checking and teardown.
Arguments:
- listenPort: port numer to listen to
- discard_seq: sequence number to simulate controlled packet drop(-1 = none)
Returns: none
""" 

def receive_file(listenPort, discard_seq):
    sock = createSocket()
    sock.bind(('', listenPort))

    print ("waiting for client to connect\n")

    
    #Handshake first -- connection establishment
    while True:
        try:
            data, client = sock.recvfrom(PACKET_SIZE)
            seq, _, flags, client_window, _ = parse_packet(data)
            syn, _, _ = parse_flags(flags)
            if syn:
                print("SYN packet is received")

                if client_window > MAX_SERVER_WINDOW:
                    print(f"Client's window size ({client_window}) exceeds server limit ({MAX_SERVER_WINDOW}). closing..")
                    reject_msg = b"REJECT"
                    sock.sendto(create_packet(0,0,0,0, reject_msg), (client))
                    sock.close()
                    return
                
                #Else the code runs and sends a syn-ack packet
                sock.sendto(create_packet(0, seq + 1, SYN | ACK, MAX_SERVER_WINDOW), client)
                print("SYN-ACK packet is sent")
                break
        except socket.timeout:
            continue

    while True:
        try:
            data, _ = sock.recvfrom(PACKET_SIZE)
            _, _, flags, _, _ = parse_packet(data)
            _, ack_flag, _ =parse_flags(flags)
            if ack_flag:
                print("ACK FLAG IS RECIEVED\n")
                print("connection esablished\n ")
                break
        except socket.timeout:
            continue

    
    #-- data reception
    

    #For testing purposes, the received file is saved as 'received.jpg'.
    """ 
    This can be upgraded to dynamic naming by sending the filename in a
    special metadata packet before the file transfer begins.
    """
    output_filename="received.jpg"
    f = open(output_filename, 'wb')
    expected_seq = 1
    total_bytes = 0
    start_time = time.time()

    while True:
        try:
            pkt, client = sock.recvfrom(PACKET_SIZE)
            seq, _, flags, client_win, data = parse_packet(pkt)
            _, _, fin = parse_flags(flags)

            if fin:
                print ("\n fin flag is received ")
                sock.sendto(create_packet(0,seq+1,ACK,0), client)
                print ("FIN ACK packet is sent ")
                break

            if seq == discard_seq:
                print(f"{timestamp()} -- simulated drop of packet {seq}")
                discard_seq = -1 #only drop once
                continue

            if seq == expected_seq:
                f.write(data)
                total_bytes += PACKET_SIZE  # this will calcuate the data + header for the throughput 
                print(f"{timestamp()} -- packet {seq} is received")
                sock.sendto(create_packet(0, seq + 1, ACK, 0), client)
                print(f"{timestamp()} -- sending ack for the received {seq}")
                expected_seq += 1
            else:
                print(f"{timestamp()} -- out of order packet {seq} is received")
                continue
        except socket.timeout:
            continue

    f.close()

    end_time = time.time()
    throughput = (total_bytes * 8)/ ((end_time - start_time)* 1_000_000)
    print(f"\nThe throughput is {throughput:.2f} Mbps")
    print("connection closes")
    sock.close()


# -- main function 
"""
discription: 
parses command-line arguments and runs the program in client or server mode.

Arguments:
Role: client or server
-- additioanl options like file, IP, port, window, discard sequence
Returns: none
"""
def main():
    parser = argparse.ArgumentParser(description="DRTP File Transfer")
    parser.add_argument("role", choices=['client', 'server'], help="Run as client or server")
    parser.add_argument("--file", help="File to send (client only)")
    parser.add_argument("--ip", help="Server IP for client")
    parser.add_argument("--port", type=int, default=9000, help="Port number")
    parser.add_argument("--window", type=int, default=3, help="Window size (client only)")
    parser.add_argument("--discard", "-d", type= int, help="Simulate dropping a packet with this sequence number (server only)")

    args = parser.parse_args()

    if args.role == "client":
        if not args.ip or not args.file:
            print("Client mode requires --ip argument and --file argument")
            sys.exit(1)
        global WINDOW_SIZE
        WINDOW_SIZE = args.window if hasattr(args,"window") else 3
        send_file(args.file, args.ip, args.port)

    elif args.role == "server":
        discard_seq = args.discard if args.discard is not None else -1
        receive_file(args.port, args.discard)

# Entry point
if __name__ == "__main__":
    main()