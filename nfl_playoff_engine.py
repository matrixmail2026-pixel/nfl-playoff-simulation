#!/usr/bin/env python3
"""
NFL Playoff Simulation Engine
Live-data model using NFLMeta API

License: Creative Commons Attribution 4.0 International (CC BY 4.0)
"""

import math
import os
import random
import time

import numpy as np
import pandas as pd
import requests


# =====================================================================
# 0. CONFIGURATION
# =====================================================================

NFLMETA_BASE = "https://nflmeta.org/api/v1"

API_KEY = os.getenv("NFLMETA_API_KEY")
SEASON = 2026
REQUEST_INTERVAL = 3.1
TEAMS_PER_CONFERENCE = 7
USE_FIXED_RANDOM_SEED = False

if USE_FIXED_RANDOM_SEED:
    random.seed(42)
    np.random.seed(42)


# =====================================================================
# 1. NFLMETA API CLIENT
# =====================================================================

class NFLMetaClient:
    """Thin REST client for NFLMeta with rate-limit handling."""

    def __init__(self, api_key):
        if not api_key:
            raise RuntimeError(
                "NFLMETA_API_KEY is missing.\n\n"
                "Set it before running the model."
            )

        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-NFLMeta-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "NFL-Rating-Engine/1.0"
        })

        self.last_request_time = 0.0

    def get(self, endpoint, params=None):
        """GET request with rate-limit and transient-error handling."""

        elapsed = time.time() - self.last_request_time

        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)

        url = f"{NFLMETA_BASE}{endpoint}"

        response = self.session.get(
            url,
            params=params,
            timeout=30
        )

        self.last_request_time = time.time()

        if response.status_code == 429:
            retry_after = int(
                response.headers.get("Retry-After", "10")
            )
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return self.get(endpoint, params)

        if response.status_code >= 500:
            time.sleep(5)
            return self.get(endpoint, params)

        response.raise_for_status()

        payload = response.json()

        if "error" in payload:
            raise RuntimeError(payload["error"])

        return payload.get("data", payload)


# =====================================================================
# 2. DATA EXTRACTION HELPERS
# =====================================================================

def first_value(obj, possible_keys, default=None):
    """Find the first matching field in a dictionary."""

    if isinstance(obj, dict):
        for key in possible_keys:
            if key in obj and obj[key] is not None:
                return obj[key]

        for value in obj.values():
            result = first_value(
                value,
                possible_keys,
                default=None
            )
            if result is not None:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = first_value(
                item,
                possible_keys,
                default=None
            )
            if result is not None:
                return result

    return default


def recursive_rows(obj):
    """Find list-like rows inside an API response."""

    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        if "data" in obj:
            return recursive_rows(obj["data"])

        for key in (
            "standings",
            "teams",
            "games",
            "roster",
            "rows",
            "items"
        ):
            if key in obj and isinstance(obj[key], list):
                return obj[key]

    return []


# =====================================================================
# 3. DATA INGESTION & MODEL RATING ENGINE
# =====================================================================

