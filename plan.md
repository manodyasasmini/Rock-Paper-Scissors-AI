# Rock Paper Scissors AI: Redesign and Upgrade Plan

**Goal:** turn the working prototype into an exhibition piece where a visitor walks up, plays with one hand, and clearly sees the AI learning their habits.

**Approach:** keep the stack (Python, OpenCV, MediaPipe, NumPy, Pillow, JSON). Upgrade the structure, the hand viewport, the prediction engine and the visual design. Build the new version next to `rps_game.py`, so the current game keeps working until the new one is better.

**Status:** Phases 0-2, 4 and 5 done. The hand-only viewport described in section 3 was built, then dropped after the first play-test: the camera now shows normally inside the player's card, next to the AI's card (see Phase 2 and section 5.4).

---

## 1. Design principles

1. **The hand and the AI's reasoning are the stars.** Everything else supports them.
2. **Every number on screen is real.** The reference HUDs are full of decorative readouts. We take their look, but never show a number the program didn't measure.
3. **Never reveal the AI's read before the throw.** See section 4.3.
4. **No video is saved.** The current code has no `VideoWriter` or `imwrite` calls. The new version must keep it that way. The live camera picture appears in the player's card only. A skeleton-only mode is still a planned option for venues that don't want faces shown.
5. **A stranger can play without instructions.** No required typing, and the game shouldn't depend on keyboard shortcuts.

---

## 2. What the current code needs fixed

Found by reading `rps_game.py`. The redesign should fix each of these.

| # | Issue | Where | Why it matters |
|---|---|---|---|
| 1 | AI card says "NEURAL BOT", but the AI is a Markov chain | line 520 | Inaccurate claim, and judges may ask about it |
| 2 | "CALCULATING ODDS" shows during the countdown, but the AI only decides when it ends | lines 533, 703 | The UI describes something that isn't happening |
| 3 | The canvas size comes from the camera frame, and layout uses fixed pixel values | lines 294, 370-401 | Layout is tied to the webcam's resolution, so a lower-resolution camera would cramp or break it |
| 4 | Guest shares one saved AI memory | lines 752, 176-191 | Each visitor inherits the habits of the visitors before them |
| 5 | The move is read from one frame when the countdown ends | line 702 | A slightly late or flickering hand becomes "NO DETECTION" |
| 6 | Gesture smoothing counts frames, not time | lines 92-93 | Responsiveness changes with FPS |
| 7 | Prediction is deterministic apart from a tiny tie-break | line 241 | Players can learn to exploit it |
| 8 | Transition counts never decay | line 248 | The AI adapts more slowly the longer someone has played |
| 9 | The skeleton is drawn on the frame before resizing | lines 690, 462 | It would turn blurry once the crop zooms in |
| 10 | Can't quit from the name or session screens, and closing the window isn't handled | line 758 | Awkward for running a kiosk |
| 11 | Both `opencv-python` (our requirement) and `opencv-contrib-python` (a MediaPipe dependency) are installed | `requirements.txt`, `venv` | Both supply the `cv2` module, so which one loads is unclear. Keep only the contrib build |

---

## 3. Vision: the hand-only viewport

> **Dropped on 2026-11-02.** I built this (smoothed crop, mask, placement hints) and it was tested with the player. They found it looked bad and wanted the normal camera view. The code was removed. The gesture-reading points in 3.5 still apply. The privacy discussion in 3.3 is why a skeleton-only mode stays on the list.

### 3.1 Pipeline

```
Full camera frame (never displayed)
   → MediaPipe finds 21 landmarks on the full frame
   → Crop controller picks a smoothed square-ish region
   → Hand mask hides everything except the hand
   → Resize to viewport size
   → Draw skeleton at viewport resolution (stays sharp)
```

### 3.2 Crop controller

A landmark bounding box alone won't work well. A fist's box is much smaller than an open palm's, so the view would zoom in and out every time the player changes gesture, right when they are watching it.

