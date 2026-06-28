#!/usr/bin/env python3
"""
Daily no-key update for finished World Cup 2026 matches.

Rules:
- No proxy values.
- No API keys.
- Only direct fields returned by no-key public endpoints or existing repository data.
- If a field is unavailable, keep NA.
- ESPN public endpoint is used only as a no-key source for finalized scores and direct match stats when returned.

Main outputs:
- data/daily_updates/finished_matches_espn.csv
- data/daily_updates/finished_match_team_stats_espn.csv
- data/daily_updates/finished_match_events_espn.csv
- data/daily_updates/sources_used_daily.csv
- data/daily_updates/last_run_report.md
- data/resultados_reais.csv
- data/resultados.csv
- data/database/matches.csv status updates
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

NA = "NA"
ESPN_LEAGUE = "fifa.world"
ESPN_SCOREBOARD = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{ESPN_LEAGUE}/scoreboard"
ESPN_SUMMARY = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{ESPN_LEAGUE}/summary"

HEADERS = {
    "User-Agent": "tabela-copa-2026-daily-no-key/1.0 (polite no-key data update)",
    "Accept": "application/json,text/plain,*/*",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def repo_root_from(start: Optional[Path] = None) -> Path:
    p = Path(start or Path.cwd()).resolve()
    for cand in [p] + list(p.parents):
        if (cand / ".git").exists() or (cand / "data" / "database" / "matches.csv").exists():
            return cand
    return p


@dataclass
class SourceRow:
    source_id: str
    category: str
    entity_type: str
    entity_name: str
    url: str
    publisher: str
    title: str
    date_published: str
    date_accessed: str
    data_collected: str
    reliability_0_100: int
    notes: str


class DailyUpdater:
    def __init__(self, root: Path, delay_seconds: float = 3.0, offline: bool = False):
        self.root = root
        self.delay_seconds = delay_seconds
        self.offline = offline
        self.data_dir = root / "data"
        self.db_dir = root / "data" / "database"
        self.out_dir = root / "data" / "daily_updates"
        self.cache_dir = root / ".copa_2026_request_cache"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sources: List[SourceRow] = []
        self.request_log: List[Dict[str, Any]] = []
        self.source_counter = 0

    def source(self, category: str, entity_type: str, entity_name: str, url: str, publisher: str,
               title: str, data_collected: str, reliability_0_100: int = 80, notes: str = "") -> str:
        self.source_counter += 1
        sid = f"DLY{self.source_counter:05d}"
        self.sources.append(SourceRow(
            source_id=sid,
            category=category,
            entity_type=entity_type,
            entity_name=entity_name,
            url=url,
            publisher=publisher,
            title=title,
            date_published=NA,
            date_accessed=now_iso(),
            data_collected=data_collected,
            reliability_0_100=reliability_0_100,
            notes=notes,
        ))
        return sid

    def cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")

    def get_json(self, url: str) -> Optional[Dict[str, Any]]:
        cp = self.cache_path(url)
        if cp.exists():
            self.request_log.append({"url": url, "status": "cache_hit", "timestamp": now_iso()})
            try:
                return json.loads(cp.read_text(encoding="utf-8"))
            except Exception as e:
                self.request_log.append({"url": url, "status": "cache_read_error", "error": repr(e), "timestamp": now_iso()})

        if self.offline:
            self.request_log.append({"url": url, "status": "offline_skip", "timestamp": now_iso()})
            return None

        time.sleep(max(0.0, self.delay_seconds))
        try:
            r = requests.get(url, headers=HEADERS, timeout=35)
            self.request_log.append({"url": url, "status_code": r.status_code, "timestamp": now_iso()})
            r.raise_for_status()
            data = r.json()
            cp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        except Exception as e:
            self.request_log.append({"url": url, "status": "error", "error": repr(e), "timestamp": now_iso()})
            return None

    def read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[], encoding="latin1")

    def write_csv(self, df: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df = df.copy().replace({pd.NA: NA, None: NA, "nan": NA, "NaN": NA}).fillna(NA)
        df.to_csv(path, index=False, encoding="utf-8", na_rep=NA)

    def load_aliases(self) -> Dict[str, str]:
        aliases: Dict[str, str] = {}
        matches_path = self.db_dir / "matches.csv"
        matches = self.read_csv(matches_path)
        if not matches.empty:
            for c in ["equipe1", "equipe2"]:
                if c in matches.columns:
                    for team in matches[c].dropna().astype(str).unique():
                        aliases[normalize_text(team)] = team

        alias_path = self.root / "data" / "mappings" / "team_name_aliases.csv"
        if alias_path.exists():
            alias_df = self.read_csv(alias_path)
            for _, r in alias_df.iterrows():
                repo_team = str(r.get("repo_team", "")).strip()
                alias = str(r.get("alias", "")).strip()
                if repo_team:
                    aliases[normalize_text(repo_team)] = repo_team
                if repo_team and alias:
                    aliases[normalize_text(alias)] = repo_team
        return aliases

    def canon_team(self, name: Any, aliases: Dict[str, str]) -> str:
        return aliases.get(normalize_text(name), str(name).strip() if name is not None else NA)

    def dates_to_check(self, days_back: int, days_forward: int, all_past: bool, start_date: Optional[str], end_date: Optional[str]) -> List[dt.date]:
        today = dt.datetime.now().date()
        if start_date or end_date:
            start = dt.date.fromisoformat(start_date) if start_date else today - dt.timedelta(days=days_back)
            end = dt.date.fromisoformat(end_date) if end_date else today + dt.timedelta(days=days_forward)
        elif all_past:
            matches = self.read_csv(self.db_dir / "matches.csv")
            if not matches.empty and "data" in matches.columns:
                parsed = pd.to_datetime(matches["data"], errors="coerce").dropna()
                if parsed.empty:
                    start = today - dt.timedelta(days=days_back)
                else:
                    start = parsed.min().date()
                end = min(today + dt.timedelta(days=days_forward), parsed.max().date()) if not parsed.empty else today
            else:
                start = today - dt.timedelta(days=days_back)
                end = today + dt.timedelta(days=days_forward)
        else:
            start = today - dt.timedelta(days=days_back)
            end = today + dt.timedelta(days=days_forward)
        if end < start:
            return []
        return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]

    def fetch_espn_date(self, date: dt.date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        ymd = date.strftime("%Y%m%d")
        url = f"{ESPN_SCOREBOARD}?dates={ymd}&limit=200"
        data = self.get_json(url)
        if not data:
            return [], [], []
        self.source("match_result", "date_scoreboard", ymd, url, "ESPN public site API", "ESPN FIFA World Cup scoreboard", "final scores and status", 80, "No API key. Public ESPN JSON endpoint.")

        aliases = self.load_aliases()
        match_rows: List[Dict[str, Any]] = []
        stat_rows: List[Dict[str, Any]] = []
        event_rows: List[Dict[str, Any]] = []

        for ev in data.get("events", []):
            status = ev.get("status", {}).get("type", {})
            completed = bool(status.get("completed")) or str(status.get("name", "")).upper() in {"STATUS_FINAL", "STATUS_FULL_TIME"}
            if not completed:
                continue
            comps = (ev.get("competitions") or [{}])[0]
            competitors = comps.get("competitors", [])
            if len(competitors) < 2:
                continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            home_name_raw = home.get("team", {}).get("displayName") or home.get("team", {}).get("name") or NA
            away_name_raw = away.get("team", {}).get("displayName") or away.get("team", {}).get("name") or NA
            team_home = self.canon_team(home_name_raw, aliases)
            team_away = self.canon_team(away_name_raw, aliases)
            score_home = home.get("score", NA)
            score_away = away.get("score", NA)
            event_id = ev.get("id", NA)
            event_url = ev.get("links", [{}])[0].get("href", f"{ESPN_SCOREBOARD}?dates={ymd}") if ev.get("links") else f"{ESPN_SCOREBOARD}?dates={ymd}"
            winner = NA
            try:
                sh, sa = int(score_home), int(score_away)
                winner = team_home if sh > sa else team_away if sa > sh else "Empate"
            except Exception:
                pass

            match_rows.append({
                "espn_event_id": event_id,
                "date": date.isoformat(),
                "status": "Finalizado",
                "team_home": team_home,
                "team_away": team_away,
                "team_home_source_name": home_name_raw,
                "team_away_source_name": away_name_raw,
                "score_home": score_home,
                "score_away": score_away,
                "winner": winner,
                "source_url": event_url,
                "source_publisher": "ESPN public site API",
                "date_accessed": now_iso(),
                "data_leakage_risk": "post_match_only",
                "notes": "Final score/status directly from ESPN public JSON. No proxy.",
            })

            # Summary endpoint may include direct stats/events; keep only if returned.
            if event_id != NA:
                summary_url = f"{ESPN_SUMMARY}?event={event_id}"
                summary = self.get_json(summary_url)
                if summary:
                    self.source("match_stats", "match_summary", str(event_id), summary_url, "ESPN public site API", "ESPN match summary", "team statistics/events when returned", 80, "No API key. Direct fields only.")
                    # Team statistics in boxscore.
                    for team_obj in summary.get("boxscore", {}).get("teams", []):
                        team_name = self.canon_team(team_obj.get("team", {}).get("displayName") or team_obj.get("team", {}).get("name") or NA, aliases)
                        stats = team_obj.get("statistics", []) or []
                        for st in stats:
                            stat_rows.append({
                                "espn_event_id": event_id,
                                "date": date.isoformat(),
                                "team": team_name,
                                "stat_name": st.get("name", NA),
                                "stat_display_name": st.get("displayName", NA),
                                "stat_value": st.get("displayValue", st.get("value", NA)),
                                "source_url": summary_url,
                                "source_publisher": "ESPN public site API",
                                "date_accessed": now_iso(),
                                "data_leakage_risk": "post_match_only",
                                "notes": "Direct ESPN post-match statistic. No proxy.",
                            })
                    # Scoring/events when returned.
                    for comp in summary.get("scoringPlays", []) or []:
                        event_rows.append({
                            "espn_event_id": event_id,
                            "date": date.isoformat(),
                            "event_type": comp.get("type", {}).get("text", NA) if isinstance(comp.get("type"), dict) else comp.get("type", NA),
                            "team": self.canon_team(comp.get("team", {}).get("displayName", NA) if isinstance(comp.get("team"), dict) else NA, aliases),
                            "athlete": comp.get("athletes", [{}])[0].get("displayName", NA) if comp.get("athletes") else NA,
                            "clock": comp.get("clock", {}).get("displayValue", NA) if isinstance(comp.get("clock"), dict) else comp.get("clock", NA),
                            "text": comp.get("text", NA),
                            "source_url": summary_url,
                            "source_publisher": "ESPN public site API",
                            "date_accessed": now_iso(),
                            "data_leakage_risk": "post_match_only",
                            "notes": "Direct ESPN scoring play/event when available. No proxy.",
                        })
        return match_rows, stat_rows, event_rows

    def read_existing_finished(self) -> pd.DataFrame:
        # Keeps existing repository data as a direct source from prior curated update.
        paths = [self.data_dir / "resultados_reais.csv", self.data_dir / "resultados.csv"]
        for p in paths:
            df = self.read_csv(p)
            if not df.empty:
                return df
        return pd.DataFrame()


    def existing_results_to_finished_rows(self) -> List[Dict[str, Any]]:
        """Seeds daily_updates from existing resultados_reais.csv without creating proxy values."""
        df = self.read_existing_finished()
        if df.empty:
            return []
        rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            status = str(r.get("status_real", "")).strip().lower()
            if status and "final" not in status:
                continue
            team1 = r.get("equipe1", NA)
            team2 = r.get("equipe2", NA)
            g1 = r.get("gols1_real", NA)
            g2 = r.get("gols2_real", NA)
            src = r.get("fonte", NA)
            rows.append({
                "espn_event_id": f"repo_existing_{r.get('jogo', NA)}",
                "date": str(r.get("data", NA))[:10],
                "status": "Finalizado",
                "team_home": team1,
                "team_away": team2,
                "team_home_source_name": team1,
                "team_away_source_name": team2,
                "score_home": g1,
                "score_away": g2,
                "winner": r.get("vencedor_real", NA),
                "source_url": src,
                "source_publisher": "existing_repository_resultados_reais",
                "date_accessed": now_iso(),
                "data_leakage_risk": "post_match_only",
                "notes": "Existing finalized result already present in repository; direct source URL preserved. No proxy.",
            })
            if src and src != NA:
                self.source("match_result", "existing_repository_result", str(r.get("jogo", NA)), src, "existing repository source", "resultados_reais.csv source", "final score from existing curated repository data", 70, "Seeded from repository; no proxy.")
        return rows

    def merge_finished_matches(self, new_rows: List[Dict[str, Any]]) -> pd.DataFrame:
        cols = ["espn_event_id", "date", "status", "team_home", "team_away", "team_home_source_name", "team_away_source_name", "score_home", "score_away", "winner", "source_url", "source_publisher", "date_accessed", "data_leakage_risk", "notes"]
        new_df = pd.DataFrame(new_rows, columns=cols)
        out_path = self.out_dir / "finished_matches_espn.csv"
        old = self.read_csv(out_path)
        if old.empty:
            merged = new_df
        elif new_df.empty:
            merged = old
        else:
            merged = pd.concat([old, new_df], ignore_index=True)
            keys = ["espn_event_id", "date", "team_home", "team_away"]
            merged = merged.drop_duplicates(subset=keys, keep="last")
        self.write_csv(merged, out_path)
        return merged

    def merge_simple(self, rows: List[Dict[str, Any]], filename: str, key_cols: List[str]) -> pd.DataFrame:
        expected_cols = {
            "finished_match_team_stats_espn.csv": ["espn_event_id", "date", "team", "stat_name", "stat_display_name", "stat_value", "source_url", "source_publisher", "date_accessed", "data_leakage_risk", "notes"],
            "finished_match_events_espn.csv": ["espn_event_id", "date", "event_type", "team", "athlete", "clock", "text", "source_url", "source_publisher", "date_accessed", "data_leakage_risk", "notes"],
            "sources_used_daily.csv": ["source_id", "category", "entity_type", "entity_name", "url", "publisher", "title", "date_published", "date_accessed", "data_collected", "reliability_0_100", "notes"],
        }
        new = pd.DataFrame(rows)
        if new.empty and filename in expected_cols:
            new = pd.DataFrame(columns=expected_cols[filename])
        path = self.out_dir / filename
        old = self.read_csv(path)
        if old.empty:
            merged = new
        elif new.empty:
            merged = old
        else:
            merged = pd.concat([old, new], ignore_index=True)
            keep_cols = [c for c in key_cols if c in merged.columns]
            if keep_cols:
                merged = merged.drop_duplicates(subset=keep_cols, keep="last")
            else:
                merged = merged.drop_duplicates(keep="last")
        self.write_csv(merged, path)
        return merged

    def match_to_schedule(self, row: pd.Series, matches: pd.DataFrame) -> Optional[int]:
        if matches.empty:
            return None
        date = str(row.get("date", ""))[:10]
        th = normalize_text(row.get("team_home", ""))
        ta = normalize_text(row.get("team_away", ""))
        candidates = matches[matches.get("data", "").astype(str).str[:10] == date].copy()
        if candidates.empty:
            candidates = matches.copy()
        for idx, m in candidates.iterrows():
            e1 = normalize_text(m.get("equipe1", ""))
            e2 = normalize_text(m.get("equipe2", ""))
            if {e1, e2} == {th, ta}:
                return idx
        return None

    def update_resultados_and_matches(self, finished: pd.DataFrame) -> int:
        if finished.empty:
            return 0
        matches_path = self.db_dir / "matches.csv"
        matches = self.read_csv(matches_path)
        if matches.empty:
            return 0
        resultados_path = self.data_dir / "resultados_reais.csv"
        resultados = self.read_csv(resultados_path)
        res_cols = ["jogo", "data", "fase", "equipe1", "equipe2", "gols1_real", "gols2_real", "placar_real", "vencedor_real", "status_real", "fonte", "placar_original"]
        if resultados.empty:
            resultados = pd.DataFrame(columns=res_cols)
        for c in res_cols:
            if c not in resultados.columns:
                resultados[c] = NA

        added_or_updated = 0
        for _, f in finished.iterrows():
            midx = self.match_to_schedule(f, matches)
            if midx is None:
                continue
            m = matches.loc[midx]
            team1, team2 = str(m.get("equipe1", NA)), str(m.get("equipe2", NA))
            th, ta = str(f.get("team_home", NA)), str(f.get("team_away", NA))
            score_h, score_a = f.get("score_home", NA), f.get("score_away", NA)
            # Convert home/away score to equipe1/equipe2 score.
            if normalize_text(team1) == normalize_text(th):
                g1, g2 = score_h, score_a
            elif normalize_text(team1) == normalize_text(ta):
                g1, g2 = score_a, score_h
            else:
                g1, g2 = score_h, score_a
            try:
                i1, i2 = int(g1), int(g2)
                vencedor = team1 if i1 > i2 else team2 if i2 > i1 else "Empate"
            except Exception:
                vencedor = NA
            jogo = str(m.get("jogo", NA))
            new_res = {
                "jogo": jogo,
                "data": str(m.get("data", f.get("date", NA)))[:10],
                "fase": m.get("fase", NA),
                "equipe1": team1,
                "equipe2": team2,
                "gols1_real": g1,
                "gols2_real": g2,
                "placar_real": f"{g1}-{g2}" if g1 != NA and g2 != NA else NA,
                "vencedor_real": vencedor,
                "status_real": "Finalizado",
                "fonte": f.get("source_url", NA),
                "placar_original": f"{th} {score_h} x {score_a} {ta}",
            }
            mask = resultados["jogo"].astype(str) == jogo
            if mask.any():
                # Update only if source provides non-NA direct value.
                for k, v in new_res.items():
                    if v != NA:
                        resultados.loc[mask, k] = v
            else:
                resultados = pd.concat([resultados, pd.DataFrame([new_res])], ignore_index=True)
            if "status" in matches.columns:
                matches.loc[midx, "status"] = "Finalizado"
            added_or_updated += 1

        self.write_csv(resultados[res_cols], resultados_path)
        self.write_csv(resultados[res_cols], self.data_dir / "resultados.csv")
        self.write_csv(matches, matches_path)
        return added_or_updated

    def run(self, days_back: int, days_forward: int, all_past: bool, start_date: Optional[str], end_date: Optional[str]) -> int:
        dates = self.dates_to_check(days_back, days_forward, all_past, start_date, end_date)
        all_match_rows: List[Dict[str, Any]] = []
        all_stat_rows: List[Dict[str, Any]] = []
        all_event_rows: List[Dict[str, Any]] = []
        for d in dates:
            m, s, e = self.fetch_espn_date(d)
            all_match_rows.extend(m)
            all_stat_rows.extend(s)
            all_event_rows.extend(e)

        # Seed with existing repository results as direct known finalized data, then add any newly collected ESPN rows.
        seed_rows = self.existing_results_to_finished_rows()
        finished = self.merge_finished_matches(seed_rows + all_match_rows)
        stats = self.merge_simple(all_stat_rows, "finished_match_team_stats_espn.csv", ["espn_event_id", "team", "stat_name"])
        events = self.merge_simple(all_event_rows, "finished_match_events_espn.csv", ["espn_event_id", "team", "athlete", "clock", "text"])
        updated = self.update_resultados_and_matches(finished)

        sources_df = pd.DataFrame([s.__dict__ for s in self.sources])
        if sources_df.empty:
            sources_df = pd.DataFrame([{
                "source_id": "NA", "category": "match_result", "entity_type": "run", "entity_name": "daily_update",
                "url": "NA", "publisher": "NA", "title": "NA", "date_published": "NA", "date_accessed": now_iso(),
                "data_collected": "No new source data collected", "reliability_0_100": 0,
                "notes": "No ESPN data returned or offline/cache only run. No proxy used."
            }])
        self.merge_simple(sources_df.to_dict("records"), "sources_used_daily.csv", ["category", "entity_type", "entity_name", "url"])
        self.write_csv(pd.DataFrame(self.request_log), self.out_dir / "request_log_daily.csv")

        report = [
            "# Relatório diário de atualização sem API key",
            "",
            f"Executado em: {now_iso()}",
            f"Datas verificadas: {', '.join([d.isoformat() for d in dates]) if dates else 'NA'}",
            f"Offline: {self.offline}",
            "",
            "## Regra",
            "Sem proxy, sem estimativa e sem API key. Apenas dados diretos de endpoint público sem chave ou dados existentes do repositório.",
            "",
            "## Resultados",
            f"- Jogos finalizados mantidos em finished_matches_espn.csv: {len(finished)}",
            f"- Linhas de estatísticas diretas ESPN: {len(stats)}",
            f"- Linhas de eventos diretos ESPN: {len(events)}",
            f"- Jogos atualizados em resultados_reais.csv/matches.csv: {updated}",
            "",
            "## Limitações",
            "ESPN é endpoint público não oficial/sem key. Se indisponível, o script não força scraping e não inventa dados.",
            "Campos não retornados pela fonte ficam NA.",
        ]
        (self.out_dir / "last_run_report.md").write_text("\n".join(report), encoding="utf-8")
        print("\n".join(report))
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=None, help="Raiz do repositório. Default: auto-detect.")
    parser.add_argument("--days-back", type=int, default=3)
    parser.add_argument("--days-forward", type=int, default=0)
    parser.add_argument("--all-past", action="store_true")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--delay-seconds", type=float, default=float(os.environ.get("REQUEST_DELAY_SECONDS", "3")))
    parser.add_argument("--offline", action="store_true", help="Não faz requisições; usa apenas cache/dados existentes.")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from()
    updater = DailyUpdater(root=root, delay_seconds=args.delay_seconds, offline=args.offline)
    return updater.run(days_back=args.days_back, days_forward=args.days_forward, all_past=args.all_past, start_date=args.start_date, end_date=args.end_date)


if __name__ == "__main__":
    raise SystemExit(main())
