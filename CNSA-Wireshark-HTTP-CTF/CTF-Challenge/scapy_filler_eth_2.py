#!/usr/bin/env python3

from scapy.all import *
import random, time, sys, os, string

# --- Parameters you can change ---
DEFAULT_N = 1700
BASE_MAC = "02:11:22:%02x:%02x:%02x"  # template
SRC_SUBNETS = {
    "arp": "10.10.%d.%d",
    "icmp_src": "10.1.%d.%d",
    "icmp_dst": "10.2.%d.%d",
    "dns_src": "10.3.%d.%d",
    "dns_srv": "10.254.0.53",
    "http_client": "10.4.%d.%d",
    "http_server": "10.5.%d.%d",
    "tls_client": "10.6.%d.%d",
    "tls_server": "10.7.%d.%d",
}

def rand_label(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def rand_payload_bytes(n=24):
    return os.urandom(n)

HTTP_HOSTS = ["cdn.example.net","images.example.org","api.example.com","static.example.test"]
HTTP_PATHS = ["/", "/assets/img.png", "/api/health", "/index.html", "/search?q=test"]
USER_AGENTS = ["Mozilla/5.0 (X11; Linux x86_64) filler/1.0", "curl/7.79.1", "Wget/1.21.1", "python-requests/2.31.0"]

def mac_for(i):
    a = (i >> 16) & 0xff
    b = (i >> 8) & 0xff
    c = i & 0xff
    return BASE_MAC % (a, b, c)

def ipv4_for(pattern, i):
    return pattern % (i % 10, ((i * 7) % 240) + 1)

def arp_pair(i):
    src_mac = mac_for(i)
    req_ip = ipv4_for(SRC_SUBNETS["arp"], i)
    target_ip = "10.10.%d.1" % (i % 10)
    # Request (broadcast)
    ether_req = Ether(dst="ff:ff:ff:ff:ff:ff", src=src_mac, type=0x0806)
    arp_req = ARP(hwsrc=src_mac, psrc=req_ip, hwdst="00:00:00:00:00:00", pdst=target_ip, op=1)
    # Reply (from target)
    reply_mac = "02:aa:bb:%02x:%02x:%02x" % ((i >> 8) & 0xff, (i >> 4) & 0xff, i & 0xff)
    ether_rep = Ether(dst=src_mac, src=reply_mac, type=0x0806)
    arp_rep = ARP(hwsrc=reply_mac, psrc=target_ip, hwdst=src_mac, pdst=req_ip, op=2)
    return [ether_req/arp_req, ether_rep/arp_rep]

def icmp_pair(i):
    client_mac = mac_for(i+1)
    server_mac = "02:cc:dd:%02x:%02x:%02x" % (((i+3)>>8)&0xff, ((i+3)>>4)&0xff, (i+3)&0xff)
    src = ipv4_for(SRC_SUBNETS["icmp_src"], i)
    dst = ipv4_for(SRC_SUBNETS["icmp_dst"], i)


    icmp_id  = random.randint(0, 0xffff)
    icmp_seq = random.randint(0, 0xffff)
    payload  = rand_payload_bytes(random.randint(16, 48))  # binary (non-readable)
    ttl_req  = random.randint(40, 120)
    ttl_rep  = min(255, ttl_req + random.randint(0, 5))    # plausible reply TTL


    req = (
        Ether(src=client_mac, dst=server_mac, type=0x0800) /
        IP(src=src, dst=dst, ttl=ttl_req) /
        ICMP(type=8, id=icmp_id, seq=icmp_seq) /
        Raw(payload)
    )


    rep = (
        Ether(src=server_mac, dst=client_mac, type=0x0800) /
        IP(src=dst, dst=src, ttl=ttl_rep) /
        ICMP(type=0, id=icmp_id, seq=icmp_seq) /
        Raw(payload)
    )

    return [req, rep]


def dns_pair(i):
    client_mac = mac_for(i+2)
    server_mac = "02:ee:ff:%02x:%02x:%02x" % (((i+5)>>8)&0xff, ((i+5)>>4)&0xff, (i+5)&0xff)
    client_ip = ipv4_for(SRC_SUBNETS["dns_src"], i)
    server_ip = SRC_SUBNETS["dns_srv"]
    qname = f"{rand_label(random.randint(6,12))}."


    ether_q = Ether(src=client_mac, dst=server_mac, type=0x0800)
    ip_q = IP(src=client_ip, dst=server_ip)
    udp_q = UDP(sport=random.randint(20000,60000), dport=53)
    dns_q = DNS(id=random.randint(0,0xffff), rd=1, qd=DNSQR(qname=qname))

    ether_r = Ether(src=server_mac, dst=client_mac, type=0x0800)
    ip_r = IP(src=server_ip, dst=client_ip)
    udp_r = UDP(sport=53, dport=udp_q.sport)

    answer_ip = "10.200.%d.%d" % (i % 10, ((i*3) % 240) + 1)
    dns_r = DNS(id=dns_q.id, qr=1, aa=1, qdcount=1, ancount=1,
                qd=DNSQR(qname=qname),
                an=DNSRR(rrname=qname, type="A", rdata=answer_ip, ttl=300))
    return [ether_q/ip_q/udp_q/dns_q, ether_r/ip_r/udp_r/dns_r]


def http_flow(i):
    client_mac = mac_for(i+10)
    server_mac = "02:44:55:%02x:%02x:%02x" % (((i+7)>>8)&0xff, ((i+7)>>4)&0xff, (i+7)&0xff)
    cli_ip = ipv4_for(SRC_SUBNETS["http_client"], i)
    srv_ip = ipv4_for(SRC_SUBNETS["http_server"], i)
    sport = random.randint(20000,60000)
    dport = 80
    seq_c = random.randint(0,0xffffffff)
    seq_s = random.randint(0,0xffffffff)

    syn    = Ether(src=client_mac, dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="S", seq=seq_c)
    synack = Ether(src=server_mac, dst=client_mac)/IP(src=srv_ip,dst=cli_ip)/TCP(sport=dport,dport=sport,flags="SA",seq=seq_s, ack=seq_c+1)
    ack    = Ether(src=client_mac, dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="A", seq=seq_c+1, ack=seq_s+1)


    host = random.choice(HTTP_HOSTS)
    path = random.choice(HTTP_PATHS)
    ua = random.choice(USER_AGENTS)
    http_get_payload = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {ua}\r\nAccept: */*\r\n\r\n").encode()
    get_pkt = Ether(src=client_mac, dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="PA",seq=seq_c+1,ack=seq_s+1)/Raw(http_get_payload)


    if random.random() < 0.2:

        color = random.choice(["red","green","blue","purple"])
        body = (f"<html><body><h1 style='color:{color}'>Section {i}</h1><p>Response {rand_label(6)}</p></body></html>\r\n").encode()
    else:
        body = (f"<html><body><p>OK filler {rand_label(8)}</p></body></html>\r\n").encode()

    http_resp_headers = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n"
    )
    resp_payload = http_resp_headers + body

    resp_pkt = Ether(src=server_mac, dst=client_mac)/IP(src=srv_ip,dst=cli_ip)/TCP(sport=dport,dport=sport,flags="PA",seq=seq_s+1,ack=seq_c+1 + len(http_get_payload))/Raw(resp_payload)
    ack2 = Ether(src=client_mac, dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="A",seq=seq_c+1 + len(http_get_payload),ack=seq_s+1 + len(resp_payload))

    return [syn, synack, ack, get_pkt, resp_pkt, ack2]


def tls_flow(i):
    client_mac = mac_for(i+20)
    server_mac = "02:66:77:%02x:%02x:%02x" % (((i+9)>>8)&0xff, ((i+9)>>4)&0xff, (i+9)&0xff)
    cli_ip = ipv4_for(SRC_SUBNETS["tls_client"], i)
    srv_ip = ipv4_for(SRC_SUBNETS["tls_server"], i)
    sport = random.randint(20000,60000)
    dport = 443
    seq_c = random.randint(0,0xffffffff)
    seq_s = random.randint(0,0xffffffff)

    syn = Ether(src=client_mac,dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="S",seq=seq_c)
    synack = Ether(src=server_mac,dst=client_mac)/IP(src=srv_ip,dst=cli_ip)/TCP(sport=dport,dport=sport,flags="SA",seq=seq_s,ack=seq_c+1)
    ack = Ether(src=client_mac,dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="A",seq=seq_c+1,ack=seq_s+1)

    client_blob = os.urandom(random.randint(40,120))
    client_record = b"\x16\x03\x03" + len(client_blob).to_bytes(2,"big") + client_blob
    client_pkt = Ether(src=client_mac,dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="PA",seq=seq_c+1,ack=seq_s+1)/Raw(client_record)

    server_blob = os.urandom(random.randint(80,200))
    server_record = b"\x16\x03\x03" + len(server_blob).to_bytes(2,"big") + server_blob
    server_pkt = Ether(src=server_mac,dst=client_mac)/IP(src=srv_ip,dst=cli_ip)/TCP(sport=dport,dport=sport,flags="PA",seq=seq_s+1,ack=seq_c+1+len(client_record))/Raw(server_record)

    ack2 = Ether(src=client_mac,dst=server_mac)/IP(src=cli_ip,dst=srv_ip)/TCP(sport=sport,dport=dport,flags="A",seq=seq_c+1+len(client_record),ack=seq_s+1+len(server_record))
    return [syn, synack, ack, client_pkt, server_pkt, ack2]


def noise_pkt(i):
    mac = mac_for(i)
    ip = IP(src="172.16.%d.%d" % (i%10, ((i*5)%240)+1), dst="172.16.%d.%d" % ((i+1)%10, ((i*11)%240)+1))
    tcp = TCP(sport=random.randint(1024,60000), dport=random.choice([22,123,37,111,8080]), flags="PA", seq=random.randint(0,100000))
    return Ether(src=mac,dst="02:aa:bb:cc:dd:ee")/ip/tcp/b"."


def generate_packets(total):
    pkts = []
    i = 0
    while len(pkts) < total:
        r = random.random()

        if r < 0.08 and len(pkts) + 2 <= total:
            pkts.extend(arp_pair(i))

        elif r < 0.28 and len(pkts) + 2 <= total:
            pkts.extend(icmp_pair(i))

        elif r < 0.46 and len(pkts) + 2 <= total:
            pkts.extend(dns_pair(i))

        elif r < 0.76 and len(pkts) + 6 <= total:
            pkts.extend(http_flow(i))

        elif r < 0.88 and len(pkts) + 6 <= total:
            pkts.extend(tls_flow(i))
        else:
            pkts.append(noise_pkt(i))
        i += 1

    now = time.time()
    t = now
    for idx,p in enumerate(pkts):
        t += random.uniform(0.0005, 0.01)
        p.time = t
    return pkts

if __name__ == "__main__":
    N = DEFAULT_N
    if len(sys.argv) > 1:
        try:
            N = int(sys.argv[1])
        except:
            pass
    print("Generating", N, "packets to filler_realistic.pcap ...")
    pkts = generate_packets(N)
    wrpcap("filler_realistic.pcap", pkts)
    print("Wrote filler_realistic.pcap with", len(pkts), "packets")