- **Set zoom from palm size,** using the distance between wrist and middle-finger knuckle (landmarks 0 and 9). This stays much steadier across gestures. Widen the crop only if the fingers would otherwise be cut off.
- **Smooth position and zoom separately.** Position follows fairly quickly, zoom follows slowly. Add a small dead-zone so the view stays still when the hand barely moves.
- **Limit the zoom** to about 2.5x, so a distant hand isn't enlarged into a blur. Tune this on the real webcam.
- **At frame edges,** fill with the dark background rather than shifting the hand off-centre.
- **When tracking is lost,** hold the last crop for about 0.5 s, then fade to the "show your hand" placeholder. **Never fall back to the full frame.**

### 3.3 Privacy: cropping isn't enough

A hand raised in front of the face still has the face behind it in the crop. So the viewport also uses a **hand mask**:

- Draw thick lines along the landmark connections and fill the palm, then feather the edges with a blur.
- Darken everything outside the mask almost to the background colour.

This is cheap because it only runs on the small crop. It also produces the look of the reference images: a lit hand floating on a dark field.

**Skeleton-only mode** (admin key) hides the video completely and draws only landmarks. Use it where a venue or a visitor's guardian wants no video shown at all.

### 3.4 Placement guidance

Cropping removes the player's sense of where the camera's edges are. Replace that with:

- A small **position radar** in the viewport corner: a dot showing the hand's place in the camera's view, with no video.
- **Chevrons** at the viewport edge when the hand nears the limit ("move left").
- A **"move closer"** hint when the hand is too small to track reliably.

### 3.5 Gesture reading

- **Time-based stability:** vote over the last ~300 ms, not the last 10 frames.
- **Capture window:** take the move from a short window around "GO" (about 150 ms before to 250 ms after), which fixes most false "NO DETECTION" results. Confirm it can't give an advantage: the AI's move is locked first (section 4.3) and hidden until reveal, so the extra time reveals nothing.
- **Show confidence as a stability meter,** based on how consistent the votes are. MediaPipe's own score measures hand detection, not gesture certainty.

---

## 4. AI: the prediction engine

### 4.1 Why the design differs from a simple "add second-order Markov" upgrade

The saved profiles have only **23 and 9 learned transitions** in their active rows. Visitors at an exhibition may play only 10-20 rounds. A second-order table has **27 cells**, so it will barely fill during one visit.

So the first thing to add is a model that learns quickly:

| Expert | What it learns | Cells | Learns useful patterns by |
|---|---|---|---|
| **Frequency** | "Plays Rock a lot" | 3 | ~5 rounds |
| **Win-stay / lose-shift** | Repeat, move up or move down, after a win, loss or tie | 9 | ~8-10 rounds |
| **First-order Markov** | Next move given last move | 9 | ~10-15 rounds |
| **Second-order Markov** | Next move given last two moves | 27 | 30+ rounds, mainly returning players |
| **Anti-AI** (stretch) | "Is this player countering what I just played?" | 9 | ~10 rounds |

The round estimates are starting guesses, and Phase 4's simulator will replace them with measured figures.

### 4.2 How the experts combine

1. **Decay:** multiply counts by about 0.95 per round, a half-life of roughly 13.5 rounds, so old habits fade. Tune this in simulation.
2. **Handle small samples:** `p = (count + α) / (total + 3α)`. With little data, estimates stay near 33%, so two observations can't produce a "90%" prediction.
3. **Weight by track record:** each expert predicts every round, and its weight rises or falls with how well it did (multiplicative weights). This replaces a fixed fallback chain, and lets the UI truthfully say which pattern the AI currently trusts.
4. **Choose by expected score,** not by simply countering the top prediction. This handles close calls like 45% / 45% / 10% properly.
5. **Mix in randomness when the edge is small.** With no clear pattern, the AI plays close to random, which can't be exploited. This also keeps it fair against truly random players.

### 4.3 Fairness and the probability bars

**Live prediction bars during play would break the game.** If the screen says "AI expects ROCK, 70%", the player knows the AI will throw Paper, and simply throws Scissors. The feature meant to show off the AI would let anyone beat it.

| Stage | Shown on the AI panel |
|---|---|
| Ready / countdown | "MOVE LOCKED" and how much evidence the AI has. **No prediction shown** |
| Reveal | AI's move, then the bars animate in: what it expected from you |
| Explanation | One sentence: *"You repeated your move after a win, and the AI expected that."* |

