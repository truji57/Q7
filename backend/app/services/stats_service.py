"""
Q7 Backend - Statistics Service
Recolecta cierres de ciclo + serie de equity y computa metricas por cuenta,
grupo y preset (winrate, max DD, profit factor, expectativa, etc).
"""
import hashlib
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.account import (
    Account, EquitySnapshot, TradeClose, ConfigSnapshot,
)


def make_preset_key(account) -> str:
    """Hash de la config de riesgo de la cuenta (TPC/SLC/TPR/SLR/TPG/SLG/CT/MXP)."""
    payload = json.dumps({
        "ct": int(getattr(account, "ct", 1) or 1),
        "max_positions": int(getattr(account, "max_positions", 6) or 6),
        "tpc": round(float(getattr(account, "tpc", 1500.0) or 0), 2),
        "slc": round(float(getattr(account, "slc", 2000.0) or 0), 2),
        "pdpt": round(float(getattr(account, "pdpt", 1600.0) or 0), 2),
        "pdll": round(float(getattr(account, "pdll", 2100.0) or 0), 2),
        "tpd": round(float(getattr(account, "tpd", 0.0) or 0), 2),
        "sld": round(float(getattr(account, "sld", 0.0) or 0), 2),
        "tpg": round(float(getattr(account, "tpg", 0.0) or 0), 2),
        "slg": round(float(getattr(account, "slg", 0.0) or 0), 2),
    }, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _fmt_dt(dt) -> str:
    return dt.isoformat() if dt else ""


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    # ========== RECOLECCION (usado por el orquestador) ==========

    def record_close(self, account: Account, pnl: float, reason: str, ts_open=None):
        """Registra un cierre de ciclo + el snapshot de config que lo produjo."""
        ts_close = datetime.utcnow()
        preset_key = make_preset_key(account)
        self.db.add(TradeClose(
            account_id=account.id, group_id=account.group_id,
            ts_open=ts_open or ts_close, ts_close=ts_close,
            direction=(account.position or "?") if account.position not in ("", "FLAT") else "?",
            instrument=account.symbol or "--",
            pnl=round(float(pnl), 2), reason=reason, preset_key=preset_key,
        ))
        self.db.add(ConfigSnapshot(
            account_id=account.id, group_id=account.group_id,
            ts=ts_close, preset_key=preset_key,
            ct=account.ct or 1, max_positions=account.max_positions or 6,
            tpc=account.tpc or 0, slc=account.slc or 0,
            pdpt=account.pdpt or 0, pdll=account.pdll or 0,
            tpd=account.tpd or 0, sld=account.sld or 0,
            tpg=account.tpg or 0, slg=account.slg or 0,
        ))
        self.db.commit()

    def snapshot(self, account: Account):
        """Inserta un punto de equity (balance + open pnl)."""
        self.db.add(EquitySnapshot(
            account_id=account.id, group_id=account.group_id,
            ts=datetime.utcnow(),
            balance=account.balance or 0.0,
            equity=(account.balance or 0.0) + (account.open_pnl or 0.0),
            daily_pnl=account.daily_pnl or 0.0,
        ))
        self.db.commit()

    # ========== QUERIES ==========

    def _closes(self, account_id: int = None, group_id: int = None, from_dt=None, to_dt=None):
        q = self.db.query(TradeClose)
        if account_id: q = q.filter(TradeClose.account_id == account_id)
        if group_id: q = q.filter(TradeClose.group_id == group_id)
        if from_dt: q = q.filter(TradeClose.ts_close >= from_dt)
        if to_dt: q = q.filter(TradeClose.ts_close <= to_dt)
        return q.order_by(TradeClose.ts_close).all()

    def _snapshots(self, account_id: int = None, group_id: int = None, from_dt=None, to_dt=None):
        q = self.db.query(EquitySnapshot)
        if account_id: q = q.filter(EquitySnapshot.account_id == account_id)
        if group_id: q = q.filter(EquitySnapshot.group_id == group_id)
        if from_dt: q = q.filter(EquitySnapshot.ts >= from_dt)
        if to_dt: q = q.filter(EquitySnapshot.ts <= to_dt)
        return q.order_by(EquitySnapshot.ts).all()

    def _metrics(self, closes: list[TradeClose], snaps: list[EquitySnapshot]) -> dict:
        n = len(closes)
        wins = [c for c in closes if c.pnl > 0]
        losses = [c for c in closes if c.pnl <= 0]
        n_wins, n_losses = len(wins), len(losses)
        gross_win = sum(c.pnl for c in wins)
        gross_loss = sum(c.pnl for c in losses)
        net = sum(c.pnl for c in closes)
        avg_win = gross_win / n_wins if n_wins else 0.0
        avg_loss = gross_loss / n_losses if n_losses else 0.0
        pf = (gross_win / abs(gross_loss)) if gross_loss else (gross_win if n else 0.0)

        # Max DD desde los CIERRES realizados (curva de pnl acumulado): refleja
        # la perdida real de las operaciones (ej. cierre por SLC), no el flotante.
        peak, max_dd, max_dd_date = 0.0, 0.0, None
        cum = 0.0
        for c in sorted(closes, key=lambda c: c.ts_close):
            cum += c.pnl or 0
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > max_dd:
                max_dd = dd
                max_dd_date = c.ts_close

        # Sin cierres aun: usar la curva de equity muestreada como fallback
        if not closes:
            for s in snaps:
                eq = s.equity or s.balance or 0.0
                if peak is None or eq > peak:
                    peak = eq
                dd = peak - eq
                if dd > max_dd:
                    max_dd = dd
                    max_dd_date = s.ts

        snap_peak = max((s.equity or s.balance or 0.0) for s in snaps) if snaps else 0.0
        max_dd_pct = (max_dd / snap_peak * 100.0) if snap_peak else 0.0

        return {
            "n": n,
            "wins": n_wins,
            "losses": n_losses,
            "winrate": round((n_wins / n * 100.0) if n else 0.0, 1),
            "net_pnl": round(net, 2),
            "gross_win": round(gross_win, 2),
            "gross_loss": round(gross_loss, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(pf, 2) if pf else 0.0,
            "expectancy": round((net / n) if n else 0.0, 2),
            "max_dd": round(max_dd, 2),
            "max_dd_pct": round(max_dd_pct, 2),
            "max_dd_date": _fmt_dt(max_dd_date),
        }

    def account_summary(self, account_id: int, from_dt=None, to_dt=None) -> dict:
        closes = self._closes(account_id=account_id, from_dt=from_dt, to_dt=to_dt)
        snaps = self._snapshots(account_id=account_id, from_dt=from_dt, to_dt=to_dt)
        return self._metrics(closes, snaps)

    def account_equity(self, account_id: int, from_dt=None, to_dt=None, bucket: int = 0) -> list:
        """Serie equity; si bucket>0 segundos, se toman los ultimos puntos por bucket."""
        q = self.db.query(EquitySnapshot)
        q = q.filter(EquitySnapshot.account_id == account_id)
        if from_dt: q = q.filter(EquitySnapshot.ts >= from_dt)
        if to_dt: q = q.filter(EquitySnapshot.ts <= to_dt)
        q = q.order_by(EquitySnapshot.ts).all()

        if bucket and bucket > 0:
            last = {}
            for s in q:
                last[int(s.ts.timestamp() // bucket)] = s
            q = [last[k] for k in sorted(last)]

        peak, out = None, []
        for s in q:
            eq = s.equity or s.balance or 0.0
            if peak is None or eq > peak:
                peak = eq
            dd = (peak - eq) if peak else 0.0
            out.append({
                "ts": _fmt_dt(s.ts),
                "balance": round(s.balance or 0.0, 2),
                "equity": round(eq, 2),
                "drawdown": round(dd, 2),
            })
        return out

    def account_breakdowns(self, account_id: int, from_dt=None, to_dt=None) -> dict:
        closes = self._closes(account_id=account_id, from_dt=from_dt, to_dt=to_dt)
        return self._breakdowns(closes)

    def account_trades(self, account_id: int, from_dt=None, to_dt=None, limit: int = 200) -> list:
        q = self.db.query(TradeClose).filter(TradeClose.account_id == account_id)
        if from_dt: q = q.filter(TradeClose.ts_close >= from_dt)
        if to_dt: q = q.filter(TradeClose.ts_close <= to_dt)
        q = q.order_by(TradeClose.ts_close.desc()).limit(limit).all()
        return [{
            "id": t.id,
            "ts_open": _fmt_dt(t.ts_open),
            "ts_close": _fmt_dt(t.ts_close),
            "direction": t.direction,
            "instrument": t.instrument,
            "pnl": round(t.pnl, 2),
            "reason": t.reason,
            "preset_key": t.preset_key,
        } for t in q]

    def _breakdowns(self, closes: list[TradeClose]) -> dict:
        def group_by(key_fn):
            groups = {}
            for c in closes:
                k = key_fn(c)
                g = groups.setdefault(k, {"n": 0, "pnl": 0.0, "wins": 0})
                g["n"] += 1
                g["pnl"] += c.pnl or 0
                if c.pnl > 0: g["wins"] += 1
            return [
                {"key": k, "n": v["n"], "wins": v["wins"],
                 "winrate": round(v["wins"] / v["n"] * 100.0, 1) if v["n"] else 0.0,
                 "net_pnl": round(v["pnl"], 2)}
                for k, v in sorted(groups.items(), key=lambda kv: -abs(kv[1]["pnl"]))
            ]

        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return {
            "direction": group_by(lambda c: c.direction or "?"),
            "instrument": group_by(lambda c: c.instrument or "--"),
            "reason": group_by(lambda c: c.reason or ""),
            "weekday": group_by(lambda c: weekdays[c.ts_close.weekday()] if c.ts_close else "?"),
            "month": group_by(lambda c: c.ts_close.strftime("%Y-%m") if c.ts_close else "?"),
        }

    def preset_summary(self, from_dt=None, to_dt=None) -> list:
        """Comparativa de presets agrupando cierres por preset_key."""
        closes = self._closes(from_dt=from_dt, to_dt=to_dt)
        snaps = self.db.query(ConfigSnapshot)
        if from_dt: snaps = snaps.filter(ConfigSnapshot.ts >= from_dt)
        if to_dt: snaps = snaps.filter(ConfigSnapshot.ts <= to_dt)
        snap_by_key = {}
        for s in snaps.all():
            snap_by_key.setdefault(s.preset_key, s)

        groups = {}
        for c in closes:
            key = c.preset_key or "?"
            g = groups.setdefault(key, {"n": 0, "wins": 0, "pnl": 0.0})
            g["n"] += 1
            g["pnl"] += c.pnl or 0
            if c.pnl > 0: g["wins"] += 1

        out = []
        for key, g in groups.items():
            snap = snap_by_key.get(key)
            gross_win = sum(c.pnl for c in closes if (c.preset_key or "?") == key and c.pnl > 0)
            gross_loss = sum(c.pnl for c in closes if (c.preset_key or "?") == key and c.pnl <= 0)
            out.append({
                "preset_key": key,
                "n": g["n"],
                "wins": g["wins"],
                "winrate": round(g["wins"] / g["n"] * 100.0, 1) if g["n"] else 0.0,
                "net_pnl": round(g["pnl"], 2),
                "avg": round(g["pnl"] / g["n"], 2) if g["n"] else 0.0,
                "profit_factor": round(gross_win / abs(gross_loss), 2) if gross_loss else (gross_win if g["n"] else 0.0),
                "ct": snap.ct if snap else None,
                "max_positions": snap.max_positions if snap else None,
                "tpc": snap.tpc if snap else None,
                "slc": snap.slc if snap else None,
                "pdpt": snap.pdpt if snap else None,
                "pdll": snap.pdll if snap else None,
                "tpd": snap.tpd if snap else None,
                "sld": snap.sld if snap else None,
                "tpg": snap.tpg if snap else None,
                "slg": snap.slg if snap else None,
            })
        out.sort(key=lambda r: -abs(r["net_pnl"]))
        return out
