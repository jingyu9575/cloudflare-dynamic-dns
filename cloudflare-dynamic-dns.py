import dns.exception
import dns.resolver
import argparse
import CloudFlare


def main():
    BASE_URL = 'https://api.cloudflare.com/client/v4/zones'

    parser = argparse.ArgumentParser(
        description='Cloudflare dynamic DNS updater.')
    parser.add_argument('-4', '--ipv4-record',
                        action='append', help='IPv4 DNS record name')
    parser.add_argument('-6', '--ipv6-record',
                        action='append', help='IPv6 DNS record name')
    parser.add_argument('-r', '--record', action='append',
                        help='IPv4/IPv6 DNS record name')
    parser.add_argument('-z', '--zone', required=True, help='Zone name')
    parser.add_argument('-e', '--email', help='Account email')
    parser.add_argument('-k', '--apikey', help='Account API key')
    args = parser.parse_args()

    cloudflare = CloudFlare.CloudFlare(email=args.email, token=args.apikey)

    zone_id = None

    def load_zone_id():
        nonlocal zone_id
        if zone_id is not None:
            return
        zone_id = cloudflare.zones.get(params={'name': args.zone})[0]['id']

    def nslookup(host, rdtype, nameserver=None):
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 8
        if nameserver:
            resolver.nameservers = [nameserver]
        return [r.address for r in resolver.query(host, rdtype)]

    MY_IP_NAMESERVERS = {
        'A': '208.67.222.222',
        'AAAA': '2620:0:ccc::2',
    }

    def load_my_ip(rdtype):
        return nslookup('myip.opendns.com', rdtype, MY_IP_NAMESERVERS[rdtype])[0]

    if args.ipv4_record or args.record:
        ip = load_my_ip('A')

    CLOUDFLARE_NAMESERVER = nslookup('woz.ns.cloudflare.com', 'A')[0]

    def update(rdtype, records):
        if not records:
            return
        my_ip = load_my_ip(rdtype)
        for record in records:
            full_name = record + '.' + args.zone
            try:
                current_ip = nslookup(full_name, rdtype, CLOUDFLARE_NAMESERVER)
                if current_ip == my_ip:
                    return
            except dns.exception.DNSException:
                pass
            load_zone_id()
            dns_records = cloudflare.zones.dns_records.get(
                zone_id, params={'name': full_name, 'type': rdtype})
            if dns_records:
                for dns_record in dns_records:
                    dns_record['content'] = my_ip
                    cloudflare.zones.dns_records.put(
                        zone_id, dns_record['id'], data=dns_record)
            else:
                cloudflare.zones.dns_records.post(zone_id, data={
                    "type": rdtype,
                    "name": record,
                    "content": my_ip,
                    'ttl': 300,
                })

    update('A', (args.ipv4_record or []) + (args.record or []))
    update('AAAA', (args.ipv6_record or []) + (args.record or []))


if __name__ == "__main__":
    main()