The AI **locks its move when the countdown starts**, before the camera reads the player's throw. Explaining this to visitors is a good answer to "isn't it just cheating by watching your hand?"

**Displaying confidence** always pairs the two values:
- **Prediction strength:** the probability of the top move.
- **Evidence:** LOW, MEDIUM or HIGH, from the decayed sample size. "62%, LOW evidence" is honest in a way a bare "62%" isn't.

### 4.4 Proof it works

- **Simulator** with scripted players: uniform random, cycler, win-stay/lose-shift, biased, and player-switches-strategy-midway.
- **Pass criteria:**
  - Against random: win rate statistically indistinguishable from chance.
  - Against each patterned player: clearly better than the current first-order model.
  - After a strategy switch: measured recovery time improves.
- **Play-test logs:** at least 10 real people, with consent, recording moves only, to tune decay and α. Scripted players alone will flatter the model.
- **Report plainly:** AI prediction accuracy compared with the 33% chance level, with the number of rounds. Real-person results may be modest, and an honest figure is more defensible at an exhibition.

### 4.5 Saved data (version 2)

- Add `"version": 2` and a capped move/outcome history per player. Keep the file name `players_data.json`, which is already git-ignored.
- **Migrate old files:** copy `transitions` into the first-order table, **subtracting the built-in +1 starting count**, since the new formula adds its own. Back up the old file first.
- **Guests:** in-memory only, wiped per visitor. Saves nothing about them except an anonymous score if they join the leaderboard.

---

## 5. Visual design

### 5.1 What to take from the references

| Reference | Take | Leave |
|---|---|---|
| **Glowing wireframe hand and gesture cards** | Glowing landmark nodes, thin bones, dark field, gesture tiles drawn in the same style | Dense mesh as if it were real data; fake FPS and latency values |
| **Cyan circular HUD** | Corner brackets, thin rings, a calm reticle around the hand, restrained line weights | Decorative codes like "G2" or "X5", random numbers, tiny illegible text |
| **Cyber game UI kit** | Chamfered panels, segmented ring gauge, big "3" countdown ring, stat bars, chevrons, warning banner | Heavy glow on everything, fantasy icons, gold button styles |

These are **inspiration only**. All elements get drawn in code, so there are no licensing questions about third-party artwork.

### 5.2 Theme

| Token | Colour | Used for |
|---|---|---|
| `bg` | `#070B14` | Background |
| `panel` | `#0E1524` (~85% opacity) | Panels |
| `stroke` | `#24344F` | Panel borders, grid lines |
| `player` | `#00E5FF` | **Everything belonging to the player** |
| `ai` | `#FF2E88` | **Everything belonging to the AI** |
| `warn` | `#FFB020` | Ties, streaks, warnings only |
| `text` | `#E6EEF8` | Main text |
| `muted` | `#8A9BB5` | Secondary text |

- **Colour means ownership.** A player win is cyan, an AI win is magenta, a tie is amber. Results are always labelled in words as well, so colour is never the only signal.
- **Glow is rationed:** only the hand skeleton, the active countdown ring, and the reveal moment. Tune it on the actual display, ideally in a bright room.
- **Type:** bundle one angular display font for headings and numbers (candidate: Chakra Petch or Rajdhani) and one clean font for small text, in `assets/fonts/`. Check each font's licence before adding it, and fall back to Segoe UI if a file is missing.
- **Minimum text size:** about 24 px at 1080p, readable from 2 m. Most current labels are 16 px.

### 5.3 Gesture icons without image files

Save one reference set of 21 landmarks for each of Rock, Paper and Scissors, then draw the same skeleton style in the move cards: cyan for the player, magenta for the AI. This also replaces the emoji in `CHOICE_ICONS`, which aren't currently used on screen.

### 5.4 Main screen (built)

