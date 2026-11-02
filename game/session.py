"""Game state, scoring and keyboard rules. Knows nothing about cameras or drawing."""
from collections import deque

import config
from ai.engine import CHOICES, AdaptiveEngine, explain
from game.summary import RoundRecord, summarize

BEATS = {"ROCK": "SCISSORS", "PAPER": "ROCK", "SCISSORS": "PAPER"}
GUEST_NAME = "Guest"  # never saved: each guest starts fresh and leaves nothing behind

STATE_NAME_INPUT = "NAME_INPUT"          # Entering player name
STATE_SESSION_CHOICE = "SESSION_CHOICE"  # Choose Start New vs Resume
STATE_IDLE = "IDLE"                      # Waiting for player to press SPACE
STATE_COUNTDOWN = "COUNTDOWN"            # 3, 2, 1 countdown
STATE_SHOW_RESULT = "RESULT"             # Showing winner of current round
STATE_SUMMARY = "SUMMARY"                # End of a match: what the AI learned

ACTION_QUIT = "quit"
ACTION_TOGGLE_FULLSCREEN = "fullscreen"

KEY_ENTER = 13
KEY_ESC = 27
KEY_BACKSPACE = 8
KEY_SPACE = 32


def determine_winner(p_move, a_move):
    if p_move not in CHOICES:
        return "INVALID"
    if p_move == a_move:
        return "TIE"
    if BEATS[p_move] == a_move:
        return "PLAYER"
    return "AI"


