import unittest

from hoop_tape_miner.official import load_glory, map_time

SEGS = [{"official_from": 0, "official_to": 300, "offset_s": 60.0},
        {"official_from": 300, "official_to": 2400, "offset_s": 120.0}]


def stat(n, value=None, made=None, total=None):
    return {"shortName": n, "value": value, "made": made, "total": total}


def player(num, pts, two, three, pf):
    return {"playerNumber": num, "person": {"fullNameWithAnonymisation": "Secret Name"},
            "boxScoreStats": [stat("PTS", str(pts)), stat("2PM-A", made=two, total=two),
                              stat("3PM-A", made=three, total=three),
                              stat("FTM-A", made=0, total=0), stat("PF", str(pf))]}


def team(home, name, players, pts, pf):
    return {"isHomeTeam": home, "team": {"name": name}, "gamePlayers": players,
            "boxScoreTotalStats": [stat("PTS", str(pts)), stat("PF", str(pf))]}


BOX = {"data": {"game": {"participations": [
    team("False", "Away FC", [player("7", 3, 0, 1, 2)], 3, 2),
    team("True", "Home FC", [player("19", 2, 1, 0, 0)], 2, 0)]}}}
CHART = {"data": {"game": {"pointChart": {"entries": [
    {"timeString": "00:00", "homeScore": 0, "awayScore": 0},
    {"timeString": "02:20", "homeScore": 0, "awayScore": 2},
    {"timeString": "06:00", "homeScore": 2, "awayScore": 2},
    {"timeString": "06:10", "homeScore": 2, "awayScore": 3}]}}}}


class OfficialTests(unittest.TestCase):
    def test_map_time_segments(self):
        self.assertEqual(map_time(140, SEGS), 80.0)
        self.assertEqual(map_time(300, SEGS), 180.0)
        self.assertEqual(map_time(2270, SEGS), 2150.0)
        self.assertIsNone(map_time(2380, SEGS, video_len=2000))
        self.assertIsNone(map_time(5000, SEGS))
        self.assertIsNone(map_time(10, [{"official_from": 0, "official_to": 50, "offset_s": 60.0}]))

    def test_load_glory_away_team_is_us_without_names(self):
        d = load_glory(BOX, CHART, us_is_home=False, segments=SEGS)
        self.assertEqual(d["final"]["us"]["pts"], 3)
        self.assertEqual(d["final"]["them"]["pts"], 2)
        self.assertEqual(d["players"]["us"]["7"]["3PM-A"], {"made": 1, "att": 1})
        self.assertEqual(d["players"]["us"]["7"]["PF"], 2)
        self.assertEqual(list(d["players"]["them"]), ["19"])
        self.assertNotIn("Secret", str(d))
        f = d["score_flow"]
        self.assertEqual([(x["team"], x["points"], x["score_us"], x["score_them"]) for x in f],
                         [("us", 2, 2, 0), ("them", 2, 2, 2), ("us", 1, 3, 2)])
        self.assertEqual(f[0]["our_video_t"], 80.0)
        self.assertEqual(f[1]["our_video_t"], 240.0)

    def test_load_glory_sums_players_sharing_a_jersey(self):
        box = {"data": {"game": {"participations": [
            team("True", "Home FC", [player("21", 2, 1, 0, 1), player("21", 3, 0, 1, 2), player("9", 2, 1, 0, 0)], 7, 3),
            team("False", "Away FC", [player("5", 2, 1, 0, 0)], 2, 0)]}}}
        d = load_glory(box, CHART, us_is_home=True)
        p = d["players"]["us"]["21"]
        self.assertEqual((p["PTS"], p["PF"]), (5, 3))
        self.assertEqual((p["2PM-A"], p["3PM-A"]), ({"made": 1, "att": 1}, {"made": 1, "att": 1}))
        self.assertEqual(sum(x["PTS"] for x in d["players"]["us"].values()), 7)
        self.assertEqual(d["shared_jerseys"], {"us": {"21": 2}})


if __name__ == "__main__":
    unittest.main()
