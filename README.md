<div id="top"></div>

[![Contributors][contributors-shield]](https://github.com/franckferman/PowerNest/graphs/contributors)
[![Forks][forks-shield]](https://github.com/franckferman/PowerNest/network/members)
[![Stargazers][stars-shield]](https://github.com/franckferman/PowerNest/stargazers)
[![Issues][issues-shield]](https://github.com/franckferman/PowerNest/issues)
[![MIT License][license-shield]](https://github.com/franckferman/PowerNest/blob/main/LICENSE)

<br />
<div align="center">
  <a href="https://github.com/franckferman/PowerNest">
    <img src="https://raw.githubusercontent.com/franckferman/PowerNest/main/img/logo.png" alt="Logo" width="140" height="130">
  </a>

<h3 align="center">The Network Calculator Toolbox</h3>

  <p align="center">
    The Network Calculator Toolbox is a Python3 tool allowing the realization of numerous calculations dedicated essentially to the network administration.
    <br />
    <a href="https://github.com/franckferman/PowerNest/blob/main/README.md"><strong>Explore the full documentation »</strong></a>
    <br />
    <br />
    <a href="https://asciinema.org/a/89042M80fkodhk45SasDXn0Qu">View Demo</a>
    .
    <a href="https://github.com/franckferman/PowerNest/issues">Report Bug</a>
    ·
    <a href="https://github.com/franckferman/PowerNest/issues">Request Feature</a>
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

Control your Google Nest Mini with PowerShell.

<br />Here is an overview of the available features:

- Hey Google.
- Schedule an alarm.

Many other features are under development.

<p align="right">(<a href="#top">back to top</a>)</p>

### Tested On

This program has been tested on different operating systems:
* - [x] [Microsoft Windows 11 Pro, PowerShell](https://www.microsoft.com/en-us/windows/get-windows-11)
* - [x] [Microsoft Windows 10 Pro, Python 3](https://www.microsoft.com/en-us/d/windows-10-pro/df77x4d43rkt?activetab=pivot:overviewtab)
* - [x] [Microsoft Windows PowerShell 7.2.2](https://microsoft.com/powershell)
* - [x] [Microsoft Windows PowerShell 5.1.22000.282](https://microsoft.com/powershell)

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

This course is not intended to teach you how to use PowerShell. However, I will simply show you (for beginners) how to easily download my script with PowerShell and run it.

I don't think a tutorial would be very useful to teach you how to use the script as it was designed to be naturally intuitive, you should be able to find your way around quite easily.

### Prerequisites

Please note that my script must be placed where you want your machines to be stored.

* For example, if you want them to be in your C:\ directory, issue the following command from your PowerShell terminal:
```sh
Start-BitsTransfer -Source https://raw.githubusercontent.com/franckferman/hyper-v_toolbox/main/hyper-v_toolbox.ps1 -Destination "C:\" -DisplayName "Hyper-V_Toolbox - Downloading function - Franck FERMAN." -Description "Downloading the script."
```

Of course, you can change the desired destination path. To do this, you just have to change the argument of the -Destination parameter.

* For example:
```sh
Start-BitsTransfer -Source https://raw.githubusercontent.com/franckferman/hyper-v_toolbox/main/hyper-v_toolbox.ps1 -Destination "D:\" -DisplayName "Hyper-V_Toolbox - Downloading function - Franck FERMAN." -Description "Downloading the script."
```

<!-- USAGE EXAMPLES -->
## Usage

* To run the script, simply go to the script installation path and run the PowerShell script (Administrator rights are required):
```sh
Set-Location -Path "C:\";Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force;.\hyper-v_toolbox.ps1
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

Project Link: [https://github.com/franckferman/PowerNest](https://github.com/franckferman/PowerNest)

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/franckferman/PowerNest.svg?style=for-the-badge
[contributors-url]: https://github.com/franckferman/PowerNest/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/franckferman/PowerNest.svg?style=for-the-badge
[forks-url]: https://github.com/franckferman/PowerNest/network/members
[stars-shield]: https://img.shields.io/github/stars/franckferman/PowerNest.svg?style=for-the-badge
[stars-url]: https://github.com/franckferman/PowerNest/stargazers
[issues-shield]: https://img.shields.io/github/issues/franckferman/PowerNest.svg?style=for-the-badge
[issues-url]: https://github.com/franckferman/PowerNest/issues
[license-shield]: https://img.shields.io/github/license/franckferman/PowerNest.svg?style=for-the-badge
[license-url]: https://github.com/franckferman/PowerNest/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/fferman42
[product-screenshot]: images/screenshot.png