class NFLRatingEngine:
    """Live-data NFL playoff rating and simulation engine."""

    def __init__(self, season=SEASON, api_key=None):
        self.season = season
        self.api = NFLMetaClient(api_key or API_KEY)
        self.weights = {
            "pass_off_epa": 0.40,
            "pass_def_epa": 0.25,
            "rush_off_epa": 0.15,
            "trench_mass": 0.10,
            "narrative_adjustment": -0.05
        }

    def fetch_standings(self):
        data = self.api.get(
            "/standings",
            params={
                "season": self.season,
                "limit": 100
            }
        )
        return recursive_rows(data)

    def normalize_standings(self, rows):
        normalized = []

        for row in rows:
            team = first_value(
                row,
                [
                    "abbr",
                    "team_abbr",
                    "team",
                    "team_abbreviation"
                ]
            )

            conference = first_value(
                row,
                [
                    "conference",
                    "conf"
                ]
            )

            wins = first_value(
                row,
                [
                    "wins",
                    "win",
                    "w"
                ],
                0
            )

            losses = first_value(
                row,
                [
                    "losses",
                    "loss",
                    "l"
                ],
                0
            )

            ties = first_value(
                row,
                [
                    "ties",
                    "tie",
                    "t"
                ],
                0
            )

            if not team or not conference:
                continue

            try:
                wins = int(wins or 0)
                losses = int(losses or 0)
                ties = int(ties or 0)
            except (ValueError, TypeError):
                wins = losses = ties = 0

            normalized.append({
                "team": str(team).upper(),
                "conf": str(conference).upper(),
                "wins": wins,
                "losses": losses,
                "ties": ties
            })

        df = pd.DataFrame(normalized)

        if df.empty:
            raise RuntimeError(
                "NFLMeta standings response could not be parsed."
            )

        return df

    def build_provisional_playoff_field(self):
        standings = self.fetch_standings()
        df = self.normalize_standings(standings)

        df["conf"] = df["conf"].replace({
            "AFC": "AFC",
            "NFC": "NFC"
        })

        playoff_teams = []

        for conference in ["AFC", "NFC"]:
            conf_df = df[
                df["conf"] == conference
            ].copy()

            if conf_df.empty:
                raise RuntimeError(
                    f"No {conference} standings found."
                )

            conf_df = conf_df.sort_values(
                by=[
                    "wins",
                    "ties",
                    "losses"
                ],
                ascending=[
                    False,
                    False,
                    True
                ]
            ).head(TEAMS_PER_CONFERENCE)

            conf_df["seed"] = range(
                1,
                len(conf_df) + 1
            )

            playoff_teams.append(conf_df)

        result = pd.concat(
            playoff_teams,
            ignore_index=True
        )

        return result

    def fetch_team_games(self, team):
        data = self.api.get(
            "/games",
            params={
                "season": self.season,
                "team": team,
                "limit": 100
            }
        )
        return recursive_rows(data)

    def collect_playoff_team_games(self, teams):
        games = {}

        for team in teams:
            rows = self.fetch_team_games(team)

            for game in rows:
                game_id = first_value(
                    game,
                    [
                        "id",
                        "game_id"
                    ]
                )

                if game_id is not None:
                    games[str(game_id)] = game

        return games

    def fetch_game_plays(self, game_id):
        data = self.api.get(
            "/plays",
            params={
                "game_id": game_id,
                "skip_markers": "true",
                "limit": 1000
            }
        )
        return recursive_rows(data)

    @staticmethod
    def classify_play(play):
        play_type = str(
            first_value(
                play,
                [
                    "play_type",
                    "type"
                ],
                ""
            )
        ).lower()

        if play_type in {
            "pass",
            "passing",
            "complete_pass",
            "incomplete_pass",
            "sack",
            "scramble"
        }:
            return "pass"

        if play_type in {
            "run",
            "rush",
            "rushing"
        }:
            return "rush"

        return None

    @staticmethod
    def get_epa(play):
        value = first_value(
            play,
            [
                "epa",
                "expected_points_added"
            ]
        )

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def get_offense_team(play):
        return first_value(
            play,
            [
                "possession_team",
                "offense_team",
                "offensive_team",
                "posteam"
            ]
        )

    @staticmethod
    def get_home_team(game):
        return first_value(
            game,
            [
                "home_team",
                "home_abbr"
            ]
        )

    @staticmethod
    def get_away_team(game):
        return first_value(
            game,
            [
                "away_team",
                "away_abbr"
            ]
        )

    def calculate_team_epa(self, playoff_df, games):
        teams = playoff_df["team"].tolist()

        records = {
            team: {
                "pass_off": [],
                "rush_off": [],
                "pass_def": []
            }
            for team in teams
        }

        processed_games = set()

        for game_id, game in games.items():
            if game_id in processed_games:
                continue

            processed_games.add(game_id)

            home = self.get_home_team(game)
            away = self.get_away_team(game)

            if not home or not away:
                continue

            home = str(home).upper()
            away = str(away).upper()

            if (home not in teams and away not in teams):
                continue

            plays = self.fetch_game_plays(game_id)

            for play in plays:
                category = self.classify_play(play)

                if category is None:
                    continue

                epa = self.get_epa(play)

                if epa is None:
                    continue

                offense = self.get_offense_team(play)

                if offense:
                    offense = str(offense).upper()

                if offense not in {home, away}:
                    continue

                defense = (
                    away
                    if offense == home
                    else home
                )

                if offense in records:
                    if category == "pass":
                        records[
                            offense
                        ]["pass_off"].append(epa)

                    elif category == "rush":
                        records[
                            offense
                        ]["rush_off"].append(epa)

                if (
                    category == "pass"
                    and defense in records
                ):
                    records[
                        defense
                    ]["pass_def"].append(-epa)

        result = []

        for team in teams:
            pass_off = records[team]["pass_off"]
            rush_off = records[team]["rush_off"]
            pass_def = records[team]["pass_def"]

            result.append({
                "team": team,
                "pass_off": (
                    np.mean(pass_off)
                    if pass_off
                    else 0.0
                ),
                "pass_def": (
                    np.mean(pass_def)
                    if pass_def
                    else 0.0
                ),
                "rush_off": (
                    np.mean(rush_off)
                    if rush_off
                    else 0.0
                ),
                "pass_off_samples": len(pass_off),
                "pass_def_samples": len(pass_def),
                "rush_off_samples": len(rush_off)
            })

        return pd.DataFrame(result)

    def calculate_trench_mass(self, playoff_df):
        results = []

        for team in playoff_df["team"]:
            roster_data = self.api.get(
                f"/teams/{team}/roster",
                params={
                    "season": self.season
                }
            )

            roster = recursive_rows(roster_data)

            ol_weights = []
            dl_weights = []

            for player in roster:
                position = first_value(
                    player,
                    [
                        "position",
                        "pos"
                    ]
                )

                weight = first_value(
                    player,
                    [
                        "weight",
                        "weight_lbs",
                        "weight_pounds"
                    ]
                )

                if position is None or weight is None:
                    continue

                try:
                    weight = float(weight)
                except (ValueError, TypeError):
                    continue

                position = str(position).upper()

                if position in {
                    "C",
                    "G",
                    "OG",
                    "OL",
                    "OT",
                    "T"
                }:
                    ol_weights.append(weight)

                elif position in {
                    "DL",
                    "DT",
                    "DE",
                    "NT",
                    "EDGE"
                }:
                    dl_weights.append(weight)

            if ol_weights and dl_weights:
                trench_difference = (
                    np.mean(ol_weights)
                    -
                    np.mean(dl_weights)
                )
            else:
                trench_difference = 0.0

            results.append({
                "team": team,
                "ol_dl_mass_diff": trench_difference
            })

        return pd.DataFrame(results)

    def narrative_hype(self, playoff_df):
        return pd.DataFrame({
            "team": playoff_df["team"],
            "narrative_hype": 0.0
        })

    def fetch_api_team_stats(self):
        playoff_df = (
            self.build_provisional_playoff_field()
        )

        teams = playoff_df["team"].tolist()

        print(
            f"Building provisional {len(teams)}-team "
            f"playoff field from {self.season} standings..."
        )

        games = self.collect_playoff_team_games(
            teams
        )

        print(
            f"Found {len(games)} unique games."
        )

        epa_df = self.calculate_team_epa(
            playoff_df,
            games
        )

        trench_df = self.calculate_trench_mass(
            playoff_df
        )

        narrative_df = self.narrative_hype(
            playoff_df
        )

        df = playoff_df.merge(
            epa_df,
            on="team",
            how="left"
        )

        df = df.merge(
            trench_df,
            on="team",
            how="left"
        )

        df = df.merge(
            narrative_df,
            on="team",
            how="left"
        )

        return df

    def compute_composite_rating(self, df):
        df = df.copy()

        df["rating"] = (
            df["pass_off"]
            * self.weights["pass_off_epa"]

            +

            df["pass_def"]
            * self.weights["pass_def_epa"]

            +

            df["rush_off"]
            * self.weights["rush_off_epa"]

            +

            (
                df["ol_dl_mass_diff"]
                / 20.0
            )
            * self.weights["trench_mass"]

            +

            df["narrative_hype"]
            * self.weights["narrative_adjustment"]
        )

        return df


