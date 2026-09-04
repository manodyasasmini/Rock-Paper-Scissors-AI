# 🎮 Rock-Paper-Scissors AI Battle Arena

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-green.svg?logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-orange.svg?logo=opencv&logoColor=white)](https://opencv.org/)
[![Pillow](https://img.shields.io/badge/Pillow-UI%20Rendering-yellow.svg)](https://python-pillow.org/)

An interactive, real-time Computer Vision game that lets you play **Rock-Paper-Scissors** against an adaptive AI bot through your webcam. Powered by **MediaPipe Hands** landmark detection and an intelligent **Markov Chain** pattern prediction algorithm.

---

## 📸 Demo & Gameplay Preview

> 🎬 **[Watch Full Video Demo (demo/demo-rps.mp4)](demo/demo-rps.mp4)**

https://github.com/user-attachments/assets/demo-rps.mp4 <!-- When uploaded to GitHub, this plays inline -->

| Profile Login & Arena | Live Hand Tracking | Showdown & Victory |
| :---: | :---: | :---: |
| ![Login Preview](demo/Screenshot%202026-09-04%20204456.png) | ![Gameplay Preview](demo/Screenshot%202026-09-04%20204518.png) | ![Victory Preview](demo/Screenshot%202026-09-04%20204530.png) |

---

## ✨ Features

- 🖐️ **Real-Time Hand Tracking**: Uses Google MediaPipe's 21 3D-landmark skeletal tracking pipeline to recognize Rock, Paper, and Scissors gestures instantly at 30+ FPS.
- 👤 **Multi-Player Profiles & Persistent Memory (`players_data.json`)**:
  - Enter your player name at startup or switch profiles on the fly with `[P]`.
  - Saves individualized Markov Chain behavioral transition matrices, high scores, win streaks, and match stats per player across game sessions!
- 🧠 **Adaptive AI (Markov Chain Predictor)**:
  - Tracks player transition patterns between moves in real-time.
  - Anticipates the user's next gesture based on past behavioral probability and counters it dynamically.
  - Toggle between **Predictive AI** and **Random AI** on the fly.
- 🎨 **Esports Cyberpunk HUD**:
  - Crisp typography rendered via TrueType fonts and PIL RGBA alpha blending.
  - Animated 360° circular radial countdown timer.
  - Live scoreboard with Win Streaks and recent match outcome pills (`W` / `L` / `D`).
  - Interactive split-screen move showdown cards.
- 🖥️ **Full-Screen Responsive**: Seamlessly adapts to full screen and standard window modes with the press of a key.

---

## 🏗️ System Architecture

```
[ Webcam Input ] 
       │
       ▼
[ OpenCV Frame Capture ] ──► [ RGB Conversion ]
                                   │
                                   ▼
                       [ MediaPipe Hands Pipeline ]
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
       [ 21 3D Landmarks ]              [ Cyber Skeleton Overlay ]
                   │
                   ▼
     [ Geometric Gesture Classifier ]
       (Rock / Paper / Scissors)
                   │
                   ▼
       [ Game State Machine ]
    (IDLE ➔ COUNTDOWN ➔ EVALUATE ➔ RESULT)
                   │
                   ├───────────────┐
                   ▼               ▼
        [ Markov Chain AI ]   [ Score & Streak Tracker ]
                   │
                   ▼
   [ PIL + OpenCV HUD Renderer ] ──► [ Fullscreen Display ]
```

---

## 🕹️ Controls

| Key | Action |
| :---: | :--- |
| **`[SPACE]`** | Start round / trigger 3-second animated countdown |
| **`[P]`** | Switch active Player Profile & load individual AI memory |
| **`[F]`** | Toggle Fullscreen / Windowed mode |
| **`[D]`** | Switch AI Mode (*Predictive* vs *Random*) |
| **`[R]`** | Reset scoreboard & streaks |
| **`[Q]`** | Save and quit game |

---

## 🚀 Quickstart & Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-username/rock-paper-scissors-ai.git
cd rock-paper-scissors-ai
```

### 2. Set up virtual environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Launch the game
```bash
python rps_game.py
```

---

## 🛠️ Tech Stack & Concepts

- **Language**: Python 3.10+
- **Computer Vision**: OpenCV, Google MediaPipe
- **Machine Learning / AI**: Discrete-time Markov Chains, Transition Probability Matrices
- **Graphics & UI**: PIL (Pillow), Alpha Compositing, Bézier & Radial Arc geometry
