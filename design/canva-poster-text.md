# Text for the Canva poster (FIT EXPO template)

Paste each block into the matching box of the template. Everything below comes from the project as it is now.

## Header
- **PROJECT NAME:** ROCK PAPER SCISSORS AI
- **Sub Title:** AN AI THAT LEARNS YOUR HABITS

## Footer (the template has five member boxes; use one)
- **TEAM NAME:** (delete, or leave blank)
- **Member name:** SMS Abeyrathne
- **Member index:** 235501H · BSc (Hons) Artificial Intelligence
- Delete the other four member boxes.
- **QR:** the GitHub repository for this project.

## PROJECT OVERVIEW
Rock Paper Scissors AI is a real-time computer vision game. You play with your bare hand in front of a webcam against an AI that learns your habits as the match goes on. After 15 rounds it shows what it found out about you, and how much better than chance it could predict your throws.

## PROBLEM STATEMENT
Simple Rock Paper Scissors bots play at random or follow one fixed rule, so they are either pure luck or easy to beat. When an AI does learn from the player, the player rarely sees what it learned, and camera games often feel like a black box that is hard to trust.

## PROPOSED SOLUTION
A webcam game where MediaPipe tracks 21 points on the hand and a geometric classifier reads rock, paper or scissors. Four small predictors learn the player's habits, the AI usually plays the counter to what it expects, and a report at the end explains what it noticed.

## INNOVATIVE & UNIQUE FEATURES
- Four predictors in one AI: how often you throw each move, what follows your last one or two moves, and how you react to a win or loss. The best performer counts most.
- Fair by design: the AI locks its move before your throw is read.
- Forgets old habits, so it keeps up when you change tactics.
- Honest numbers: every guess is shown beside the one-in-three chance level.
- Leaderboard and Learn mode: the start screen ranks who beat the AI most. Press H to see what it expected after every round.
- Private: no video is stored, guests are never saved, and a skeleton-only view can hide faces.

## TECHNOLOGIES USED
- Python 3.12 - game logic, AI engine and tests
- MediaPipe Hands - 21-point hand landmark tracking
- OpenCV - camera capture and the window
- NumPy - the AI's decaying probability tables
- Pillow - text, panels and the gesture artwork
- JSON - saved player profiles and the leaderboard

## SYSTEM ARCHITECTURE (boxes, left to right)
Webcam → OpenCV (capture and mirror) → MediaPipe Hands (21 landmarks) → Gesture classifier (rock / paper / scissors) → Game state machine (ready, countdown, reveal) → Adaptive AI (four predictors) → Display (OpenCV + Pillow) · Players & board (JSON file) · Match report (what it learned)

Caption: Camera frame → hand landmarks → move → game → AI reply (locked before the throw is read).

## DEMO / KEY SCREENS / WORKFLOW
Pictures (screen-framed, transparent, in `design/poster-assets/`): `screen-05-ready.png`, `screen-07-you-win.png`, `screen-10-learn-mode.png`, `screen-12-report.png`
- Ready: live camera with the hand skeleton and the match score.
- Reveal: the AI's hand against yours. Its thinking stays hidden during play.
- Learn mode: what the AI expected, with the one-in-three chance line.
- Report card: a title, how well the AI read you, and the habits it found.

Workflow strip: NAME (join the leaderboard) › CAMERA CHECK (hold your hand up) › COUNTDOWN (AI locks its move) › THROW + REVEAL (gesture read, winner shown) › REPORT (what it learned)

## PRACTICAL IMPACT, RESULTS & NEXT STEPS
**Impact:** in about two minutes visitors see how an AI learns from behaviour, and why being unpredictable beats it.

**Results (simulation, 400 games of 30 rounds):** about fair against a random player, and the AI wins 84-91% of rounds against players with a pattern (R-R-P, win-stay/lose-shift, counter-the-AI).

**Expo trial:** add after the expo: number of players, average % of throws the AI predicted.

**Next steps:** tuning the AI on real players, an auto-restart launcher for unattended use, and saving the leaderboard to a file.
