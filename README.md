# 🎮 Rock-Paper-Scissors AI Battle Arena

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-green.svg?logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-orange.svg?logo=opencv&logoColor=white)](https://opencv.org/)
[![Pillow](https://img.shields.io/badge/Pillow-UI%20Rendering-yellow.svg)](https://python-pillow.org/)

An interactive, real-time Computer Vision game that lets you play **Rock-Paper-Scissors** against an adaptive AI bot through your webcam. Powered by **MediaPipe Hands** landmark detection and an intelligent **Markov Chain** pattern prediction algorithm.

---

## 📸 Gameplay & Interface Previews

### 1. Player Profiles & Session Management
| Profile Login Screen | Returning Player Decision Modal |
| :---: | :---: |
| ![Profile Login Screen](demo/Screenshot%202026-09-04%20213000.png) | ![Session Decision Modal](demo/Screenshot%202026-09-04%20213010.png) |
| *Personalized profile login for unique AI tracking* | *Choose between starting fresh or resuming scores* |

### 2. Live Arena & Hand Landmark Tracking
| Arena Idle & Ready Screen | Live Round Countdown & Tracking |
| :---: | :---: |
| ![Arena Ready Screen](demo/Screenshot%202026-09-04%20213200.png) | ![Live Round Countdown](demo/Screenshot%202026-09-04%20213056.png) |
| *Arena ready prompt with live gesture tracking* | *3... 2... 1... circular countdown gauge triggered via [SPACE]* |

### 3. Match Outcomes & Round Results
| Player Victory | AI Victory | Draw Match |
| :---: | :---: | :---: |
| ![Player Victory](demo/Screenshot%202026-09-04%20213133.png) | ![AI Victory](demo/Screenshot%202026-09-04%20213147.png) | ![Draw Match](demo/Screenshot%202026-09-04%20213110.png) |
| *Rock counters Scissors (+1 to Player)* | *Scissors counters Paper (+1 to AI)* | *Matching moves (Draw / Streak maintained)* |

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
- 🎨 **3-Column Arena & Cyberpunk HUD**:
  - Crisp TrueType typography rendered via PIL RGBA alpha blending.
  - Dedicated center camera viewport with 100% natural aspect ratio and live skeletal tracking.
  - Unobstructed side-by-side **Player** and **AI** action cards.
  - Animated 360° circular radial countdown timer.
  - Live scoreboard with Win Streaks and recent match outcome pills (`W` / `L` / `D`).
- 🖥️ **Full-Screen Responsive**: Seamlessly adapts to full screen and standard window modes with the press of `[F]`.

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
    (LOGIN ➔ READY ➔ COUNTDOWN ➔ RESULT)
                   │
                   ├───────────────┐
                   ▼               ▼
        [ Markov Chain AI ]   [ Score & Streak Tracker ]
                   │
                   ▼
   [ PIL + OpenCV HUD Renderer ] ──► [ Fullscreen Arena Display ]
```

---

## 🕹️ How a visit works

1. **Start screen:** the leaderboard shows who beat the AI most. Press `SPACE`.
2. **Your name:** type a name (up to 12 letters) and press `ENTER`. Leave it empty to play as a guest, who is never saved.
3. **Camera check:** hold your hand up. The match starts by itself after two seconds.
4. **The match:** 15 rounds. Show rock, paper or scissors on SHOOT! The AI has already locked its move.
5. **Report card:** a title, how readable you were, the habits it found, and your leaderboard rank.

## 🎛️ Controls

| Key | Action |
| :---: | :--- |
| **`[SPACE]`** | Play, start a round, move on |
| **`[ENTER]`** | Confirm your name |
| **`[H]`** | Learn mode: show what the AI expected after each round |
| **`[R]`** | On the report: see every round |
| **`[N]` / `[P]`** | Next player (back to the start screen) |
| **`[F]`** | Toggle Fullscreen / Windowed mode |
| **`[Ctrl+A]`** | Admin settings: match length, default mode, hide the camera picture, idle time, clear the leaderboard |
| **`[Q]`** | Save and quit game |

---: | :--- |
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
git clone https://github.com/manodyasasmini/Rock-Paper-Scissors-AI.git
cd Rock-Paper-Scissors-AI
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

---

## 👤 Author

**SMS Abeyrathne** · 235501H · BSc (Hons) Artificial Intelligence
