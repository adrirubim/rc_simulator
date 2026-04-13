<p align="center">
  <img src="assets/icons/png/rc-simulator-128.png" alt="RC Simulator logo" width="96" />
</p>

# RC Simulator

> Desktop UI (Qt / PySide6) to control an RC car (MOZA + UDP + video). Goal: an operational Linux frontend, usable on Windows via WSLg.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-N%2FA-lightgrey?style=flat)](REPO_STANDARD.md)
[![PySide6](https://img.shields.io/badge/PySide6-6.11+-41CD52?style=flat)](https://doc.qt.io/qtforpython/)
[![Tests](https://img.shields.io/github/actions/workflow/status/adrirubim/rc_simulator/tests.yml?branch=main&label=Tests&style=flat&color=brightgreen)](https://github.com/adrirubim/rc_simulator/actions/workflows/tests.yml)
[![Lint](https://img.shields.io/github/actions/workflow/status/adrirubim/rc_simulator/lint.yml?branch=main&label=Lint&style=flat&color=blue)](https://github.com/adrirubim/rc_simulator/actions/workflows/lint.yml)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat)](LICENSE)

## 📋 Table of Contents

- [Operational Quickstart](#operational-quickstart)
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Installation](#installation)
- [Security](#security)
- [Documentation](#documentation)
- [CI/CD](#cicd)
- [Testing](#testing)
- [Architecture](#architecture)
- [Optional Tooling](#optional-tooling)
- [Project Status](#project-status)
- [Default Users](#default-users-development)
- [Useful Commands](#useful-commands)
- [Before Pushing to GitHub](#before-pushing-to-github)
- [Contributing](#contributing)
- [Author](#author)
- [License](#license)

---

<a id="operational-quickstart"></a>
## ⚙️ Operational Quickstart

Use these commands from the **repository root** as your main entrypoints:

| Command | Purpose | Notes |
|--------|---------|-------|
| `./scripts/dev-verify.sh` | **Full validation** (CI parity) | Creates venv if missing, installs deps, runs audit + ruff + pytest |
| `python -m rc_simulator` | **Run the app** | Requires a GUI-capable environment (Linux desktop or WSLg) |
| `ops/linux/install_launcher.sh` | **Install desktop launcher** | Linux only (writes a `.desktop` entry) |

---

<a id="overview"></a>
## 🎯 Overview

RC Simulator is a Qt UI that coordinates:

- “Car” discovery (network/UDP)
- Control (MOZA/evdev → UDP)
- Optional video (GStreamer), depending on environment

### Key Highlights

- **Single official entrypoint:** `python -m rc_simulator`
- **CI-parity gate:** `./scripts/dev-verify.sh`
- **OS integration:** systemd + desktop launcher (Linux) and shortcut installer (Windows via WSL)

### Runtime notes

- **Linux** is the original target.
- On **Windows**, **WSLg** is recommended to render the UI. Access to `/dev/input` (MOZA) may not be available.

---

<a id="features"></a>
## ✨ Features

### 🔐 Security & Stability

- ✅ Repo hygiene guardrails (no build artifacts tracked; CI gate via `./scripts/dev-verify.sh`)
- ✅ Conservative defaults (env-driven config via `RC_UI_*`)

### ⚙️ Control & Connectivity

- ✅ Discovery and control services (`src/rc_simulator/services/`)
- ✅ MOZA input support via `evdev` (Linux only; environment-dependent)

### 🎥 Video & UI

- ✅ Qt UI (PySide6) with clear operational states
- ✅ GStreamer helper (`ops/linux/camera_receive.sh`) for UDP H264 receive

### 🧰 Operations

- ✅ OS integration scripts (Linux systemd / launcher; Windows shortcut via WSL)

---

<a id="tech-stack"></a>
## 🛠 Tech Stack

- **Language:** Python 3.12+
- **UI:** Qt / PySide6
- **Linux input:** evdev (Linux only)
- **Video (optional):** GStreamer (system packages)
- **Quality:** ruff + pytest

---

<a id="requirements"></a>
## 📦 Requirements

- Linux (original target). On Windows, WSLg for UI (access to `/dev/input` may not work).
- Python 3.12+

Video (Linux, optional):

```bash
sudo apt update
sudo apt install -y python3-gi gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

---

<a id="installation"></a>
## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/adrirubim/rc_simulator.git
cd rc_simulator
```

### 2. System dependencies (Ubuntu/Debian)

MOZA (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install -y python3-evdev
```

Video (optional):

```bash
sudo apt update
sudo apt install -y python3-gi gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

### 3. Python environment (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

### 4. Run

```bash
python -m rc_simulator
```

---

<a id="security"></a>
## 🔒 Security

- Never commit secrets (see `SECURITY.md`).
- Avoid hardcoded absolute paths like `$HOME/...` in runtime; prefer env vars or repo-relative paths when appropriate.

---

<a id="documentation"></a>
## 📚 Documentation

Index: [docs/README.md](docs/README.md).

| Section | Links |
|---------|-------|
| **Technical** | [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) · [VERSION_STACK.md](VERSION_STACK.md) |
| **Development** | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) · [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| **Architecture** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| **Operations** | [ops/README.md](ops/README.md) |
| **Policy** | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [SUPPORT.md](SUPPORT.md) · [REPO_STANDARD.md](REPO_STANDARD.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [CHANGELOG.md](CHANGELOG.md) |

---

<a id="cicd"></a>
## 🔄 CI/CD

GitHub Actions runs workflows on `push` and `pull_request`.

Workflows:

- `.github/workflows/lint.yml`
- `.github/workflows/tests.yml`
- `.github/workflows/security.yml`

Local equivalent (CI parity):

```bash
./scripts/dev-verify.sh
```

---

<a id="testing"></a>
## 🧪 Testing

Minimal:

```bash
pytest
```

Notes:

- CI-parity local gate (recommended):

```bash
./scripts/dev-verify.sh
```

- CI (GitHub Actions) equivalent:

```bash
python -m pip install -U pip
python -m pip install -e ".[dev]"
PYTHONPATH=src pytest -q
```

- If you didn't install the package into the venv, use `PYTHONPATH=src`:

```bash
PYTHONPATH=src pytest
```

---

<a id="architecture"></a>
## 🏗 Architecture

RC Simulator follows a modular architecture with a clear separation of concerns across UI, app coordination, core types/config, and service logic.

**High-level flow:**

```text
Bootstrap → Qt UI (PySide6) → Discovery | Control Session | Video (optional)
                          ↓
             core/config/state/events + adapters/ports/services
```

For a more detailed module map, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

<a id="optional-tooling"></a>
## 🧩 Optional Tooling

N/A. This repository does not ship optional tooling beyond `scripts/` and `ops/` directories.

---

<a id="project-status"></a>
## 📊 Project Status

- **Current release:** **v0.1.0** — **In Development**
- **Changelog:** see [CHANGELOG.md](CHANGELOG.md).
- **Local quality gate:** `./scripts/dev-verify.sh` (CI parity).

---

<a id="default-users-development"></a>
## ⚠️ Default Users (development)

N/A. RC Simulator does not ship with user accounts. Any authentication/authorization is handled by the upstream system and/or the environment where the RC car is deployed.

---

<a id="useful-commands"></a>
## 🛠 Useful Commands

```bash
./scripts/dev-verify.sh
python -m rc_simulator
python3 scripts/audit_layout.py
```

---

<a id="before-pushing-to-github"></a>
## 📤 Before Pushing to GitHub

CI parity (single entrypoint):

```bash
./scripts/dev-verify.sh
```

---

<a id="contributing"></a>
## 🤝 Contributing

See [CONTRIBUTING](CONTRIBUTING.md) for local checks, branch/commit conventions, and how to open PRs and issues. This is an open-source project (MIT); for inquiries, contact the author.

### Code Standards

- **Python style**: Follow PEP 8 / PEP 20 and project conventions for layout and imports.
- **Tests**: Write tests for new features; keep the test suite passing.
- **Documentation**: Keep public behavior documented (docs and docstrings) in English.
- **Pull Requests**: PRs must pass the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) checklist and GitHub Actions CI.

---

<a id="author"></a>
## 👨‍💻 Author

**Developed by:** [Adrián Morillas Pérez](https://linktr.ee/adrianmorillasperez)

### Connect

- 📧 **Email:** [adrianmorillasperez@gmail.com](mailto:adrianmorillasperez@gmail.com)
- 💻 **GitHub:** [@adrirubim](https://github.com/adrirubim)
- 🌐 **Linktree:** [adrianmorillasperez](https://linktr.ee/adrianmorillasperez)
- 💼 **LinkedIn:** [Adrián Morillas Pérez](https://www.linkedin.com/in/adrianmorillasperez)
- 📱 **Instagram:** [@adrirubim](https://instagram.com/adrirubim)
- 📘 **Facebook:** [AdRubiM](https://facebook.com/adrirubim)

---

<a id="license"></a>
## 📄 License

MIT — See [LICENSE](LICENSE).

---

**Last Updated:** April 2026 · **Status:** In Development 🚧 · **Version:** v0.1.0 · **Stack:** [VERSION_STACK.md](VERSION_STACK.md)