# =====================================================================
# 4. MATCHUP & PLAYOFF BRACKET SIMULATION
# =====================================================================

def simulate_game(team_a, team_b):
    rating_diff = (
        team_a["rating"]
        -
        team_b["rating"]
    )

    win_prob_a = (
        1.0
        /
        (
            1.0
            +
            math.exp(-rating_diff * 15.0)
        )
    )

    if random.random() < win_prob_a:
        return team_a

    return team_b


def run_conference_playoffs(conf_teams):
    teams_by_seed = {
        int(t["seed"]): t
        for _, t in conf_teams.iterrows()
    }

    wc_winners = [
        simulate_game(
            teams_by_seed[2],
            teams_by_seed[7]
        ),

        simulate_game(
            teams_by_seed[3],
            teams_by_seed[6]
        ),

        simulate_game(
            teams_by_seed[4],
            teams_by_seed[5]
        )
    ]

    divisional_teams = (
        [teams_by_seed[1]]
        +
        wc_winners
    )

    divisional_teams = sorted(
        divisional_teams,
        key=lambda x: x["seed"]
    )

    div_winner_1 = simulate_game(
        divisional_teams[0],
        divisional_teams[3]
    )

    div_winner_2 = simulate_game(
        divisional_teams[1],
        divisional_teams[2]
    )

    conf_champ = simulate_game(
        div_winner_1,
        div_winner_2
    )

    return {
        "wc_winners": wc_winners,
        "div_winners": [
            div_winner_1,
            div_winner_2
        ],
        "champ": conf_champ
    }


