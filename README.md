<div id="top"></div>

<div id="top" align="center">

[![Contributors][contributors-shield]](https://github.com/franckferman/The_Network_Calculator_Toolbox/graphs/contributors)
[![Forks][forks-shield]](https://github.com/franckferman/The_Network_Calculator_Toolbox/network/members)
[![Stargazers][stars-shield]](https://github.com/franckferman/The_Network_Calculator_Toolbox/stargazers)
[![Issues][issues-shield]](https://github.com/franckferman/The_Network_Calculator_Toolbox/issues)
[![MIT License][license-shield]](https://github.com/franckferman/The_Network_Calculator_Toolbox/blob/main/LICENSE)
[![LinkedIn][linkedin-shield]](https://www.linkedin.com/in/fferman42)

</div>

<br />
<div align="center">
  <a href="https://github.com/franckferman/The_Network_Calculator_Toolbox">
    <img src="https://raw.githubusercontent.com/franckferman/The_Network_Calculator_Toolbox/main/img/logo.png" alt="Logo" width="140" height="130">
  </a>

<h3 align="center">The Network Calculator Toolbox</h3>

  <p align="center">
    The Network Calculator Toolbox is a Python3 tool allowing the realization of numerous calculations dedicated essentially to the network administration.
    <br />
    <a href="https://github.com/franckferman/The_Network_Calculator_Toolbox/blob/main/README.md"><strong>Explore the full documentation »</strong></a>
    <br />
    <br />
    <a href="https://asciinema.org/a/Rjq1ZgtQ78G02PNWNwdGWsMuw">View Demo</a>
    .
    <a href="https://github.com/franckferman/The_Network_Calculator_Toolbox/issues">Report Bug</a>
    ·
    <a href="https://github.com/franckferman/The_Network_Calculator_Toolbox/issues">Request Feature</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#tested-on">Tested on</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

[![asciicast](https://asciinema.org/a/Rjq1ZgtQ78G02PNWNwdGWsMuw.svg)](https://asciinema.org/a/Rjq1ZgtQ78G02PNWNwdGWsMuw)

The goal of this project is not to reinvent the wheel. But to my knowledge, no similar tool of this type as complete in Python existed on Github before this one.

Of course, individually, on the whole, these projects all exist, but I haven't found a simple and quick tool to use to perform classic tasks that a network administrator for example would have to perform.

I also did this project to consolidate some of my Python knowledge. It is true that learning is much easier (and deeper) with practical cases, so a project like this was in my opinion a good way to do it although quite simple but useful for me. Link the useful to the pleasant, consolidate my knowledge in Python, make a tool that will be useful to me. Also, as a computer science teacher, this tool will be useful for some of my students.

At the end of the day, the ultimate goal is to achieve time savings and ease of use. 

Also, I prefer to have my tool (regrouping multiple tools) locally, allowing me to do these tasks, rather than being dependent on multiple tools, being in addition on Internet sites.

The Network Calculator Toolbox is a tool allowing the realization of numerous calculations dedicated essentially to the network administration.

<br />Here is an overview of the available features:

- Convert an IP address and its mask (or CIDR) into a binary number.

- Convert an IP address (in decimal format) to a binary number.

- Convert an IP address (in binary number) to a decimal format.

- Convert a decimal number into a binary number.

- Convert a binary number into a decimal number.

- Convert a decimal number into a hexadecimal number.

- Convert a hexadecimal number into a decimal number.

- Calculate the CIDR of a mask.

- Calculate the mask from a CIDR.

- Convert a mask to wildcard mask.

- Convert a wildcard mask to a mask.

- CONVERT A CIDR TO WILDCARD MASK.

- Convert a wildcard mask to a mask.

Many other features are under development.

<p align="right">(<a href="#top">back to top</a>)</p>

### Tested On

This program has been tested on different operating systems:
* - [x] [Microsoft Windows 11 Pro, Python 3](https://www.microsoft.com/en-us/windows/get-windows-11)
* - [x] [Microsoft Windows 10 Pro, Python 3](https://www.microsoft.com/en-us/d/windows-10-pro/df77x4d43rkt?activetab=pivot:overviewtab)
* - [x] [Debian 11, Python 3](https://www.debian.org/)

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

This course is not intended to teach you how to use your Windows or Linux terminal. However, I will simply show you (for beginners) how to easily download my script and run it.

I don't think a tutorial would be very useful to teach you how to use the script as it was designed to be naturally intuitive, you should be able to find your way around quite easily.

### Prerequisites

Please note that my script must be placed where you want your machines to be stored.

* For example, on Windows, if you want them to be in your C:\ directory, issue the following command from your PowerShell terminal:
```sh
Start-BitsTransfer -Source https://raw.githubusercontent.com/franckferman/The_Network_Calculator_Toolbox/main/main.py -Destination "C:\" -DisplayName "The_Network_Calculator_Toolbox - Downloading function - Franck FERMAN." -Description "Downloading the script."
```

Of course, you can change the desired destination path. To do this, you just have to change the argument of the -Destination parameter.

* For example:
```sh
Start-BitsTransfer -Source https://raw.githubusercontent.com/franckferman/The_Network_Calculator_Toolbox/main/main.py -Destination "D:\" -DisplayName "The_Network_Calculator_Toolbox - Downloading function - Franck FERMAN." -Description "Downloading the script."
```

* For example, on Linux, if you want them to be in your home folder, issue the following command from your terminal:
```sh
curl https://raw.githubusercontent.com/franckferman/The_Network_Calculator_Toolbox/main/main.py -o ~/main.py
```

Of course, you can change the desired destination path. To do this, you just have to change the argument of the -o parameter.

* For example:
```sh
mkdir ./The_Network_Calculator_Toolbox&&curl https://raw.githubusercontent.com/franckferman/The_Network_Calculator_Toolbox/main/main.py -o ./The_Network_Calculator_Toolbox/main.py
```

<!-- USAGE EXAMPLES -->
## Usage

* On Windows, to run the program, simply go to the program installation path and run the program:
```sh
Set-Location -Path "C:\";python3.exe;.\main.py
```

* On Linux, to run the program, simply go to the program installation path and run the program:
```sh
cd ~&&python3 ./main.py
```

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Project Link: [https://github.com/franckferman/The_Network_Calculator_Toolbox](https://github.com/franckferman/The_Network_Calculator_Toolbox)

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/franckferman/The_Network_Calculator_Toolbox.svg?style=for-the-badge
[contributors-url]: https://github.com/franckferman/The_Network_Calculator_Toolbox/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/franckferman/The_Network_Calculator_Toolbox.svg?style=for-the-badge
[forks-url]: https://github.com/franckferman/The_Network_Calculator_Toolbox/network/members
[stars-shield]: https://img.shields.io/github/stars/franckferman/The_Network_Calculator_Toolbox.svg?style=for-the-badge
[stars-url]: https://github.com/franckferman/The_Network_Calculator_Toolbox/stargazers
[issues-shield]: https://img.shields.io/github/issues/franckferman/The_Network_Calculator_Toolbox.svg?style=for-the-badge
[issues-url]: https://github.com/franckferman/The_Network_Calculator_Toolbox/issues
[license-shield]: https://img.shields.io/github/license/franckferman/The_Network_Calculator_Toolbox.svg?style=for-the-badge
[license-url]: https://github.com/franckferman/The_Network_Calculator_Toolbox/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/fferman42
[product-screenshot]: images/screenshot.png