Two equal cards, Player and AI, under the scoreboard bar:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ PLAYER: ALEX      [ YOU 3 ]  ( 2 )  [ AI 2 ]            STREAK  W L W D W │
├────────────────────────────────────┬─────────────────────────────────────┤
│ YOUR ACTION         ● DETECTED: …  │ AI OPPONENT          MARKOV AI (…)  │
│ ┌────────────────────────────────┐ │ ┌─────────────────────────────────┐ │
│ │      live camera picture       │ │ │   AI's hand hangs from the top  │ │
│ │      + cyan hand skeleton      │ │ │   after the reveal; "DECIDING…" │ │
│ │                                │ │ │   while the countdown runs      │ │
│ └────────────────────────────────┘ │ └─────────────────────────────────┘ │
│  [ rock ]  [ PAPER ]  [ scissors ] │  [ ROCK ]  [ paper ]  [ scissors ]  │
├────────────────────────────────────┴─────────────────────────────────────┤
│        [SPACE] Play   [P] Player   [F] Fullscreen   [D] AI   [R]   [Q]   │
└──────────────────────────────────────────────────────────────────────────┘
```

- The hand pictures are cut from the supplied banner artwork, with no text for the moves. The lit tile shows the player's detected (then final) move, and the AI's revealed move.
- The countdown ring replaces "VS" in the scoreboard bar. The result banner sits between the two cards.
- The Phase 3 redesign (colours, fonts, spacing, animation) and the Phase 5 prediction bars build on this layout.

### 5.5 Screens and flow

```
ATTRACT → READY → COUNTDOWN → REVEAL → EXPLAIN ─┬→ READY (next round)
   ↑                                            └→ SUMMARY (match over) ─┐
   └─────────────────────────────────────────────────────────────────────┘
```

- **Attract:** looping animated skeleton hand, "Show your hand to play", and a privacy line: *"Your hand is tracked live. No video is saved."* A detected hand starts a Guest game.
- **Profiles:** still available through `[P]` for returning players, but no longer the first thing a visitor sees.
- **Ready:** hold a hand steady in view for ~1 s to start, with `[SPACE]` still working. **Any** gesture counts, because requiring an open palm would make visitors begin from Paper and skew the data.
- **Countdown:** large segmented ring and "ROCK... PAPER... SCISSORS... SHOOT!". The AI shows MOVE LOCKED.
- **Reveal:** both moves appear, the winner's panel lights up, the bars animate in.
- **Summary (the takeaway):** final score, the line "The AI predicted you X of Y rounds (chance is about 1 in 3)", a chart of accuracy over the match, and the habit it found most. Returns to Attract after ~20 s, wiping guest data.

### 5.6 Animation

Short and purposeful: panels ease in (~200 ms), score numbers pop on change, the probability bars grow, the reticle slowly rotates. All timed by the clock, never by frame count. Nothing moves while the player needs to concentrate on the countdown number except the ring itself.

---

## 6. Architecture

Fewer files than a full package tree, since one person maintains this. Split a file further only when it gets hard to work with.

```
Rock Paper Scissors AI/
├── main.py                 # New entry point: wiring and main loop
├── rps_game.py             # Current game, untouched, until Phase 7
├── config.py               # All tunable values
├── vision/
│   ├── tracker.py          # Camera + MediaPipe
│   ├── gesture.py          # Classifier and time-based stability
│   └── viewport.py         # Crop controller and hand mask
├── ai/
│   ├── experts.py          # Frequency, WSLS, Markov 1 and 2
│   ├── engine.py           # Weighting, decision, explanation text
│   └── simulate.py         # Scripted players, strategy comparison
├── game/
│   ├── session.py          # State machine, scoring, match rules
│   └── store.py            # Save/load, migration, guest handling
├── ui/
│   ├── theme.py            # Colours, fonts, scaling
│   ├── widgets.py          # Panels, rings, bars, skeleton drawing
│   └── screens.py          # One draw function per screen
├── assets/fonts/
└── tests/
```

**Rules that keep it testable:**
- `ai/` and `game/` import no OpenCV or Pillow, so they can be tested with no camera.
- `ui/` only reads state and never changes it.
- Time gets passed in as a value, so tests don't need to wait on real timers.

**Engine interface** (fixed early, so the UI can be built against it before the new AI exists):

```python
class Prediction:
    probs: dict[str, float]     # {"ROCK": .., "PAPER": .., "SCISSORS": ..}
    evidence: str               # "LOW" | "MEDIUM" | "HIGH"
    top_expert: str             # which pattern is most trusted
    ai_move: str

