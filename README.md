<div id="top" align="center">

<!-- Shields Header -->
[![Contributors][contributors-shield]](https://github.com/franckferman/SysAdminToolbox/graphs/contributors)
[![Forks][forks-shield]](https://github.com/franckferman/SysAdminToolbox/network/members)
[![Stargazers][stars-shield]](https://github.com/franckferman/SysAdminToolbox/stargazers)
[![Issues][issues-shield]](https://github.com/franckferman/SysAdminToolbox/issues)
[![License][license-shield]](https://github.com/franckferman/SysAdminToolbox/blob/stable/LICENSE)

<!-- Logo -->
<a href="https://github.com/franckferman/SysAdminToolbox">
  <img src="https://raw.githubusercontent.com/franckferman/SysAdminToolbox/stable/docs/github/graphical_resources/Logo-Without_background-SysAdminToolbox.png" alt="SysAdminToolbox Logo" width="auto" height="auto">
</a>

<!-- Title & Tagline -->
<h3 align="center">🌐 SysAdminToolbox</h3>
<p align="center">
    <em>Versatile tool designed for network administration, providing a wide range of useful calculations.</em>
    <br>
    Network Calculations and Conversions Tool.
</p>

<!-- Links & Demo -->
<p align="center">
    <a href="https://github.com/franckferman/SysAdminToolbox/blob/stable/README.md" class="button-style"><strong>📘 Explore the full documentation</strong></a>
    ·
    <a href="https://github.com/franckferman/SysAdminToolbox/issues">🐞 Report Bug</a>
    ·
    <a href="https://github.com/franckferman/SysAdminToolbox/issues">🛠️ Request Feature</a>
</p>

</div>

## 📜 Table of Contents

<details open>
  <summary><strong>Click to collapse/expand</strong></summary>
  <ol>
    <li><a href="#-about">📖 About</a></li>
    <li><a href="#-installation">🛠️ Installation</a></li>
    <li><a href="#-usage">🎮 Usage</a></li>
    <li><a href="#-troubleshooting">❗ Troubleshooting</a></li>
    <li><a href="#-contributing">🤝 Contributing</a></li>
    <li><a href="#-star-evolution">🌠 Star Evolution</a></li>
    <li><a href="#-license">📜 License</a></li>
    <li><a href="#-contact">📞 Contact</a></li>
  </ol>
</details>

## 📖 About

**SysAdminToolbox:** _Versatile tool designed for network administration, providing a wide range of useful calculations._

The ultimate goal of the SysAdminToolbox is to save time and streamline the network administration process. By consolidating multiple tools into a single, locally-hosted application, users can quickly and easily perform a wide range of network calculations without the need for external resources.

Whether you are an experienced network administrator or just getting started in the field, the SysAdminToolbox offers a convenient and powerful solution for all your network calculation needs.

### ✨ List of features

* - [x] Convert decimal to binary (`--dectobin`, `--dec2bin`, `--d2b`)
* - [x] Convert binary to decimal (`--bintodec`, `--bin2dec`, `--b2d`)
* - [x] Convert decimal to hexadecimal (`--dectohex`, `--dec2hex`, `--d2h`)
* - [x] Convert hexadecimal to decimal (`--hextodec`, `--hex2dec`, `--h2d`)
* - [x] Convert binary to hexadecimal (`--bintohex`, `--bin2hex`, `--b2h`)
* - [x] Convert hexadecimal to binary (`--hextobin`, `--hex2bin`, `--h2b`)
* - [x] Convert IP address to binary (`--iptobin`, `--ip2bin`, `--i2b`)
* - [x] Convert binary to IP address (`--bintoip`, `--bin2ip`, `--b2i`)
* - [x] Convert subnet mask to binary (`--masktobin`, `--mask2bin`, `--m2b`)
* - [x] Convert binary to subnet mask (`--bintomask`, `--bin2mask`, `--b2m`)
* - [x] Convert subnet mask to CIDR (`--masktocidr`, `--mask2cidr`, `--m2c`)
* - [x] Convert CIDR to subnet mask (`--cidrtomask`, `--cidr2mask`, `--c2m`)
* - [x] Convert subnet mask to wildcard (`--masktowildcard`, `--mask2wildcard`, `--m2w`)
* - [x] Convert wildcard to subnet mask (`--wildcardtomask`, `--wildcard2mask`, `--w2m`)
* - [x] Convert CIDR to wildcard (`--cidrtowildcard`, `--cidr2wildcard`, `--c2w`)
* - [x] Convert wildcard to CIDR (`--wildcardtocidr`, `--wildcard2cidr`, `--w2c`)
* - [x] Convert address (and optional mask) to binary (`--addrtobin`, `--addr2bin`, `--a2b`)
* - [x] Convert binary to address or mask (`--bintoaddr`, `--bin2addr`, `--b2a`)
* - [x] Calculate subnet details (`--subnetcalc`, `--subnet`, `--sc`)
* - [x] Calculate advanced subnet details (`--advancedsubnetcalc`, `--asc`)
* - [x] Calculate VLSM details for a network with required hosts (`--vlsmcalc`, `--vlsm`)
* - [x] Perform a DNS lookup on a dostable name (`--dnslookup`)
* - [x] Provide VLAN creation command help (`--vlanhelper`)
* - [x] Provide ACL creation command help (`--aclhelper`)
* - [x] Display VLAN cheat sheet (`--vlancheatsheet`)
* - [x] Display ACL cheat sheet (`--aclcheatsheet`)

<p align="center">
  <img src="https://raw.githubusercontent.com/franckferman/SysAdminToolbox/stable/docs/github/graphical_resources/Screenshot-SysAdminToolbox_Demo.png" alt="SysAdminToolbox Demo Screenshot" width="auto" height="auto">
</p>

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

## 🚀 Installation

Before diving into the installation process, ensure you meet the following prerequisites.

### Prerequisites

**Python 3**: Ensure Python 3 is installed on your system before initiating the installation process.

> ⚠️ **Note**: SysAdminToolbox has been rigorously tested with Python 3.11.2 on Linux (Debian) Windows (11). While it may function with other versions, compatibility is guaranteed only with these specific configurations.

### Installation methods

**Git clone the repository**:
```bash
git clone https://github.com/franckferman/SysAdminToolbox.git
```

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

## 🎮 Usage

Ensure you adapt your command according to how you've set up `SysAdminToolbox`.

### **Getting started**

Kick off with the built-in help to explore SysAdminToolbox's functionalities:

```bash
python3 src/SysAdminToolbox/SysAdminToolbox.py -h
```

### **Command examples**

#### 🔢 Binary and Hexadecimal Conversions:

| Task | Command |
| --- | --- |
| Convert decimal to binary | `python3 src/SysAdminToolbox/SysAdminToolbox.py --dectobin 42` |
| Convert binary to decimal | `python3 src/SysAdminToolbox/SysAdminToolbox.py --bintodec 101010` |
| Convert decimal to hexadecimal | `python3 src/SysAdminToolbox/SysAdminToolbox.py --dectohex 255` |
| Convert hexadecimal to decimal | `python3 src/SysAdminToolbox/SysAdminToolbox.py --hextodec ff` |
| Convert binary to hexadecimal | `python3 src/SysAdminToolbox/SysAdminToolbox.py --bintohex 101010` |
| Convert hexadecimal to binary | `python3 src/SysAdminToolbox/SysAdminToolbox.py --hextobin ff` |
| Convert IP address to binary | `python3 src/SysAdminToolbox/SysAdminToolbox.py --iptobin 192.168.1.1` |
| Convert binary to IP address | `python3 src/SysAdminToolbox/SysAdminToolbox.py --bintoip 11000000.10101000.00000001.00000001` |
| Convert subnet mask to binary | `python3 src/SysAdminToolbox/SysAdminToolbox.py --masktobin 255.255.255.0` |
| Convert binary to subnet mask | `python3 src/SysAdminToolbox/SysAdminToolbox.py --bintomask 11111111.11111111.11111111.00000000` |
| Convert address (and optional mask) to binary | `python3 src/SysAdminToolbox/SysAdminToolbox.py --addrtobin 192.168.0.1 255.255.255.0` |
| Convert binary to address or mask | `python3 src/SysAdminToolbox/SysAdminToolbox.py --bintoaddr 11000000.10101000.00000001.00000001` |

#### 🧮 Network Conversions:

| Task | Command |
| --- | --- |
| Convert subnet mask to CIDR | `python3 src/SysAdminToolbox/SysAdminToolbox.py --masktocidr 255.255.255.0` |
| Convert CIDR to subnet mask | `python3 src/SysAdminToolbox/SysAdminToolbox.py --cidrtomask 24` |
| Convert subnet mask to wildcard | `python3 src/SysAdminToolbox/SysAdminToolbox.py --masktowildcard 255.255.255.0` |
| Convert wildcard to subnet mask | `python3 src/SysAdminToolbox/SysAdminToolbox.py --wildcardtomask 0.0.0.255` |
| Convert CIDR to wildcard | `python3 src/SysAdminToolbox/SysAdminToolbox.py --cidrtowildcard 24` |
| Convert wildcard to CIDR | `python3 src/SysAdminToolbox/SysAdminToolbox.py --wildcardtocidr 0.0.0.255` |

#### 🌐 Network and Subnet Calculations:

| Task | Command |
| --- | --- |
| Calculate subnet details | `python3 src/SysAdminToolbox/SysAdminToolbox.py --subnetcalc 192.168.0.1 255.255.255.0` |
| Calculate advanced subnet details | `python3 src/SysAdminToolbox/SysAdminToolbox.py --advancedsubnetcalc 192.168.0.1/24 26` |
| Calculate VLSM details for a network with required hosts | `python3 src/SysAdminToolbox/SysAdminToolbox.py --vlsmcalc 192.168.0.0/24 50 30 10 5` |

#### 🔍 Networking tools:
| Task | Command |
| --- | --- |
| Perform a DNS lookup on a dostable name | `python3 src/SysAdminToolbox/SysAdminToolbox.py --dnslookup example.com` |

#### 🕵️ Configuration Helpers:
| Task | Command |
| --- | --- |
| Provide VLAN creation command help | `python3 src/SysAdminToolbox/SysAdminToolbox.py --vlanhelper cisco 10 Engineering Gi0/1-15` |
| Provide ACL creation command help | `python3 src/SysAdminToolbox/SysAdminToolbox.py --aclhelper cisco ACL_NAME permit tcp 192.168.1.0/24 any` |

#### 📝 Cheat Sheets:
| Task | Command |
| --- | --- |
| Display VLAN cheat sheet | `python3 src/SysAdminToolbox/SysAdminToolbox.py --vlancheatsheet trunk` |
| Display ACL cheat sheet | `python3 src/SysAdminToolbox/SysAdminToolbox.py --aclcheatsheet creation` |

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

## 🔧 Troubleshooting

Encountering issues? Don't worry. If you come across any problems or have questions, please don't hesitate to submit a ticket for assistance: [Submit an issue on GitHub](https://github.com/franckferman/SysAdminToolbox/issues)

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

## 🤝 Contributing

We truly appreciate and welcome community involvement. Your contributions, feedback, and suggestions play a crucial role in improving the project for everyone. If you're interested in contributing or have ideas for enhancements, please feel free to open an issue or submit a pull request on our GitHub repository. Every contribution, no matter how big or small, is highly valued and greatly appreciated!

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

## 🌠 Star Evolution

Explore the star history of this project and see how it has evolved over time:

<a href="https://star-history.com/#franckferman/SysAdminToolbox&Timeline">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=franckferman/SysAdminToolbox&type=Timeline&theme=dark" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=franckferman/SysAdminToolbox&type=Timeline" />
  </picture>
</a>

Your support is greatly appreciated. We're grateful for every star! Your backing fuels our passion. ✨

## 📚 License

This project is licensed under the GNU Affero General Public License, Version 3.0. For more details, please refer to the LICENSE file in the repository: [Read the license on GitHub](https://github.com/franckferman/SysAdminToolbox/blob/stable/LICENSE)

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

## 📞 Contact

[![ProtonMail][protonmail-shield]](mailto:contact@franckferman.fr) 
[![LinkedIn][linkedin-shield]](https://www.linkedin.com/in/franckferman)
[![Twitter][twitter-shield]](https://www.twitter.com/franckferman)

<p align="right">(<a href="#top">🔼 Back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/franckferman/SysAdminToolbox.svg?style=for-the-badge
[contributors-url]: https://github.com/franckferman/SysAdminToolbox/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/franckferman/SysAdminToolbox.svg?style=for-the-badge
[forks-url]: https://github.com/franckferman/SysAdminToolbox/network/members
[stars-shield]: https://img.shields.io/github/stars/franckferman/SysAdminToolbox.svg?style=for-the-badge
[stars-url]: https://github.com/franckferman/SysAdminToolbox/stargazers
[issues-shield]: https://img.shields.io/github/issues/franckferman/SysAdminToolbox.svg?style=for-the-badge
[issues-url]: https://github.com/franckferman/SysAdminToolbox/issues
[license-shield]: https://img.shields.io/github/license/franckferman/SysAdminToolbox.svg?style=for-the-badge
[license-url]: https://github.com/franckferman/SysAdminToolbox/blob/stable/LICENSE
[protonmail-shield]: https://img.shields.io/badge/ProtonMail-8B89CC?style=for-the-badge&logo=protonmail&logoColor=blueviolet
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=blue
[twitter-shield]: https://img.shields.io/badge/-Twitter-black.svg?style=for-the-badge&logo=twitter&colorB=blue
