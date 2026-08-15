<div align="center">

<a href="https://github.com/franckferman/SysAdminToolbox">
  <img src="https://raw.githubusercontent.com/franckferman/SysAdminToolbox/stable/docs/github/graphical_resources/Logo-Without_background-SysAdminToolbox.png" alt="SysAdminToolbox logo" width="400">
</a>

*Network administration suite - calculations, diagnostics, and configuration helpers.*

Zero runtime Python dependencies. Standard library only.

[![Tests](https://github.com/franckferman/SysAdminToolbox/actions/workflows/tests.yml/badge.svg?branch=stable)](https://github.com/franckferman/SysAdminToolbox/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

## About

SysAdminToolbox is a self-contained CLI for day-to-day network administration. It brings address and subnet calculations, IPv6 and MAC utilities, diagnostics, vendor configuration helpers, and concise cheatsheets into one installable Python package.

- **Conversions** - Binary, decimal, hexadecimal, IPv4, masks, CIDR, and wildcards.
- **Address planning** - IPv4/IPv6 subnetting, VLSM, ranges, overlap checks, and supernets.
- **Diagnostics** - Ping, port checks, traceroute, DNS, WHOIS, TLS certificates, and HTTP headers.
- **Configuration** - VLAN and ACL generators for Cisco, Juniper, and Huawei.
- **Reference** - VLAN, ACL, firewall, routing, and NAT cheatsheets.
- **Automation** - Consistent JSON output, no-color mode, and an interactive REPL.

## Installation

Requires Python 3.9 or newer.

Run directly from a clone:

```bash
git clone https://github.com/franckferman/SysAdminToolbox.git
cd SysAdminToolbox
python3 src/SysAdminToolbox/SysAdminToolbox.py --version
```

Or install the command in an isolated environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
SysAdminToolbox --version
```

The calculations and socket-based checks use only the Python standard library. These optional diagnostics call operating-system tools when available:

| Command | System tool |
| --- | --- |
| `net ping`, `net pingsweep` | `ping` |
| `net traceroute`, `net traceroute-asn` | `traceroute` or `tracert` |
| `net whois` | `whois` |
| Advanced DNS and ASN lookups | `dig`, with `nslookup` fallback for record lookups |

## Usage

```text
SysAdminToolbox <command> <operation> [arguments] [--json] [--no-color]
```

Quick examples:

```bash
SysAdminToolbox subnet calc 192.168.1.42/24
SysAdminToolbox subnet vlsm 192.168.1.0/24 50 30 10
SysAdminToolbox convert ipinfo 192.168.1.42/24 --json
SysAdminToolbox ipv6 ula
SysAdminToolbox mac generate 5 cisco
SysAdminToolbox net dns example.com
SysAdminToolbox vendor vlan juniper 100 Guest ge-0/0/1 ge-0/0/2
```

Run `SysAdminToolbox --help` or `SysAdminToolbox <command> --help` for the built-in reference. Run `SysAdminToolbox -i` for the interactive REPL.

### Commands

| Command | Operations |
| --- | --- |
| `convert` (`c`) | `d2b`, `b2d`, `d2h`, `h2d`, `b2h`, `h2b`, `iptobin`, `bintoip`, mask/CIDR/wildcard conversions, `ipinfo` |
| `subnet` (`s`) | `calc`, `adv`, `vlsm`, `range`, `overlap`, `supernet` |
| `ipv6` (`v6`) | `expand`, `compress`, `tobin`, `type`, `subnet`, `ula` |
| `mac` (`m`) | `info`, `format`, `normalize`, `vendor`, `generate` |
| `net` (`n`) | Ping and sweeps, TCP/UDP checks, traceroute, DNS, WHOIS, TLS, HTTP headers, ARP, random ports |
| `vendor` (`v`) | `vlan`, `acl` |
| `cheat` (`cs`) | `vlan`, `acl`, `huawei`, `mikrotik`, `firewall`, `routing`, `nat` |

### Conversions and address planning

```bash
# Number and address formats
SysAdminToolbox convert d2b 42
SysAdminToolbox convert b2d 11111111
SysAdminToolbox convert c2m 24
SysAdminToolbox convert m2w 255.255.255.0
SysAdminToolbox convert ipinfo 192.168.1.42/24

# Subnets and allocation
SysAdminToolbox subnet calc 10.0.0.1 255.255.0.0
SysAdminToolbox subnet adv 192.168.1.0/24 26
SysAdminToolbox subnet adv 2001:db8::/32 48 --limit 32
SysAdminToolbox subnet vlsm 192.168.1.0/24 50 30 10
SysAdminToolbox subnet range 192.168.1.10 192.168.1.35
SysAdminToolbox subnet overlap 192.168.1.0/24 192.168.1.128/25
SysAdminToolbox subnet supernet 192.168.1.0/26 192.168.1.64/26
```

`subnet adv` reports the exact number of subnets but limits detailed rows to 256 by default. Use `--limit` to change the displayed detail without accidentally materializing billions of IPv6 networks.

### IPv6 and MAC utilities

```bash
SysAdminToolbox ipv6 expand 2001:db8::1
SysAdminToolbox ipv6 compress 2001:0db8:0000:0000:0000:0000:0000:0001
SysAdminToolbox ipv6 type fe80::1
SysAdminToolbox ipv6 subnet 2001:db8::/64
SysAdminToolbox ipv6 ula

SysAdminToolbox mac info AA:BB:CC:DD:EE:FF
SysAdminToolbox mac format aa:bb:cc:dd:ee:ff cisco
SysAdminToolbox mac normalize aabb.ccdd.eeff
SysAdminToolbox mac generate 5 colon
```

`mac vendor` extracts the OUI. It deliberately does not ship a stale vendor database; authoritative vendor resolution requires the current IEEE registry.

### Network diagnostics

```bash
# Reachability and TCP/UDP checks
SysAdminToolbox net ping 192.168.1.1
SysAdminToolbox net pingsweep 192.168.1.0/24
SysAdminToolbox net portscan 192.168.1.1 22 80 443
SysAdminToolbox net portscan-adv 192.168.1.1 top20 banner
SysAdminToolbox net portscan-udp 192.168.1.1 53 161
SysAdminToolbox net portscan-net 192.168.1.0/24 22
SysAdminToolbox net banner 192.168.1.1 80

# Routing, DNS, TLS, and HTTP
SysAdminToolbox net traceroute example.com
SysAdminToolbox net traceroute-asn example.com
SysAdminToolbox net dns example.com
SysAdminToolbox net dns-type example.com MX
SysAdminToolbox net dns-compare example.com 1.1.1.1 8.8.8.8
SysAdminToolbox net rdns 192.0.2.1
SysAdminToolbox net certcheck example.com
SysAdminToolbox net headers https://example.com
SysAdminToolbox net whois example.com

# Candidate ports are generated, not probed
SysAdminToolbox net random-ports 49152 65535 10
```

Network-wide operations are capped at 4096 hosts to prevent accidental memory or traffic spikes. Use diagnostic and scanning commands only on systems you administer or are authorized to test.

### Vendor helpers and cheatsheets

```bash
SysAdminToolbox vendor vlan cisco 10 Engineering Gi0/1 Gi0/2
SysAdminToolbox vendor vlan juniper 10 Engineering ge-0/0/1 ge-0/0/2
SysAdminToolbox vendor vlan huawei 100 MGMT GE0/0/1 GE0/0/2
SysAdminToolbox vendor acl cisco BLOCK deny tcp 192.168.1.0/24 any 0 443

SysAdminToolbox cheat vlan trunk
SysAdminToolbox cheat firewall nftables
SysAdminToolbox cheat routing ospf
SysAdminToolbox cheat nat cisco_pat
```

Generated configuration is a starting point. Review interface names, platform syntax, policy order, and change-control requirements before applying it.

### JSON and terminal output

`--json` works before or after the subcommand and returns valid JSON for every operation. Colors disable automatically when output is redirected; `--no-color` and the `NO_COLOR` environment variable disable them explicitly.

```bash
SysAdminToolbox --json subnet calc 10.0.0.0/8
SysAdminToolbox subnet calc 10.0.0.0/8 --json | jq '.first_host'
SysAdminToolbox --no-color ipv6 type fd00::1
```

## Tests

The standard-library test suite covers calculations, validation, every deterministic CLI operation, JSON behavior, vendor output, command parsers, and loopback-only network checks.

```bash
python3 -m compileall -q src
python3 -m unittest discover -s tests -v
```

## Contributing

Issues and pull requests are welcome. Include a focused test for behavior changes and keep runtime code dependency-free.

## License

SysAdminToolbox is available under the [MIT License](LICENSE).

## Contact

Franck Ferman - [GitHub](https://github.com/franckferman) - [contact@franckferman.fr](mailto:contact@franckferman.fr)