# =====================================================================
# 5. EXECUTION PIPELINE
# =====================================================================

def execute_playoff_tree():
    engine = NFLRatingEngine()

    raw_df = (
        engine.fetch_api_team_stats()
    )

    df = (
        engine.compute_composite_rating(
            raw_df
        )
    )

    df.to_csv(
        f"nfl_{SEASON}_api_model_input.csv",
        index=False
    )

    print("\n===========================================================")
    print("       NFL LIVE-API PLAYOFF SIMULATION")
    print("===========================================================\n")

    print(
        "MODEL INPUTS FROM NFLMeta API"
    )

    display_columns = [
        "seed",
        "team",
        "conf",
        "wins",
        "losses",
        "pass_off",
        "pass_def",
        "rush_off",
        "ol_dl_mass_diff",
        "narrative_hype",
        "rating"
    ]

    print(
        df[
            [
                c
                for c in display_columns
                if c in df.columns
            ]
        ]
        .sort_values(
            ["conf", "seed"]
        )
        .to_string(
            index=False
        )
    )

    afc_df = df[
        df["conf"] == "AFC"
    ].copy()

    nfc_df = df[
        df["conf"] == "NFC"
    ].copy()

    afc_results = (
        run_conference_playoffs(
            afc_df
        )
    )

    nfc_results = (
        run_conference_playoffs(
            nfc_df
        )
    )

    super_bowl_champ = simulate_game(
        afc_results["champ"],
        nfc_results["champ"]
    )

    print("\n--- WILD CARD ROUND ---")

    for label, results in [
        ("AFC", afc_results),
        ("NFC", nfc_results)
    ]:

        print(
            f"\n{label}:"
        )

        for winner in results["wc_winners"]:

            print(
                f"  Winner: "
                f"{winner['team']} "
                f"(Seed #{winner['seed']})"
            )

    print("\n--- DIVISIONAL ROUND ---")

    print(
        "AFC:"
    )

    for winner in afc_results["div_winners"]:
        print(
            f"  Winner: "
            f"{winner['team']} "
            f"(Seed #{winner['seed']})"
        )

    print(
        "NFC:"
    )

    for winner in nfc_results["div_winners"]:
        print(
            f"  Winner: "
            f"{winner['team']} "
            f"(Seed #{winner['seed']})"
        )

    print(
        "\n--- CONFERENCE CHAMPIONSHIPS ---"
    )

    print(
        f"AFC Champion: "
        f"{afc_results['champ']['team']} "
        f"(Seed #{afc_results['champ']['seed']})"
    )

    print(
        f"NFC Champion: "
        f"{nfc_results['champ']['team']} "
        f"(Seed #{nfc_results['champ']['seed']})"
    )

    print(
        "\n==========================================================="
    )

    print(
        f"SUPER BOWL CHAMPION: "
        f"{super_bowl_champ['team']}"
    )

    print(
        f"Rating: "
        f"{super_bowl_champ['rating']:.4f}"
    )

    print(
        "===========================================================\n"
    )

    return df, afc_results, nfc_results, super_bowl_champ


# =====================================================================
# 6. RUN
# =====================================================================

if __name__ == "__main__":
    execute_playoff_tree()