engine.lock_move(context) -> Prediction     # called when the countdown starts
engine.observe(player_move, outcome) -> str  # learns, returns the explanation
```

**Rendering performance.** The current code composites a full RGBA image with Pillow every frame. At 1080p, added to MediaPipe's CPU load, this is likely to be the main bottleneck, but measure before optimising.

1. Pre-render static panels once, and cache text images.
2. Draw the camera, skeleton and meters directly with NumPy/OpenCV.
3. Use Pillow only where text changes.
4. If needed, render at a lower internal resolution and scale up, or run camera and MediaPipe on a background thread.
5. Letterbox to the display's aspect ratio, so nothing stretches on a non-16:9 screen.

**Target:** at least 24 FPS sustained on the exhibition laptop, and hand-to-screen delay that feels immediate.

---

## 7. Build phases

Each phase ends with something runnable.

### Phase 0: Safe starting point
- [x] Create a `redesign` branch and commit the outstanding work on `rps_game.py` and `.gitignore`
- [x] Fix `requirements.txt` to rely on `opencv-contrib-python`, pin tested versions, and repair the venv
- [x] Add `pytest` as a dev dependency (`requirements-dev.txt`)
- [x] Measure baseline timings on the closest available machine
- [ ] Play a full round of the current game on the repaired venv

**Done when:** the current game runs from a clean install and baseline FPS is recorded.

**Baseline, 2026-11-02** (Ryzen 5 7640HS, CPU only, 1280 × 720 webcam, no hand in view, `imshow` not included, not necessarily the exhibition laptop):

| Step | Median | 95th percentile |
|---|---|---|
| Camera read | 3.3 ms | 16.5 ms |
| MediaPipe | 18.2 ms | 25.2 ms |
| UI render at 720p | 27.1 ms | 42.2 ms |
| UI render at 1080p | 44.5 ms | 67.3 ms |

This estimates about 20 FPS for the current game, below the 24 FPS target. UI rendering costs more than hand tracking, and a 1080p canvas would make it worse, so the rendering work in section 6 is required. Timings with a hand in view still need measuring.

### Phase 1: Structure
- [x] Create the modules and move logic over with the same behaviour (`config`, `vision/`, `ai/`, `game/`, `ui/`; `ui/screens.py` is the old screen code, ported as-is)
- [x] Add tests for winner logic, gesture classification and save/load (50 tests, no camera needed)
- [x] Add the engine interface, backed by the existing Markov logic
- [ ] Confirm by hand that `python main.py` plays like `rps_game.py`

**Done when:** `main.py` plays the same game as `rps_game.py`, and tests run with no camera.

**Changes from the old game, on purpose:** a profile is only saved once chosen, so nothing is written before a name is entered. The AI locks its move when the countdown starts. Closing the window quits. Labels fixed: "NEURAL BOT" is now "MARKOV AI", and "CALCULATING ODDS" is now "MOVE LOCKED".

### Phase 2: Player vs AI cards (changed from "Hand viewport")
- [x] Built the hand-only viewport (crop, mask, hints), then **removed it**: the player found it looked bad
- [x] Camera picture inside the player's card, drawn at card size with the skeleton on top (`ui/camera.py`); a frame of a different shape is cropped around the centre, never stretched
- [x] Gesture pictures replace the move names: three tiles in each card with the active move lit, and the AI's hand shown large on reveal (`ui/gestures.py`)
- [x] Icons cut from the supplied artwork by `tools/make_gesture_icons.py`; falls back to text if the files are missing
- [ ] Confirm by hand that it looks right on the real display, with a real hand in the camera

**Done when:** the player says the screen looks right. Cutting the hands out of the artwork worked automatically using the white sticker outline, but I have only seen it on a stand-in camera picture, not your webcam.

### Phase 3: New interface (design decided, not built yet)
Decisions so far, from reviewing `design/ui-mockup.html`:
- **Light mode.** Soft white background, white cards, deep blue for the player and rose for the AI. The older dark neon look is dropped.
- **Dark where the artwork needs it.** The three move tiles and the AI's panel stay dark (navy and purple), because the hand pictures have white outlines and were drawn for dark backgrounds. They stand out well against the light screen.
- **Camera skeleton** is drawn in blue over a white halo, so it shows on any room.
- **Credit line:** "Created by SMS Abeyrathne · 235501H · BSc (Hons) Artificial Intelligence" on the start screen and under the match summary. The game itself doesn't mention any event or the university.
- **Still to decide:** which suggested screens to build (start screen, camera check, chant countdown, round-by-round, leaderboard, camera problem, admin, privacy mode) and which arrangement of the main screen to use. Waiting for notes on the mockup.

Work once the design is final:
- [ ] Move every colour into one theme definition, so screens don't hardcode them
- [ ] Rebuild the screens in light mode, at any resolution
- [ ] Performance pass against the 24 FPS target

**Done when:** it looks like the approved mockup, at target FPS on 720p and 1080p.

### Phase 4: Prediction engine (done, pending real play-tests)
- [x] Four experts (frequency, last move, last two moves, win-stay/lose-shift) with decay, smoothing, track-record weighting and an expected-score choice (`ai/engine.py`)
- [x] Simulator with seven scripted players and the first version's AI as a yardstick (`python -m ai.simulate`), plus pass-criteria tests (`tests/test_simulation.py`)
- [x] Data v2: each profile now stores the AI's memory under `engine` and still writes the first version's `transitions`, so `rps_game.py` can read it. Old profiles load into the new engine. Guests are never saved, and each guest starts with a blank AI
- [ ] Play-test with at least 10 real people and re-tune (`config.py`, AI section)

**Simulation results** (400 games of 30 rounds each; "net" is AI wins minus AI losses per round, 0 means a fair match):

| Player | First version | New AI | New AI wins |
|---|---|---|---|
| Random | +0.002 | +0.008 | 34% |
| Favours rock (60%) | +0.243 | +0.229 | 47% |
| Cycles R-P-S | +0.866 | +0.861 | 90% |
| Repeats R-R-P | +0.236 | **+0.795** | 84% |
| Win-stay, lose-shift | +0.071 | **+0.839** | 88% |
| Counters the AI's last move | -0.066 | **+0.857** | 91% |
| Switches habit midway | +0.302 | +0.306 | 53% |

The new AI is fair against random play and about equal to the first version on simple habits, within noise (roughly 2 standard errors on the biased player). It is much stronger on patterns that depend on the last two moves or on the result of the last round. In longer games, forgetting old habits matters: with no decay the AI scores 0.40 against a player who changes habit twice, against 0.51 with the chosen decay.

**How fast it learns a pattern.** A player throwing rock, rock, paper on repeat: the first version predicts the rocks but never the paper, so it never wins those rounds. The new AI predicts the third paper correctly (round 9) and every round after that. The first play-test matched this: with the original smoothing of 1.0 it only got the paper on the fourth try, so smoothing was lowered to 0.5, which improved every patterned player slightly and kept random play fair.

**Limits to know about**
- The tuning was done against my own scripted players, which are simpler than people. Real play-tests may change the best values.
- Against a random player the AI states its top guess is about 45% likely, but it is right 33% of the time. Count-based estimates from a few observations look more confident than they are. Phase 5 must not show the raw number alone: show it next to the one-in-three chance level, or recalibrate it.
- Evidence thresholds (LOW under 2, MEDIUM 2-5, HIGH 5 or more observations) come from the simulation, where accuracy jumps from about 53% to 78% at 2 observations and levels off near 80%.
- No backup of the player file is made on upgrade. The old `transitions` entries are kept as they were, so nothing is lost.

### Phase 5: Showing the AI's thinking (built, pending a first-time-player test)
- [x] The AI's move is locked when the countdown starts. During the countdown the AI card shows only "MOVE LOCKED" and an evidence level, never what it expects
- [x] **Decision after play-testing:** showing the AI's expectation after every round tells the player which habit to break, so it is hidden by default ("challenge mode"). Press `H` for learn mode, which shows it after each reveal. The summary after a match always shows what the AI learned (`LEARN_MODE_DEFAULT` in `config.py`)
- [x] In learn mode, after the reveal, the AI card shows three bars: what the AI expected you to throw, with your actual move outlined, a white tick at one-in-three chance, and the evidence level (LOW, MEDIUM, HIGH)
- [x] One sentence on what happened, built from the AI's real reasoning, for example: "The AI expected PAPER (77%) because you often throw paper after rock then rock. But you threw SCISSORS. You broke your pattern!" (`explain()` in `ai/engine.py`)
- [x] Match summary after 15 rounds (`MATCH_ROUNDS` in `config.py`, 0 = play on without end): the score, how many throws the AI predicted against the one-in-three chance level, a chart of its running accuracy, and up to three habits it found (`game/summary.py`). `SPACE` after the last result opens it, and `SPACE` again starts a new match. Running totals carry over
- [x] Rounds where no hand was detected don't count toward the match, and teach the AI nothing
- [ ] Test with a first-time player: can they say what the AI noticed, without help?

**Changes from the plan**
- The "Your habits" panel on the player card was not built. The habits appear in the summary instead.
- Overconfidence is handled by showing the chance tick and the evidence level beside every percentage, not by recalibrating the numbers.
- The summary has no automatic return to a start screen yet. That belongs with the attract mode in Phase 6.

### Phase 6: Exhibition readiness
- [ ] Attract mode, hands-free start, match length, auto-return and guest wipe
- [ ] Leaderboard with short nicknames only, plus an admin key to clear it
- [ ] Kiosk controls: admin overlay, safe quit, no crash on camera disconnect
- [ ] Play-test with at least 10 people, plus a long unattended run of several hours

**Done when:** a stranger can start and finish without help, and it survives a long run.

### Phase 7: Finish
- [ ] Update `README.md`, including screenshots and accurate claims: remove "30+ FPS" unless measured
- [ ] Make `main.py` the default, and retire `rps_game.py` and the `rps_mediapipe.py` prototype

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Faces of visitors or bystanders show in the camera card | Skeleton-only mode as an option, and a privacy line on the attract screen |
| Exhibition laptop can't hold 24 FPS | Test there in Phase 0. Lower internal resolution, background-thread tracking |
| Venue lighting hurts tracking | Test on site early. Bring a lamp and a plain backdrop |
| Visitors play too few rounds to show learning | Fast-learning experts first. Summary reports evidence honestly |
| Real players are near-random, so the AI's edge is small | Accept and report it honestly. The explanations remain interesting either way |
| A bystander's hand gets tracked | Lock onto the current hand, and guide players to stand on a floor marker |
| Scope grows past the deadline | Phases 0-3 and the core of 4-5 make a complete exhibit. Anti-AI, leaderboard and skeleton-only mode can be cut |

---

## 9. Decisions needed

Defaults apply unless you say otherwise.

| Question | Default |
|---|---|
| When is the exhibition, and how long do we have? | Unknown. **This decides how much of Phase 6 fits** |
| What laptop, webcam and display will it run on? | Mid-range laptop, 720p webcam, 1080p display |
| How many rounds per visitor? | 15, or first to 8 |
| Will minors play? | Assume yes: Guest by default, no real names needed, no video shown beyond the masked hand |
| Keep named profiles at the exhibition? | Yes, but optional and off the main path |

---

## 10. Where this differs from the notes you shared

The notes' main advice stands: keep the stack, crop to the hand, use decay, and do the UI early. I changed six details:

1. **Probability bars appear after the reveal, not live.** Live bars tell the player how to beat the AI (section 4.3).
2. **Win-stay/lose-shift moves up, second-order Markov moves down.** With 10-20 rounds per visitor, the 9-cell model learns far sooner than the 27-cell one (section 4.1).
3. **Experts are weighted by results instead of using a fallback chain.** This is more robust, and tells the UI which pattern to credit (section 4.2).
4. **Crop size comes from palm size, not the bounding box.** This avoids zoom pumping when gestures change (section 3.2).
5. **Cropping is backed by a hand mask.** A crop alone can still show a face behind the hand (section 3.3). *(Later dropped: see Phase 2.)*
6. **Structure comes before the UI redesign, with a smaller folder tree.** Otherwise the new UI is built on the same global state, then has to be rewritten (section 6).