class GameSession:
    def __init__(self, store, engine=None):
        self.store = store
        self.engine = engine or AdaptiveEngine()

        self.state = STATE_NAME_INPUT
        self.state_start_time = 0.0
        self.countdown_duration = config.COUNTDOWN_SECONDS

        self.player_name = None  # None until a profile is chosen, so nothing is saved before then
        self.temp_player_name = ""
        self.input_text = ""
        self.score_player = 0
        self.score_ai = 0
        self.score_ties = 0
        self.streak = 0
        self.best_streak = 0
        self.match_history = deque(maxlen=config.MATCH_HISTORY_LENGTH)

        self.prev_score_player = 0
        self.prev_score_ai = 0
        self.prev_score_ties = 0
        self.prev_best_streak = 0

        self.player_move = None
        self.ai_move = None
        self.round_result = None
        self.prediction = None
        self.explanation = ""
        self.learn_mode = config.LEARN_MODE_DEFAULT
        self.match_log = []      # one RoundRecord per round with a detected move
        self.summary = None

    @property
    def tracking_active(self):
        return self.state not in (STATE_NAME_INPUT, STATE_SESSION_CHOICE, STATE_SUMMARY)

    @property
    def match_complete(self):
        return config.MATCH_ROUNDS > 0 and len(self.match_log) >= config.MATCH_ROUNDS

    def start_new_match(self):
        self.match_log = []
        self.summary = None
        self.explanation = ""
        self.player_move = self.ai_move = self.round_result = None
        self.state = STATE_IDLE

    def save(self):
        if not self.player_name or self.player_name == GUEST_NAME:
            return
        self.store.save_player(self.player_name, {
            "score_player": self.score_player,
            "score_ai": self.score_ai,
            "score_ties": self.score_ties,
            "best_streak": self.best_streak,
            "engine": self.engine.to_dict(),
            # The first version's format, so rps_game.py can still read this profile
            "transitions": self.engine.legacy_transitions(),
        })

    def switch_to_player(self, name, resume_scores=False):
        self.player_name = name.strip() or "Player 1"
        self.match_history.clear()
        self.match_log = []
        self.summary = None
        self.streak = 0
        self.score_player = self.score_ai = self.score_ties = 0
        self.best_streak = 0

        saved = None if self.player_name == GUEST_NAME else self.store.load_all().get(self.player_name)
        self.engine.load_record(saved)
        if saved:
            self.best_streak = saved.get("best_streak", 0)
            if resume_scores:
                self.score_player = saved.get("score_player", 0)
                self.score_ai = saved.get("score_ai", 0)
                self.score_ties = saved.get("score_ties", 0)
        else:
            self.save()

    def start_round(self, now):
        self.prediction = self.engine.lock_move()
        self.state = STATE_COUNTDOWN
        self.state_start_time = now

    def update(self, now, live_gesture):
        if self.state == STATE_COUNTDOWN and now - self.state_start_time >= self.countdown_duration:
            self._finish_round(now, live_gesture)

    def _finish_round(self, now, live_gesture):
        self.player_move = live_gesture
        self.ai_move = self.prediction.ai_move
        self.round_result = determine_winner(self.player_move, self.ai_move)

        if self.round_result == "PLAYER":
            self.score_player += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            self.match_history.append("W")
        elif self.round_result == "AI":
            self.score_ai += 1
            self.streak = 0
            self.match_history.append("L")
        elif self.round_result == "TIE":
            self.score_ties += 1
            self.match_history.append("D")

        self.explanation = explain(self.prediction, self.player_move)
        if self.round_result != "INVALID":
            expected = self.prediction.expected
            self.match_log.append(RoundRecord(
                self.player_move, self.ai_move, self.round_result, expected,
                self.prediction.probs[expected] if expected else 0.0))
        self.engine.observe(self.player_move, self.ai_move)
        self.save()
        self.state = STATE_SHOW_RESULT
        self.state_start_time = now

    def handle_key(self, key, now):
        """Apply a key press. Returns an ACTION_ the window has to act on, or None."""
        if self.state == STATE_NAME_INPUT:
            self._handle_name_key(key)
            return None
        if self.state == STATE_SESSION_CHOICE:
            self._handle_session_choice_key(key)
            return None

        if key in (ord("q"), ord("Q")):
            self.save()
            return ACTION_QUIT
        if key in (ord("f"), ord("F")):
            return ACTION_TOGGLE_FULLSCREEN
        if key in (ord("p"), ord("P")):
            self.save()
            self.input_text = self.player_name
            self.state = STATE_NAME_INPUT
        elif key == KEY_SPACE:
            if self.state == STATE_SHOW_RESULT and self.match_complete:
                self.summary = summarize(self.match_log)
                self.state = STATE_SUMMARY
            elif self.state == STATE_SUMMARY:
                self.start_new_match()
            elif self.state in (STATE_IDLE, STATE_SHOW_RESULT):
                self.start_round(now)
        elif key in (ord("d"), ord("D")):
            self.engine.toggle_mode()
        elif key in (ord("h"), ord("H")):
            self.learn_mode = not self.learn_mode
        elif key in (ord("r"), ord("R")):
            self.score_player = self.score_ai = self.score_ties = 0
            self.streak = 0
            self.match_history.clear()
            self.save()
            self.start_new_match()
        return None

    def _handle_name_key(self, key):
        if key == KEY_ENTER:
            chosen_name = self.input_text.strip() or "Player 1"
            saved = self.store.load_all().get(chosen_name)
            if saved:
                self.temp_player_name = chosen_name
                self.prev_score_player = saved.get("score_player", 0)
                self.prev_score_ai = saved.get("score_ai", 0)
                self.prev_score_ties = saved.get("score_ties", 0)
                self.prev_best_streak = saved.get("best_streak", 0)
                self.state = STATE_SESSION_CHOICE
            else:
                self.switch_to_player(chosen_name)
                self.state = STATE_IDLE
        elif key == KEY_ESC:
            self.switch_to_player(GUEST_NAME)
            self.state = STATE_IDLE
        elif key == KEY_BACKSPACE:
            self.input_text = self.input_text[:-1]
        elif 32 <= key <= 126 and len(self.input_text) < config.NAME_MAX_LENGTH:
            self.input_text += chr(key)

    def _handle_session_choice_key(self, key):
        if key in (KEY_ENTER, ord("n"), ord("N")):
            self.switch_to_player(self.temp_player_name)
            self.state = STATE_IDLE
        elif key in (ord("c"), ord("C")):
            self.switch_to_player(self.temp_player_name, resume_scores=True)
            self.state = STATE_IDLE
        elif key in (KEY_ESC, ord("b"), ord("B")):
            self.state = STATE_NAME_INPUT
