# 3rd_Party Extensions - Rusys
# Copyright (C) 2026 Pro_Tool Project
# Developer: Ali A Alwahed
# Licensed under GPL-3.0-or-later

"""Operating-system download catalogue for Rusys.

Sections: Microsoft Windows (os.click fresh links — signed URLs are
re-issued at download time so they never expire), Linux (os.click direct
mirrors), Unix / BSD, and Maintenance and Recovery (medkit). Every leaf is
single-click: direct ISO download, background fresh-link resolve, or honest
browser fallback. No expiring signed URLs are stored.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional


@dataclass
class CatalogNode:
    name: str
    node_type: str = "leaf"
    compatibility: str = "x64"
    size_gb: float = 0.0
    downloads: int = 0
    latest_update: str = ""
    page_url: Optional[str] = None
    iso_url: Optional[str] = None
    notes: str = ""
    children: List["CatalogNode"] = field(default_factory=list)
    languages: Optional[Dict[str, str]] = None  # display name -> os.click lang code
    tags: List[str] = field(default_factory=list)
    osc_walk: Optional[Dict] = None  # {"os":..,"middle":[..],"archs":[..]} fresh-link spec

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def leaf_url(self) -> Optional[str]:
        return self.iso_url or self.page_url


DEFAULT_DATE = "2026-09-09"


WINDOWS = CatalogNode("Microsoft Windows", children=[
    CatalogNode("Windows XP Professional (2600.5512) [x86]", node_type="windows", compatibility="x86", size_gb=0.6, downloads=14324, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows XP SP3 (x86) \u2014 0.6GB, os.click MSDN genuine, 24 langs.",
        languages={"Arabic": "ar", "Chinese (Hong Kong SAR China)": "zh-hk", "Chinese (Simplified)": "zh-hans", "Chinese (Taiwan)": "zh-tw", "Czech": "cs", "Danish": "da", "Dutch": "nl", "English": "en", "Finnish": "fi", "French": "fr", "German": "de", "Greek": "el", "Hebrew": "he", "Hungarian": "hu", "Italian": "it", "Japanese": "ja", "Norwegian": "no", "Polish": "pl", "Portuguese (Brazil)": "pt-br", "Portuguese (Portugal)": "pt-pt", "Russian": "ru", "Spanish": "es", "Swedish": "sv", "Turkish": "tr"},
        osc_walk={"os": "Windows XP", "middle": ["2600.5512", "Professional"], "archs": ["x86"]}),
    CatalogNode("Windows Vista (SP2) [x64]", node_type="windows", compatibility="x64", size_gb=3.6, downloads=11879, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows Vista SP2 \u2014 3.6GB, os.click MSDN genuine, 36 langs.",
        languages={"Arabic": "ar", "Bulgarian": "bg", "Chinese (China)": "cn", "Chinese (Hong Kong SAR China)": "hk", "Chinese (Taiwan)": "tw", "Croatian": "hr", "Czech": "cs", "Danish": "da", "Dutch": "nl", "English": "en", "Estonian": "et", "Finnish": "fi", "French": "fr", "German": "de", "Greek": "el", "Hebrew": "he", "Hungarian": "hu", "Italian": "it", "Japanese": "ja", "Korean": "ko", "Latvian": "lv", "Lithuanian": "lt", "Norwegian": "no", "Polish": "pl", "Portuguese": "pt", "Portuguese (Portugal)": "pp", "Romanian": "ro", "Russian": "ru", "Serbian": "sr", "Slovak": "sk", "Slovenian": "sl", "Spanish": "es", "Swedish": "sv", "Thai": "th", "Turkish": "tr", "Ukrainian": "uk"},
        osc_walk={"os": "Windows Vista", "middle": ["6002.18005", "Multi-Edition"], "archs": ["x86", "x64"]}),
    CatalogNode("Windows 7 Ultimate (7601.17514) [x64]", node_type="windows", compatibility="x64", size_gb=3.1, downloads=128974, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows 7 Ultimate SP1 \u2014 3.1GB, os.click MSDN genuine, 36 langs.",
        languages={"Arabic": "ar", "Bulgarian": "bg", "Chinese (China)": "cn", "Chinese (Hong Kong SAR China)": "hk", "Chinese (Taiwan)": "tw", "Croatian": "hr", "Czech": "cs", "Danish": "da", "Dutch": "nl", "English": "en", "Estonian": "et", "Finnish": "fi", "French": "fr", "German": "de", "Greek": "el", "Hebrew": "he", "Hungarian": "hu", "Italian": "it", "Japanese": "ja", "Korean": "ko", "Latvian": "lv", "Lithuanian": "lt", "Norwegian": "no", "Polish": "pl", "Portuguese": "pt", "Portuguese (Portugal)": "pp", "Romanian": "ro", "Russian": "ru", "Serbian": "sr", "Slovak": "sk", "Slovenian": "sl", "Spanish": "es", "Swedish": "sv", "Thai": "th", "Turkish": "tr", "Ukrainian": "uk"},
        osc_walk={"os": "Windows 7", "middle": ["7601.17514", "Ultimate"], "archs": ["x86", "x64"]}),
    CatalogNode("Windows 8 (Multi-Edition) [x64]", node_type="windows", compatibility="x64", size_gb=3.3, downloads=13281, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows 8 \u2014 3.3GB, os.click MSDN genuine, 37 langs.",
        languages={"Arabic (Saudi Arabia)": "ar-sa", "Bulgarian (Bulgaria)": "bg-bg", "Chinese (China)": "zh-cn", "Chinese (Hong Kong SAR China)": "zh-hk", "Chinese (Taiwan)": "zh-tw", "Croatian (Croatia)": "hr-hr", "Czech (Czechia)": "cs-cz", "Danish (Denmark)": "da-dk", "Dutch (Netherlands)": "nl-nl", "English": "en", "English (United Kingdom)": "en-gb", "Estonian (Estonia)": "et-ee", "Finnish (Finland)": "fi-fi", "French (France)": "fr-fr", "German (Germany)": "de-de", "Greek (Greece)": "el-gr", "Hebrew (Israel)": "he-il", "Hungarian (Hungary)": "hu-hu", "Italian (Italy)": "it-it", "Japanese (Japan)": "ja-jp", "Korean (South Korea)": "ko-kr", "Latvian (Latvia)": "lv-lv", "Lithuanian (Lithuania)": "lt-lt", "Norwegian Bokm\u00e5l (Norway)": "nb-no", "Polish (Poland)": "pl-pl", "Portuguese (Brazil)": "pt-br", "Portuguese (Portugal)": "pt-pt", "Romanian (Romania)": "ro-ro", "Russian (Russia)": "ru-ru", "Serbian (Serbia)": "sr-rs", "Slovak (Slovakia)": "sk-sk", "Slovenian (Slovenia)": "sl-si", "Spanish (Spain)": "es-es", "Swedish (Sweden)": "sv-se", "Thai (Thailand)": "th-th", "Turkish (T\u00fcrkiye)": "tr-tr", "Ukrainian (Ukraine)": "uk-ua"},
        osc_walk={"os": "Windows 8", "middle": ["9200.16384", "Multi-Edition"], "archs": ["x86", "x64"]}),
    CatalogNode("Windows 8.1 (Multi-Edition) [x64]", node_type="windows", compatibility="x64", size_gb=4.0, downloads=44550, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows 8.1 Update \u2014 4.0GB, os.click MSDN genuine, 37 langs.",
        languages={"Arabic (Saudi Arabia)": "ar-sa", "Bulgarian (Bulgaria)": "bg-bg", "Chinese (China)": "zh-cn", "Chinese (Hong Kong SAR China)": "zh-hk", "Chinese (Taiwan)": "zh-tw", "Croatian (Croatia)": "hr-hr", "Czech (Czechia)": "cs-cz", "Danish (Denmark)": "da-dk", "Dutch (Netherlands)": "nl-nl", "English": "en", "English (United Kingdom)": "en-gb", "Estonian (Estonia)": "et-ee", "Finnish (Finland)": "fi-fi", "French (France)": "fr-fr", "German (Germany)": "de-de", "Greek (Greece)": "el-gr", "Hebrew (Israel)": "he-il", "Hungarian (Hungary)": "hu-hu", "Italian (Italy)": "it-it", "Japanese (Japan)": "ja-jp", "Korean (South Korea)": "ko-kr", "Latvian (Latvia)": "lv-lv", "Lithuanian (Lithuania)": "lt-lt", "Norwegian Bokm\u00e5l (Norway)": "nb-no", "Polish (Poland)": "pl-pl", "Portuguese (Brazil)": "pt-br", "Portuguese (Portugal)": "pt-pt", "Romanian (Romania)": "ro-ro", "Russian (Russia)": "ru-ru", "Serbian (Serbia)": "sr-rs", "Slovak (Slovakia)": "sk-sk", "Slovenian (Slovenia)": "sl-si", "Spanish (Spain)": "es-es", "Swedish (Sweden)": "sv-se", "Thai (Thailand)": "th-th", "Turkish (T\u00fcrkiye)": "tr-tr", "Ukrainian (Ukraine)": "uk-ua"},
        osc_walk={"os": "Windows 8.1", "middle": ["9600.17483", "Multi-Edition"], "archs": ["x86", "x64"]}),
    CatalogNode("Windows 10 Enterprise LTSC 2021 [x64]", node_type="windows", compatibility="x64", size_gb=4.6, downloads=60769, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows 10 LTSC 2021 \u2014 4.6GB, os.click MSDN genuine, 38 langs.",
        languages={"Arabic (Saudi Arabia)": "ar-sa", "Bulgarian (Bulgaria)": "bg-bg", "Chinese (China)": "zh-cn", "Chinese (Taiwan)": "zh-tw", "Croatian (Croatia)": "hr-hr", "Czech (Czechia)": "cs-cz", "Danish (Denmark)": "da-dk", "Dutch (Netherlands)": "nl-nl", "English (United Kingdom)": "en-gb", "English (United States)": "en-us", "Estonian (Estonia)": "et-ee", "Finnish (Finland)": "fi-fi", "French (Canada)": "fr-ca", "French (France)": "fr-fr", "German (Germany)": "de-de", "Greek (Greece)": "el-gr", "Hebrew (Israel)": "he-il", "Hungarian (Hungary)": "hu-hu", "Italian (Italy)": "it-it", "Japanese (Japan)": "ja-jp", "Korean (South Korea)": "ko-kr", "Latvian (Latvia)": "lv-lv", "Lithuanian (Lithuania)": "lt-lt", "Norwegian Bokm\u00e5l (Norway)": "nb-no", "Polish (Poland)": "pl-pl", "Portuguese (Brazil)": "pt-br", "Portuguese (Portugal)": "pt-pt", "Romanian (Romania)": "ro-ro", "Russian (Russia)": "ru-ru", "Serbian (Latin, Serbia)": "sr-latn-rs", "Slovak (Slovakia)": "sk-sk", "Slovenian (Slovenia)": "sl-si", "Spanish (Mexico)": "es-mx", "Spanish (Spain)": "es-es", "Swedish (Sweden)": "sv-se", "Thai (Thailand)": "th-th", "Turkish (T\u00fcrkiye)": "tr-tr", "Ukrainian (Ukraine)": "uk-ua"},
        osc_walk={"os": "Windows 10", "middle": ["2021 LTSC", "19044.1288", "Enterprise"], "archs": ["x86", "x64"]}),
    CatalogNode("Windows 11 Consumer 26H1 [x64]", node_type="windows", compatibility="x64", size_gb=6.2, downloads=24567, latest_update="2026-09-09", page_url="https://os.click/en", notes="Windows 11 26H1 \u2014 6.2GB, os.click MSDN genuine, 38 langs.",
        languages={"Arabic (Saudi Arabia)": "ar-sa", "Bulgarian (Bulgaria)": "bg-bg", "Chinese (China)": "zh-cn", "Chinese (Taiwan)": "zh-tw", "Croatian (Croatia)": "hr-hr", "Czech (Czechia)": "cs-cz", "Danish (Denmark)": "da-dk", "Dutch (Netherlands)": "nl-nl", "English (United Kingdom)": "en-gb", "English (United States)": "en-us", "Estonian (Estonia)": "et-ee", "Finnish (Finland)": "fi-fi", "French (Canada)": "fr-ca", "French (France)": "fr-fr", "German (Germany)": "de-de", "Greek (Greece)": "el-gr", "Hebrew (Israel)": "he-il", "Hungarian (Hungary)": "hu-hu", "Italian (Italy)": "it-it", "Japanese (Japan)": "ja-jp", "Korean (South Korea)": "ko-kr", "Latvian (Latvia)": "lv-lv", "Lithuanian (Lithuania)": "lt-lt", "Norwegian Bokm\u00e5l (Norway)": "nb-no", "Polish (Poland)": "pl-pl", "Portuguese (Brazil)": "pt-br", "Portuguese (Portugal)": "pt-pt", "Romanian (Romania)": "ro-ro", "Russian (Russia)": "ru-ru", "Serbian (Latin, Serbia)": "sr-latn-rs", "Slovak (Slovakia)": "sk-sk", "Slovenian (Slovenia)": "sl-si", "Spanish (Mexico)": "es-mx", "Spanish (Spain)": "es-es", "Swedish (Sweden)": "sv-se", "Thai (Thailand)": "th-th", "Turkish (T\u00fcrkiye)": "tr-tr", "Ukrainian (Ukraine)": "uk-ua"},
        osc_walk={"os": "Windows 11", "middle": ["26H1", "28000.1450", "Multi-Edition"], "archs": ["x64"]}),
])

LINUX = CatalogNode("Linux", children=[
    CatalogNode("Arch Linux 2026.09.01 [x86_64]", compatibility="x64", size_gb=1.1, downloads=3200000, latest_update="2026-09-01", iso_url="https://ftp.spline.inf.fu-berlin.de/mirrors/archlinux/iso/2026.09.01/archlinux-2026.09.01-x86_64.iso", page_url="https://ftp.spline.inf.fu-berlin.de/mirrors/archlinux/iso/2026.09.01/archlinux-2026.09.01-x86_64.iso", notes="Arch Linux 2026.09.01 — rolling, 1.1GB, archlinux.org"),
    CatalogNode("Debian 13 iso-dvd [amd64]", compatibility="x64", size_gb=4.1, downloads=8500000, latest_update="2025-08-16", iso_url="https://cdimage.debian.org/images/release/current/amd64/iso-dvd/debian-13.6.0-amd64-DVD-1.iso", page_url="https://cdimage.debian.org/images/release/current/amd64/iso-dvd/debian-13.6.0-amd64-DVD-1.iso", notes="Debian 13 Trixie DVD — 4.1GB, debian.org"),
    CatalogNode("Debian 13 iso-hybrid gnome [amd64]", compatibility="x64", size_gb=1.1, downloads=8500000, latest_update="2025-08-16", iso_url="https://cdimage.debian.org/images/release/current-live/amd64/iso-hybrid/debian-live-13.6.0-amd64-gnome.iso", page_url="https://cdimage.debian.org/images/release/current-live/amd64/iso-hybrid/debian-live-13.6.0-amd64-gnome.iso", notes="Debian 13 GNOME Live — 3.2GB"),
    CatalogNode("Debian 13 iso-hybrid kde [amd64]", compatibility="x64", size_gb=4.1, downloads=4200000, latest_update="2025-08-16", iso_url="https://cdimage.debian.org/images/release/current-live/amd64/iso-hybrid/debian-live-13.6.0-amd64-kde.iso", page_url="https://cdimage.debian.org/images/release/current-live/amd64/iso-hybrid/debian-live-13.6.0-amd64-kde.iso", notes="Debian 13 KDE Live — 3.4GB"),
    CatalogNode("Fedora 44 x86_64 live [Workstation]", compatibility="x64", size_gb=3.4, downloads=3800000, latest_update="2025-08-16", iso_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Workstation/x86_64/iso/Fedora-Workstation-Live-44-1.7.x86_64.iso", page_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Workstation/x86_64/iso/Fedora-Workstation-Live-44-1.7.x86_64.iso", notes="Fedora 44 Workstation — 2.2GB, fedoraproject.org"),
    CatalogNode("Fedora 44 x86_64 live [Server]", compatibility="x64", size_gb=2.2, downloads=4200000, latest_update="2025-08-12", iso_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Server/x86_64/iso/Fedora-Server-dvd-x86_64-44-1.7.iso", page_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Server/x86_64/iso/Fedora-Server-dvd-x86_64-44-1.7.iso", notes="Fedora 44 Server — 2.8GB"),
    CatalogNode("Fedora 44 x86_64 live [Kde]", compatibility="x64", size_gb=2.8, downloads=1800000, latest_update="2025-08-12", iso_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/KDE/x86_64/iso/Fedora-KDE-Desktop-Live-44-1.7.x86_64.iso", page_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/KDE/x86_64/iso/Fedora-KDE-Desktop-Live-44-1.7.x86_64.iso", notes="Fedora 44 KDE — 2.4GB"),
    CatalogNode("Fedora 44 x86_64 live [Games]", compatibility="x64", size_gb=2.4, downloads=2100000, latest_update="2025-08-12", iso_url="https://download.fedoraproject.org/pub/alt/releases/44/Labs/x86_64/iso/Fedora-Games-Live-44-1.7.x86_64.iso", page_url="https://download.fedoraproject.org/pub/alt/releases/44/Labs/x86_64/iso/Fedora-Games-Live-44-1.7.x86_64.iso", notes="Fedora 44 Games — 4.2GB"),
    CatalogNode("Fedora 44 x86_64 live [Security]", compatibility="x64", size_gb=4.2, downloads=900000, latest_update="2025-08-12", iso_url="https://download.fedoraproject.org/pub/alt/releases/44/Labs/x86_64/iso/Fedora-Security-Live-44-1.7.x86_64.iso", page_url="https://download.fedoraproject.org/pub/alt/releases/44/Labs/x86_64/iso/Fedora-Security-Live-44-1.7.x86_64.iso", notes="Fedora 44 Security — 2.1GB"),
    CatalogNode("Fedora 44 x86_64 live [Everything]", compatibility="x64", size_gb=2.1, downloads=750000, latest_update="2025-08-12", iso_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-44-1.7.iso", page_url="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-44-1.7.iso", notes="Fedora 44 Netinst — 0.7GB"),
    CatalogNode("Linux Mint Ubuntu 64bit mate [22.2]", compatibility="x64", size_gb=2.9, downloads=1100000, latest_update="2025-08-12", iso_url="https://pub.linuxmint.io/stable/22.2/linuxmint-22.2-mate-64bit.iso", page_url="https://pub.linuxmint.io/stable/22.2/linuxmint-22.2-mate-64bit.iso", notes="Linux Mint 22.2 MATE — 2.9GB, linuxmint.com"),
    CatalogNode("Ubuntu 26.04.1LTS amd64 [Desktop]", compatibility="x64", size_gb=5.8, downloads=3800000, latest_update="2025-07-15", iso_url="https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-desktop-amd64.iso", page_url="https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-desktop-amd64.iso", notes="Ubuntu 26.04.1 LTS Desktop — 5.8GB, releases.ubuntu.com"),
    CatalogNode("Ubuntu 26.04.1LTS amd64 [Server]", compatibility="x64", size_gb=2.1, downloads=9500000, latest_update="2026-08-15", iso_url="https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-live-server-amd64.iso", page_url="https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-live-server-amd64.iso", notes="Ubuntu 26.04.1 Server — 2.1GB"),
    CatalogNode("Ubuntu 26.04LTS amd64 [Edubuntu]", compatibility="x64", size_gb=4.5, downloads=4200000, latest_update="2026-08-15", iso_url="https://cdimages.ubuntu.com/edubuntu/releases/26.04/release/edubuntu-26.04-desktop-amd64.iso", page_url="https://cdimages.ubuntu.com/edubuntu/releases/26.04/release/edubuntu-26.04-desktop-amd64.iso", notes="Edubuntu 26.04 — 4.5GB"),
    CatalogNode("Ubuntu 26.04LTS amd64 [Kubuntu]", compatibility="x64", size_gb=3.6, downloads=450000, latest_update="2026-04-15", iso_url="https://cdimage.ubuntu.com/kubuntu/releases/26.04.1/release/kubuntu-26.04.1-desktop-amd64.iso", page_url="https://cdimage.ubuntu.com/kubuntu/releases/26.04.1/release/kubuntu-26.04.1-desktop-amd64.iso", notes="Kubuntu 26.04.1 — 3.6GB"),
    CatalogNode("Ubuntu 26.04LTS amd64 [Lubuntu]", compatibility="x64", size_gb=3.2, downloads=2100000, latest_update="2026-08-15", iso_url="https://cdimage.ubuntu.com/lubuntu/releases/26.04.1/release/lubuntu-26.04.1-desktop-amd64.iso", page_url="https://cdimage.ubuntu.com/lubuntu/releases/26.04.1/release/lubuntu-26.04.1-desktop-amd64.iso", notes="Lubuntu 26.04.1 — 3.2GB"),
    CatalogNode("Ubuntu 26.04LTS amd64 [Budgie]", compatibility="x64", size_gb=3.4, downloads=1800000, latest_update="2026-08-15", iso_url="https://cdimage.ubuntu.com/ubuntu-budgie/releases/26.04.1/release/ubuntu-budgie-26.04.1-desktop-amd64.iso", page_url="https://cdimage.ubuntu.com/ubuntu-budgie/releases/26.04.1/release/ubuntu-budgie-26.04.1-desktop-amd64.iso", notes="Ubuntu Budgie 26.04.1 — 3.4GB"),
    CatalogNode("Ubuntu 26.04.1LTS amd64 [Studio]", compatibility="x64", size_gb=4.8, downloads=1200000, latest_update="2026-08-15", iso_url="https://cdimage.ubuntu.com/ubuntustudio/releases/resolute/release/ubuntustudio-26.04.1-desktop-amd64.iso", page_url="https://cdimage.ubuntu.com/ubuntustudio/releases/resolute/release/ubuntustudio-26.04.1-desktop-amd64.iso", notes="Ubuntu Studio 26.04.1 — 4.8GB"),
    CatalogNode("openSUSE Tumbleweed x86_64 Live_CD GNOME [20240610]", compatibility="x64", size_gb=1.2, downloads=900000, latest_update="2026-08-15", iso_url="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-GNOME-Live-x86_64-Current.iso", page_url="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-GNOME-Live-x86_64-Current.iso", notes="openSUSE Tumbleweed GNOME — 1.2GB, opensuse.org"),
    CatalogNode("openSUSE Tumbleweed x86_64 Live_CD KDE [20240610]", compatibility="x64", size_gb=1.4, downloads=1800000, latest_update="2025-08-20", iso_url="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-KDE-Live-x86_64-Current.iso", page_url="https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-KDE-Live-x86_64-Current.iso", notes="openSUSE Tumbleweed KDE — 1.4GB"),
    CatalogNode("openSUSE Leap x86_64 DVD [15.5]", compatibility="x64", size_gb=4.2, downloads=2100000, latest_update="2025-08-20", iso_url="https://download.opensuse.org/distribution/leap/15.5/iso/openSUSE-Leap-15.5-DVD-x86_64-Current.iso", page_url="https://download.opensuse.org/distribution/leap/15.5/iso/openSUSE-Leap-15.5-DVD-x86_64-Current.iso", notes="openSUSE Leap 15.5 — 4.2GB"),
    CatalogNode("Kali 26.2 [amd64]", compatibility="x64", size_gb=4.1, downloads=3200000, latest_update="2025-08-20", iso_url="https://cdimage.kali.org/kali-2026.2/kali-linux-2026.2-installer-amd64.iso", page_url="https://cdimage.kali.org/kali-2026.2/kali-linux-2026.2-installer-amd64.iso", notes="Kali Linux 2026.2 — 4.1GB, kali.org"),
    CatalogNode("Zorin OS 18.1 [amd64]", compatibility="x64", size_gb=4.1, downloads=1600000, latest_update="2025-06-10", iso_url="https://ftp.nluug.nl/pub/os/Linux/distr/zorin/18/Zorin-OS-18.1-Core-64-bit.iso", page_url="https://ftp.nluug.nl/pub/os/Linux/distr/zorin/18/Zorin-OS-18.1-Core-64-bit.iso", notes="Zorin OS 18.1 Core — 6.2GB, zorin.com"),
    CatalogNode("Parrot OS 7.3 [amd64]", compatibility="x64", size_gb=6.2, downloads=3200000, latest_update="2025-08-20", iso_url="https://bunny.deb.parrot.sh/parrot/iso/7.3/Parrot-security-7.3_amd64.iso", page_url="https://bunny.deb.parrot.sh/parrot/iso/7.3/Parrot-security-7.3_amd64.iso", notes="Parrot OS 7.3 Security — 5.4GB, parrotsec.org"),
    CatalogNode("Tails 7.11 [USB]", compatibility="x64", size_gb=5.4, downloads=1800000, latest_update="2025-08-01", iso_url="https://download.tails.net/tails/stable/tails-amd64-7.11/tails-amd64-7.11.img", page_url="https://download.tails.net/tails/stable/tails-amd64-7.11/tails-amd64-7.11.img", notes="Tails 7.11 — 1.4GB, tails.net"),
    CatalogNode("Pop OS 24.04 [amd64]", compatibility="x64", size_gb=1.4, downloads=900000, latest_update="2025-08-15", iso_url="https://iso.pop-os.org/24.04/amd64/generic/27/pop-os_24.04_amd64_generic_27.iso", page_url="https://iso.pop-os.org/24.04/amd64/generic/27/pop-os_24.04_amd64_generic_27.iso", notes="Pop!_OS 24.04 — 3.2GB, system76.com"),
    CatalogNode("TinyCore 17.1 [x86]", compatibility="x86", size_gb=0.03, downloads=900000, latest_update="2025-08-15", iso_url="http://tinycorelinux.net/17.x/x86/release/CorePlus-current.iso", page_url="http://tinycorelinux.net/17.x/x86/release/CorePlus-current.iso", notes="TinyCore 17.1 CorePlus — 0.03GB, tinycorelinux.net"),
    CatalogNode("Catchy OS Desktop [amd64]", compatibility="x64", size_gb=3.2, downloads=1200000, latest_update="2025-06-15", iso_url="https://cdn77.cachyos.org/ISO/desktop/260809/cachyos-desktop-linux-260809.iso", page_url="https://cdn77.cachyos.org/ISO/desktop/260809/cachyos-desktop-linux-260809.iso", notes="CachyOS Desktop 260809 — 3.1GB, cachyos.org"),
    CatalogNode("Slax 12.2 [amd64]", compatibility="x64", size_gb=3.1, downloads=2100000, latest_update="2025-08-15", iso_url="https://ftp.cvut.cz/slax/Slax-12.x/slax-64bit-debian-12.2.0.iso", page_url="https://ftp.cvut.cz/slax/Slax-12.x/slax-64bit-debian-12.2.0.iso", notes="Slax 12.2 Debian — 0.3GB, slax.org"),
    CatalogNode("Pika OS 3.26 amd64 [GNOME]", compatibility="x64", size_gb=3.2, downloads=800000, latest_update="2025-08-09", iso_url="https://iso.pika-os.com/PikaOS-Nest-GNOME-4.0-amd64-v3-26.08.20-4.iso", page_url="https://iso.pika-os.com/PikaOS-Nest-GNOME-4.0-amd64-v3-26.08.20-4.iso", notes="PikaOS 3.26 GNOME — 3.2GB, pika-os.com"),
    CatalogNode("Pika OS 3.26 amd64 [KDE]", compatibility="x64", size_gb=3.4, downloads=1500000, latest_update="2023-10-09", iso_url="https://iso.pika-os.com/PikaOS-Nest-KDE-4.0-amd64-v3-26.08.20-4.iso", page_url="https://iso.pika-os.com/PikaOS-Nest-KDE-4.0-amd64-v3-26.08.20-4.iso", notes="PikaOS 3.26 KDE — 3.4GB"),
    CatalogNode("Pika OS 3.26 amd64 [HYPRLAND]", compatibility="x64", size_gb=3.5, downloads=450000, latest_update="2025-08-20", iso_url="https://iso.pika-os.com/PikaOS-Nest-Hyprland-4.0-amd64-v3-26.08.20-4.iso", page_url="https://iso.pika-os.com/PikaOS-Nest-Hyprland-4.0-amd64-v3-26.08.20-4.iso", notes="PikaOS 3.26 Hyprland — 3.5GB"),
    CatalogNode("Pika OS 3.26 amd64 [NIRI]", compatibility="x64", size_gb=3.3, downloads=420000, latest_update="2025-08-20", iso_url="https://iso.pika-os.com/PikaOS-Nest-Niri-4.0-amd64-v3-26.08.20-4.iso", page_url="https://iso.pika-os.com/PikaOS-Nest-Niri-4.0-amd64-v3-26.08.20-4.iso", notes="PikaOS 3.26 Niri — 3.3GB"),
    CatalogNode("Qubes OS 4.3.1 [amd64]", compatibility="x64", size_gb=6.5, downloads=380000, latest_update="2025-08-20", iso_url="https://mirrors.edge.kernel.org/qubes/iso/Qubes-R4.3.1-x86_64.iso", page_url="https://mirrors.edge.kernel.org/qubes/iso/Qubes-R4.3.1-x86_64.iso", notes="Qubes OS 4.3.1 — 6.5GB, qubes-os.org"),
    CatalogNode("Backbox 9 amd64 [Desktop]", compatibility="x64", size_gb=3.2, downloads=350000, latest_update="2025-08-20", iso_url="https://backbox.mirror.garr.it/backbox-9-desktop-amd64.iso", page_url="https://backbox.mirror.garr.it/backbox-9-desktop-amd64.iso", notes="BackBox 9 — 3.2GB, backbox.org"),
    CatalogNode("Garuda 26.08 amd64 [GNOME]", compatibility="x64", size_gb=3.8, downloads=600000, latest_update="2025-06-15", iso_url="https://r2.garudalinux.org/iso/garuda/gnome/260819/garuda-gnome-linux-garuda-260819.iso?r2request", page_url="https://r2.garudalinux.org/iso/garuda/gnome/260819/garuda-gnome-linux-garuda-260819.iso?r2request", notes="Garuda GNOME 26.08 — 3.8GB, garudalinux.org"),
    CatalogNode("Garuda 26.08 amd64 [MOKKA]", compatibility="x64", size_gb=3.9, downloads=320000, latest_update="2025-08-15", iso_url="https://r2.garudalinux.org/iso/garuda/mokka/260819/garuda-mokka-linux-garuda-260819.iso?r2request", page_url="https://r2.garudalinux.org/iso/garuda/mokka/260819/garuda-mokka-linux-garuda-260819.iso?r2request", notes="Garuda MOKKA 26.08 — 3.9GB"),
    CatalogNode("Garuda 26.08 amd64 [KDE]", compatibility="x64", size_gb=4.1, downloads=700000, latest_update="2025-08-19", iso_url="https://r2.garudalinux.org/iso/garuda/kde-lite/260819/garuda-kde-lite-linux-garuda-260819.iso?r2request", page_url="https://r2.garudalinux.org/iso/garuda/kde-lite/260819/garuda-kde-lite-linux-garuda-260819.iso?r2request", notes="Garuda KDE 26.08 — 4.1GB"),
    CatalogNode("Csi DD [amd64]", compatibility="x64", size_gb=2.5, downloads=650000, latest_update="2025-08-19", iso_url="https://downloads.csilinux.com/CSI_Linux_Bootable.7z", page_url="https://downloads.csilinux.com/CSI_Linux_Bootable.7z", notes="CSI Linux Bootable — 2.5GB, csilinux.com"),
    CatalogNode("Athena OS Live [amd64]", compatibility="x64", size_gb=3.2, downloads=850000, latest_update="2025-08-19", iso_url="https://hub.athenaos.org/iso/athenaos-live-x86_64.iso", page_url="https://hub.athenaos.org/iso/athenaos-live-x86_64.iso", notes="Athena OS Live — 3.2GB, athenaos.org"),
    CatalogNode("Void 25.2 amd64 [XFCE]", compatibility="x64", size_gb=0.5, downloads=120000, latest_update="2025-08-15", iso_url="https://repo-default.voidlinux.org/live/current/void-live-x86_64-20250202-base.iso", page_url="https://repo-default.voidlinux.org/live/current/void-live-x86_64-20250202-base.iso", notes="Void Linux XFCE — 0.5GB, voidlinux.org"),
    CatalogNode("Gentoo 26.8 amd64 [KDE]", compatibility="x64", size_gb=4.2, downloads=400000, latest_update="2025-08-15", iso_url="https://distfiles.gentoo.org/releases/amd64/autobuilds/20260830T151604Z/livegui-amd64-20260830T151604Z.iso", page_url="https://distfiles.gentoo.org/releases/amd64/autobuilds/20260830T151604Z/livegui-amd64-20260830T151604Z.iso", notes="Gentoo LiveGUI 2026-08-30 — 4.2GB, gentoo.org"),
    CatalogNode("Rocky 10.2 [amd64]", compatibility="x64", size_gb=4.5, downloads=600000, latest_update="2025-02-02", iso_url="https://download.rockylinux.org/pub/rocky/10/isos/x86_64/Rocky-10.2-x86_64-dvd1.iso", page_url="https://download.rockylinux.org/pub/rocky/10/isos/x86_64/Rocky-10.2-x86_64-dvd1.iso", notes="Rocky Linux 10.2 — 4.5GB, rockylinux.org"),
    CatalogNode("Alma 10 amd64 [KDE]", compatibility="x64", size_gb=2.2, downloads=500000, latest_update="2026-08-30", iso_url="https://repo.almalinux.org/almalinux/10/live/x86_64/AlmaLinux-10.2-x86_64-Live-KDE.iso", page_url="https://repo.almalinux.org/almalinux/10/live/x86_64/AlmaLinux-10.2-x86_64-Live-KDE.iso", notes="AlmaLinux 10.2 KDE — 2.2GB, almalinux.org"),
    CatalogNode("Alma 10 amd64 [GNOME]", compatibility="x64", size_gb=2.4, downloads=900000, latest_update="2025-08-15", iso_url="https://repo.almalinux.org/almalinux/10/live/x86_64/AlmaLinux-10.2-x86_64-Live-GNOME.iso", page_url="https://repo.almalinux.org/almalinux/10/live/x86_64/AlmaLinux-10.2-x86_64-Live-GNOME.iso", notes="AlmaLinux 10.2 GNOME — 2.4GB"),
    CatalogNode("Manjaro 26.1 amd64 [KDE]", compatibility="x64", size_gb=3.8, downloads=800000, latest_update="2025-08-15", iso_url="https://download.manjaro.org/kde/26.1.0/manjaro-kde-26.1.0-260812-linux71.iso", page_url="https://download.manjaro.org/kde/26.1.0/manjaro-kde-26.1.0-260812-linux71.iso", notes="Manjaro 26.1 KDE — 3.8GB, manjaro.org"),
    CatalogNode("Manjaro 26.1 amd64 [GNOME]", compatibility="x64", size_gb=3.6, downloads=750000, latest_update="2025-08-15", iso_url="https://download.manjaro.org/gnome/26.1.0/manjaro-gnome-26.1.0-260812-linux71.iso", page_url="https://download.manjaro.org/gnome/26.1.0/manjaro-gnome-26.1.0-260812-linux71.iso", notes="Manjaro 26.1 GNOME — 3.6GB"),
    CatalogNode("Sigint OS 2.0 [amd64]", compatibility="x64", size_gb=3.2, downloads=1100000, latest_update="2025-08-12", iso_url="https://www.sigintos.com/downloads/sigintos2.0-community-edition.iso", page_url="https://www.sigintos.com/downloads/sigintos2.0-community-edition.iso", notes="SigintOS 2.0 — 3.2GB, sigintos.com"),
    CatalogNode("Caine 14.0 [amd64]", compatibility="x64", size_gb=4.0, downloads=900000, latest_update="2025-08-12", iso_url="https://www.caine-live.net/Downloads/caine14.0.iso", page_url="https://www.caine-live.net/Downloads/caine14.0.iso", notes="Caine 14.0 — 4.0GB, caine-live.net"),
])

UNIX = CatalogNode("Unix / BSD", children=[
    CatalogNode("FreeBSD 15.1 [amd64]", compatibility="x64", size_gb=4.3,
                downloads=600000, latest_update="2026-09-09",
                iso_url="https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES/15.1/FreeBSD-15.1-RELEASE-amd64-dvd1.iso",
                page_url="https://www.freebsd.org/where/",
                notes="FreeBSD 15.1 DVD — 4.3GB, freebsd.org"),
    CatalogNode("OpenBSD [x86_64]", compatibility="x64", size_gb=0.8,
                downloads=200000, latest_update="2026-08-01",
                page_url="https://www.openbsd.org/faq/faq4.html#Download",
                notes="OpenBSD — security-focused (browser)."),
    CatalogNode("NetBSD [x86_64]", compatibility="x64", size_gb=1.0,
                downloads=120000, latest_update="2026-07-30",
                page_url="https://www.netbsd.org/releases/",
                notes="NetBSD — portable (browser)."),
    CatalogNode("DragonFly BSD [x86_64]", compatibility="x64", size_gb=1.2,
                downloads=50000, latest_update="2026-07-25",
                page_url="https://www.dragonflybsd.org/download/",
                notes="DragonFly BSD — HAMMER (browser)."),
    CatalogNode("GhostBSD [x86_64]", compatibility="x64", size_gb=2.5,
                downloads=80000, latest_update="2026-08-05",
                page_url="https://www.ghostbsd.org/download",
                notes="GhostBSD — FreeBSD + MATE (browser)."),
    CatalogNode("NomadBSD [x86_64]", compatibility="x64", size_gb=2.5,
                downloads=40000, latest_update="2026-08-05",
                page_url="https://nomadbsd.org/",
                notes="NomadBSD — persistent USB desktop (browser)."),
    CatalogNode("pfSense [x86_64]", compatibility="x64", size_gb=1.2,
                downloads=2000000, latest_update="2026-08-10",
                page_url="https://www.pfsense.org/download/",
                notes="pfSense — firewall/router (browser)."),
    CatalogNode("OPNsense [x86_64]", compatibility="x64", size_gb=1.2,
                downloads=900000, latest_update="2026-08-10",
                page_url="https://opnsense.org/download/",
                notes="OPNsense — firewall (browser)."),
])

RECOVERY = CatalogNode("Maintenance and Recovery", children=[
        CatalogNode("System Rescue 13.02 [amd64]", compatibility="x64", size_gb=1.2, downloads=850000, latest_update="2025-06-15", iso_url="https://fastly-cdn.system-rescue.org/releases/13.02/systemrescue-13.02-amd64.iso", page_url="https://fastly-cdn.system-rescue.org/releases/13.02/systemrescue-13.02-amd64.iso", notes="System Rescue 13.02 — 1.2GB, system-rescue.org"),
    CatalogNode("GParted Live", compatibility="x64", size_gb=0.5,
                downloads=1500000, latest_update="2026-08-01",
                page_url="https://gparted.org/download.php",
                notes="GParted Live partition editor (browser)."),
    CatalogNode("Clonezilla", compatibility="x64", size_gb=0.4,
                downloads=1200000, latest_update="2026-07-22",
                page_url="https://clonezilla.org/downloads.php",
                notes="Clonezilla disk imaging (browser)."),
    CatalogNode("Rescatux", compatibility="x64", size_gb=0.7,
                downloads=150000, latest_update="2026-06-30",
                page_url="https://www.rescatux.org/",
                notes="Rescatux rescue/repair (browser)."),
    CatalogNode("Grml", compatibility="x64", size_gb=0.5,
                downloads=100000, latest_update="2026-07-28",
                page_url="https://grml.org/download/",
                notes="Grml admin live (browser)."),
    CatalogNode("Finnix", compatibility="x64", size_gb=0.4,
                downloads=50000, latest_update="2026-07-20",
                page_url="https://www.finnix.org/",
                notes="Finnix maintenance live (browser)."),
    CatalogNode("Parted Magic", compatibility="x64", size_gb=2.0,
                downloads=200000, latest_update="2026-07-30",
                page_url="https://partedmagic.com/",
                notes="Parted Magic suite (browser)."),
    CatalogNode("Trinity Rescue Kit", compatibility="x64", size_gb=0.7,
                downloads=100000, latest_update="2026-06-30",
                page_url="https://trinityhome.org/",
                notes="Trinity Rescue Kit (browser)."),
    CatalogNode("Rescuezilla", compatibility="x64", size_gb=1.1,
                downloads=300000, latest_update="2026-08-03",
                page_url="https://rescuezilla.com/",
                notes="Rescuezilla graphical Clonezilla (browser)."),
    CatalogNode("TestDisk", compatibility="x64", size_gb=0.5,
                downloads=2000000, latest_update="2026-08-05",
                page_url="https://www.cgsecurity.org/wiki/TestDisk_Download",
                notes="TestDisk recovery (browser)."),
    CatalogNode("PhotoRec", compatibility="x64", size_gb=0.5,
                downloads=1500000, latest_update="2026-08-05",
                page_url="https://www.cgsecurity.org/wiki/PhotoRec",
                notes="PhotoRec file carver (browser)."),
    CatalogNode("Ultimate Boot CD", compatibility="x64", size_gb=1.0,
                downloads=500000, latest_update="2026-07-15",
                page_url="https://www.ultimatebootcd.com/download.html",
                notes="Ultimate Boot CD diagnostics (browser)."),
    CatalogNode("MedCat USB", compatibility="x64", size_gb=1.5,
                downloads=100000, latest_update="2026-07-30",
                page_url="https://medcat.com/",
                notes="MedCat recovery toolkit (browser)."),
    CatalogNode("Hirens BootCD PE", compatibility="x64", size_gb=2.8,
                downloads=1000000, latest_update="2026-07-28",
                page_url="https://www.hirensbootcd.org/download/",
                notes="Hiren's BootCD PE WinPE (browser)."),
])

ROOT = CatalogNode("Operating Systems", children=[WINDOWS, LINUX, UNIX, RECOVERY])


def _deduplicate(node: CatalogNode, seen: set) -> None:
    """Recursively remove duplicate-named leaves (keep first occurrence)."""
    kept = []
    for child in node.children:
        if child.is_leaf:
            if child.name in seen:
                continue
            seen.add(child.name)
            kept.append(child)
        else:
            _deduplicate(child, seen)
            if child.children:
                kept.append(child)
    node.children = kept


def iter_leaves(node: CatalogNode = ROOT) -> Iterator[CatalogNode]:
    if node.is_leaf:
        yield node
        return
    for child in node.children:
        yield from iter_leaves(child)


def find_leaf(predicate) -> Optional[CatalogNode]:
    for leaf in iter_leaves():
        if predicate(leaf):
            return leaf
    return None


def load_user_overrides(path: str) -> None:
    """Load user catalogue overrides from a JSON file (best effort)."""
    import json as _json
    try:
        data = _json.load(open(os.path.expanduser(path)))
    except Exception:
        return
    by_name = {leaf.name: leaf for leaf in iter_leaves()}
    items = data if isinstance(data, list) else data.get("overrides", [])
    for item in items:
        if not isinstance(item, dict):
            continue
        leaf = by_name.get(item.get("name", ""))
        if leaf is None:
            continue
        for key in ("iso_url", "page_url", "notes", "size_gb", "downloads",
                    "latest_update", "compatibility"):
            if key in item:
                setattr(leaf, key, item[key])


def finalize_catalog() -> None:
    """Fill defaults and guarantee unique leaf names (idempotent)."""
    _deduplicate(ROOT, set())
    for leaf in iter_leaves():
        if not leaf.latest_update:
            leaf.latest_update = DEFAULT_DATE
        if not leaf.compatibility:
            leaf.compatibility = "x64"


finalize_catalog()
