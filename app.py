"""BEAST MULTI-MARKET V6.2.1 — experimental setups only, NO order execution.
Dependencies: MetaTrader5, streamlit, streamlit-autorefresh, pandas, plotly.
Runs locally: py -m streamlit run app.py
"""

from pathlib import Path
import html
import math
import re
import time

import MetaTrader5 as mt5
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh


st.set_page_config(
    page_title="BEAST Multi-Market | Private Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st_autorefresh(interval=5000, key="beast_multi_market_5s")

# NOTE: Broker symbol names may have prefixes/suffixes. Resolved automatically where possible.
WANTED = ["XAUUSD", "BTCUSD", "GBPUSD", "USDJPY"]
# V6.1 file is read only. New setup tracker uses its own CSV.
LOG_FILE = Path(__file__).resolve().parent / "beast_signals_multi_v62.csv"
ARCHIVE_FILE = Path(__file__).resolve().parent / "beast_signals_multi_v6.csv"
REFERENCE_LOTS = 0.01    # Only for indicative TP calculation; does not place an order.
TARGET_EUR = 5.0         # Indicative GROSS profit target, excluding commissions/slippage.
MAX_EVAL_BARS = 45       # Evaluate hypothetical TP/SL within next 45 completed M1 candles.
MIN_RR = 1.0            # Hypothetical reward/risk threshold; not a performance guarantee.
MIN_CONFLUENCES = 2
COOLDOWN_BARS = 5
COLUMNS = [
    "symbol", "epoch", "signal", "setup", "entry", "tp", "sl", "rr",
    "gross_target_eur", "spread_snapshot", "reason", "status", "result",
    "resolved_epoch", "note",
]

THEME = """
<style>
:root{color-scheme:dark}
[data-testid="stAppViewContainer"],.stApp{background:#07101d!important;color:#d9e9f4!important}
[data-testid="stHeader"]{background:transparent!important}
.block-container{max-width:1660px!important;padding-top:1.3rem!important}
h1,h2,h3,[data-testid="stMetricValue"]{font-family:'Trebuchet MS',sans-serif!important;color:#e3f9ff!important}
[data-testid="stMetric"]{border:1px solid #26435b!important;border-radius:13px!important;padding:12px 16px!important;background:linear-gradient(145deg,#10243b,#0c182b)!important}
[data-testid="stMetricLabel"]{color:#95b7cb!important}
[data-testid="stMetricValue"]{color:#dffef7!important;font-size:clamp(13px,1.15vw,17px)!important;line-height:1.45!important;letter-spacing:-.025em!important;min-width:0!important}
[data-testid="stMetric"]{padding:9px 8px!important;min-width:0!important}
[data-testid="stMetricValue"]>div{font-size:inherit!important;min-width:0!important;white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important}
[data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid #24445b;border-radius:12px;overflow:hidden}
[data-testid="stAlert"]{background:#122739!important;border-radius:9px!important}
hr{border-color:#29445a!important}
.beast-brand{display:flex;gap:14px;justify-content:space-between;align-items:center;border-bottom:1px solid #20435e;padding:11px 4px 19px}
.beast-brand strong{font-size:clamp(16px,2.5vw,29px);color:#4ae6ca;letter-spacing:.17em}
.beast-brand small{display:block;margin-top:5px;letter-spacing:.12em;color:#95bbcf;font-size:10px}
.beast-live{border:1px solid #2e997d;border-radius:20px;color:#70e5b8;padding:8px 11px;font-size:11px;white-space:nowrap}
/* Purely decorative orbital animation. The trading logic is Python, not this image. */
.neural-stage{position:relative;height:264px;margin:17px 0;border:1px solid #245579;border-radius:18px;overflow:hidden;display:flex;align-items:center;justify-content:center;
background:radial-gradient(ellipse at center,#123952 0%,#0a1c33 50%,#06111f 100%);box-shadow:inset 0 0 50px #1d80971a}
.neural-stage::before{content:"";position:absolute;inset:0;background-image:linear-gradient(#66e1d914 1px,transparent 1px),linear-gradient(90deg,#66e1d914 1px,transparent 1px);background-size:30px 30px;opacity:.48}
.neural-stage::after{content:"";position:absolute;left:0;right:0;top:-40%;height:40%;background:linear-gradient(transparent,#4bdce71a,transparent);animation:beastscan 6.5s linear infinite;pointer-events:none}
.neural-title{position:absolute;top:18px;left:20px;color:#b3d7e5;font-size:11px;letter-spacing:.2em;z-index:3}
.neural-foot{position:absolute;bottom:17px;left:20px;color:#83b3c6;font-size:10px;letter-spacing:.08em;z-index:3}
.neural-status{position:absolute;bottom:17px;right:20px;color:#6af4d5;font-size:10px;letter-spacing:.11em;z-index:3;animation:beastblink 2.1s ease-in-out infinite}
.neural-orbit{position:absolute;width:170px;height:170px;border:2px solid #39e9d86e;border-radius:50%;animation:beastspin 11s linear infinite;box-shadow:0 0 18px #34dfcc21}
.neural-orbit:nth-of-type(2){width:210px;height:210px;border-color:#ae7dff6a;border-style:dashed;animation-duration:16s;animation-direction:reverse}
.neural-orbit:nth-of-type(3){width:118px;height:118px;border-color:#42bafc91;transform:rotateX(62deg);animation-duration:7s}
.neural-orbit:nth-of-type(4){width:140px;height:140px;border-color:#a18afa7f;transform:rotateY(65deg);animation-duration:9s;animation-direction:reverse}
.neural-dot{position:absolute;top:-5px;left:calc(50% - 5px);height:10px;width:10px;border-radius:100%;background:#70ffeb;box-shadow:0 0 13px #70ffeb}
.neural-core{width:23px;height:23px;border-radius:50%;background:#52fee3;box-shadow:0 0 20px 8px #3cebd77d,0 0 58px 15px #27daba52;z-index:2;animation:beastpulse 2.2s ease-in-out infinite}
.beast-caption{font-size:11px;color:#90aabd;letter-spacing:.03em}
@keyframes beastspin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
@keyframes beastpulse{0%,100%{transform:scale(.85);opacity:.88}50%{transform:scale(1.16);opacity:1}}
@keyframes beastscan{from{top:-40%}to{top:120%}}
@keyframes beastblink{0%,100%{opacity:1}50%{opacity:.4}}
@media(prefers-reduced-motion:reduce){.neural-stage::after,.neural-orbit,.neural-core,.neural-status{animation:none!important}}
</style>
"""
st.markdown(THEME, unsafe_allow_html=True)
st.markdown(
    '<div class="beast-brand"><div><strong>⚡ BEAST MULTI-MARKET AI</strong>'
    '<small>PRIVATE TERMINAL / FOUR MARKET MONITOR</small></div>'
    '<div class="beast-live">● MT5 SIGNAL FEED</div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="neural-stage">'
    '<div class="neural-title">NEURAL VISUALIZER / MARKET PATTERN DISPLAY</div>'
    '<div class="neural-orbit"><span class="neural-dot"></span></div>'
    '<div class="neural-orbit"><span class="neural-dot"></span></div>'
    '<div class="neural-orbit"><span class="neural-dot"></span></div>'
    '<div class="neural-orbit"><span class="neural-dot"></span></div>'
    '<div class="neural-core"></div>'
    '<div class="neural-foot">GOLD / BITCOIN / GBPUSD / USDJPY</div>'
    '<div class="neural-status">● PATTERN MONITORING</div></div>',
    unsafe_allow_html=True,
)
st.caption("Vizualizimi qendror eshte animacion grafik. Sinjalet vijne nga rregulla eksperimentale Python, jo nga nje model AI i trajnuar.")


def find_symbol(requested, listed):
    """Find Vantage symbol safely; always show the actual resolved trading symbol."""
    if requested in listed:
        return requested
    exact_casefold = [s for s in listed if s.upper() == requested.upper()]
    if exact_casefold:
        return exact_casefold[0]
    candidates = [s for s in listed if s.upper().startswith(requested.upper())]
    if candidates:
        candidates.sort(key=lambda s: (len(s) - len(requested), s))
        return candidates[0]
    return None


def indicators(raw):
    df = pd.DataFrame(raw).copy()
    df["epoch"] = df["time"].astype("int64")
    df["chart_time"] = pd.to_datetime(df["time"], unit="s")
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, float("nan"))
    df["RSI"] = 100 - 100 / (1 + rs)
    df.loc[(al == 0) & (ag > 0), "RSI"] = 100
    df.loc[(al == 0) & (ag == 0), "RSI"] = 50
    pc = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    return df


def candle_patterns(closed):
    last, prev = closed.iloc[-1], closed.iloc[-2]
    size = max(float(last["high"] - last["low"]), 1e-12)
    body = abs(float(last["close"] - last["open"]))
    upper = float(last["high"] - max(last["open"], last["close"]))
    lower = float(min(last["open"], last["close"]) - last["low"])
    shooting = body <= .35 * size and upper >= 2 * max(body, size * .04) and upper > 1.5 * lower
    hammer = body <= .35 * size and lower >= 2 * max(body, size * .04) and lower > 1.5 * upper
    bull_engulf = bool(prev["close"] < prev["open"] and last["close"] > last["open"] and last["open"] <= prev["close"] and last["close"] >= prev["open"])
    bear_engulf = bool(prev["close"] > prev["open"] and last["close"] < last["open"] and last["open"] >= prev["close"] and last["close"] <= prev["open"])
    return shooting, hammer, bull_engulf, bear_engulf


def nearby_fvg(closed, direction, atr):
    """Experimental 3-candle FVG on closed bars only."""
    current = float(closed.iloc[-1]["close"])
    first = max(2, len(closed) - 25)
    for i in range(len(closed) - 1, first - 1, -1):
        a = closed.iloc[i - 2]
        c = closed.iloc[i]
        later = closed.iloc[i + 1:]
        if direction == "BUY" and c["low"] > a["high"]:
            bottom, top = float(a["high"]), float(c["low"])
            filled = not later.empty and (later["low"] <= bottom).any()
        elif direction == "SELL" and c["high"] < a["low"]:
            bottom, top = float(c["high"]), float(a["low"])
            filled = not later.empty and (later["high"] >= top).any()
        else:
            continue
        distance = max(bottom - current, 0, current - top)
        if not filled and distance <= .8 * atr:
            return True, (bottom, top, c["chart_time"])
    return False, None


def market_features(closed):
    bos_up = bos_down = choch_up = choch_down = False
    for i in range(len(closed) - 3, len(closed)):
        old = closed.iloc[i - 18:i]
        bar = closed.iloc[i]
        up = bool(bar["close"] > old["high"].max())
        down = bool(bar["close"] < old["low"].min())
        bos_up |= up
        bos_down |= down
        prev_bias = closed.iloc[i - 8]
        choch_up |= up and prev_bias["EMA20"] < prev_bias["EMA50"]
        choch_down |= down and prev_bias["EMA20"] > prev_bias["EMA50"]
    return bos_up, bos_down, choch_up, choch_down


def load_log():
    """Do not overwrite incompatible or corrupt data."""
    if not LOG_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    try:
        saved = pd.read_csv(LOG_FILE)
        if set(COLUMNS).issubset(saved.columns):
            return saved[COLUMNS].copy()
        st.error("CSV V6.2 ka strukture tjeter; nuk do te mbishkruhet.")
        st.stop()
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        st.error(f"Gabim ne leximin e V6.2 CSV: {exc}")
        st.stop()


def old_log_for_display():
    """V6.1 archive remains untouched and separately interpretable."""
    if not ARCHIVE_FILE.exists():
        return None
    try:
        old = pd.read_csv(ARCHIVE_FILE)
        return old if set(("symbol", "epoch", "signal", "result")).issubset(old.columns) else None
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None


def euro_conversion_rate(account_currency, available_names):
    """EUR per 1 unit of account currency using available broker spot quotes."""
    cur = str(account_currency).upper().strip()
    if cur == "EUR":
        return 1.0, "EUR"
    # If EURXXX exists, quote is XXX per 1 EUR: divide by ask.
    pair = find_symbol("EUR" + cur, available_names)
    if pair and mt5.symbol_select(pair, True):
        tick = mt5.symbol_info_tick(pair)
        if tick and float(tick.ask) > 0:
            return 1.0 / float(tick.ask), pair
    # If XXXEUR exists, quote is EUR per 1 XXX: multiply by bid.
    pair = find_symbol(cur + "EUR", available_names)
    if pair and mt5.symbol_select(pair, True):
        tick = mt5.symbol_info_tick(pair)
        if tick and float(tick.bid) > 0:
            return float(tick.bid), pair
    return None, f"Konvertimi {cur}/EUR nuk gjendet ne MT5"


def round_to_tick(price, tick_size, digits, direction):
    """Round outward in the profit direction for the TP."""
    step = float(tick_size) if tick_size and tick_size > 0 else 10 ** (-int(digits))
    units = float(price) / step
    units = math.ceil(units - 1e-8) if direction == "BUY" else math.floor(units + 1e-8)
    return round(units * step, int(digits))


def tp_for_eur(symbol, direction, entry, atr, spread, eur_rate):
    """Find TP using broker's order_calc_profit; no trades executed.

    MT5 simulates account-currency GROSS P/L from ask->bid for BUY
    or bid->ask for SELL. It does not include future slippage/commission.
    """
    if eur_rate is None or eur_rate <= 0:
        return None, "Konvertimi i valutes se llogarise ne EUR nuk u gjet"
    info = mt5.symbol_info(symbol)
    if info is None:
        return None, "Specifikat e kontrates MT5 nuk u gjeten"
    tick_size = float(getattr(info, "trade_tick_size", 0) or getattr(info, "point", 0) or 0)
    point = float(getattr(info, "point", 0) or 0)
    digits = int(getattr(info, "digits", 5) or 5)
    # Big enough to avoid near-zero precision in MT5's P/L calculation.
    probe = max(atr * 0.6, spread * 3, point * 100, tick_size * 100)
    if probe <= 0:
        return None, "Nuk ka vlere te vlefshme per ATR/point"
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    close_probe = entry + probe if direction == "BUY" else entry - probe
    if close_probe <= 0:
        return None, "Cmimi i proves del nen zero"
    pnl_account = mt5.order_calc_profit(order_type, symbol, REFERENCE_LOTS, entry, close_probe)
    if pnl_account is None or not math.isfinite(float(pnl_account)) or float(pnl_account) <= 0:
        return None, "MT5 nuk llogariti fitim pozitiv per volumin reference 0.01"
    eur_per_price_unit = (float(pnl_account) * float(eur_rate)) / probe
    if eur_per_price_unit <= 0:
        return None, "Norma e fitimit rezultoi zero"
    distance = TARGET_EUR / eur_per_price_unit
    raw_tp = entry + distance if direction == "BUY" else entry - distance
    if raw_tp <= 0:
        return None, "Targeti del jashte cmimeve te vlefshme"
    tp = round_to_tick(raw_tp, tick_size, digits, direction)
    if (tp <= entry and direction == "BUY") or (tp >= entry and direction == "SELL"):
        return None, "TP nuk respekton drejtimin e tregtimit"
    projected = mt5.order_calc_profit(order_type, symbol, REFERENCE_LOTS, entry, tp)
    gross_eur = float(projected) * eur_rate if projected is not None else None
    if gross_eur is None or not math.isfinite(gross_eur) or gross_eur <= 0:
        return None, "Llogaritja finale e TP ne MT5 nuk u krye"
    return dict(tp=tp, distance=abs(tp-entry), gross_eur=gross_eur, digits=digits,
                step=tick_size if tick_size > 0 else point), ""


def setup_candidates(closed, closed5, atr, bull_engulf, bear_engulf, hammer, shooting):
    """Look for 3 different pattern families, never just forcing a signal count."""
    last = closed.iloc[-1]
    prev = closed.iloc[-2]
    last5 = closed5.iloc[-1]
    ema20, ema50, rsi = float(last["EMA20"]), float(last["EMA50"]), float(last["RSI"])
    m5_delta = float(last5["EMA20"] - closed5.iloc[-5]["EMA20"])
    m5_support_buy = bool(last5["EMA20"] >= last5["EMA50"] or (last5["close"] > last5["EMA20"] and m5_delta > 0))
    m5_support_sell = bool(last5["EMA20"] <= last5["EMA50"] or (last5["close"] < last5["EMA20"] and m5_delta < 0))
    m1_up, m1_down = ema20 > ema50, ema20 < ema50
    green = bool(last["close"] > last["open"])
    red = bool(last["close"] < last["open"])
    rng = max(float(last["high"] - last["low"]), 1e-12)
    body_ratio = abs(float(last["close"]-last["open"]))/rng
    near_ema_buy = bool(last["close"] >= ema20 and last["close"]-ema20 <= 1.2*atr)
    near_ema_sell = bool(last["close"] <= ema20 and ema20-last["close"] <= 1.2*atr)
    touched_ema_buy = bool((closed.iloc[-4:]["low"] <= closed.iloc[-4:]["EMA20"]+0.25*atr).any())
    touched_ema_sell = bool((closed.iloc[-4:]["high"] >= closed.iloc[-4:]["EMA20"]-0.25*atr).any())
    result = []

    # 1: Trend continuation (pullback to EMA20 + bounce with M5 support)
    if m1_up and m5_support_buy and 46 <= rsi <= 74 and green and near_ema_buy and touched_ema_buy and last["close"] > prev["close"]:
        result.append(("BUY", "TREND PULLBACK", "EMA20 bounce + M1/M5 alignment", 3))
    if m1_down and m5_support_sell and 26 <= rsi <= 54 and red and near_ema_sell and touched_ema_sell and last["close"] < prev["close"]:
        result.append(("SELL", "TREND PULLBACK", "EMA20 rejection + M1/M5 alignment", 3))

    # 2: Break and retest of previously established near-term level.
    old_high = float(closed.iloc[-26:-6]["high"].max())
    old_low = float(closed.iloc[-26:-6]["low"].min())
    recent_break_up = bool((closed.iloc[-6:-1]["close"] > old_high+0.08*atr).any())
    recent_break_down = bool((closed.iloc[-6:-1]["close"] < old_low-0.08*atr).any())
    if recent_break_up and last["low"] <= old_high+0.3*atr and last["close"] > old_high+0.04*atr and green and rsi < 77 and (m1_up or m5_support_buy):
        result.append(("BUY", "BREAK & RETEST", "Resistance broken; bullish retest", 4))
    if recent_break_down and last["high"] >= old_low-0.3*atr and last["close"] < old_low-0.04*atr and red and rsi > 23 and (m1_down or m5_support_sell):
        result.append(("SELL", "BREAK & RETEST", "Support broken; bearish retest", 4))

    # 3: Liquidity sweep reversal (can run before M5 EMA confirms).
    old_lows = float(closed.iloc[-19:-3]["low"].min())
    old_highs = float(closed.iloc[-19:-3]["high"].max())
    recent = closed.iloc[-3:]
    sweep_low = bool(((recent["low"] < old_lows - .04*atr) & (recent["close"] > old_lows)).any())
    sweep_high = bool(((recent["high"] > old_highs + .04*atr) & (recent["close"] < old_highs)).any())
    if sweep_low and 32 <= rsi <= 68 and green and (hammer or bull_engulf or last["close"] > prev["high"]):
        result.append(("BUY", "LIQUIDITY REVERSAL", "Sweep below lows; bullish rejection", 4))
    if sweep_high and 32 <= rsi <= 68 and red and (shooting or bear_engulf or last["close"] < prev["low"]):
        result.append(("SELL", "LIQUIDITY REVERSAL", "Sweep above highs; bearish rejection", 4))

    # 2b: Momentum break catches strong moves but rejects extension far from EMA20.
    prior_high = float(closed.iloc[-18:-1]["high"].max())
    prior_low = float(closed.iloc[-18:-1]["low"].min())
    if (m1_up and m5_support_buy and 50 <= rsi <= 76 and green and body_ratio >= .58
            and last["close"] > prior_high+.07*atr and last["close"]-ema20 <= 1.7*atr):
        result.append(("BUY", "BREAKOUT", "Momentum breakout with EMA/M5 alignment", 2))
    if (m1_down and m5_support_sell and 24 <= rsi <= 50 and red and body_ratio >= .58
            and last["close"] < prior_low-.07*atr and ema20-last["close"] <= 1.7*atr):
        result.append(("SELL", "BREAKOUT", "Momentum breakdown with EMA/M5 alignment", 2))
    return sorted(result, key=lambda c:c[3], reverse=True)


def evaluate_symbol(log, closed, symbol):
    """After entry, evaluate candle highs/lows for hypothetical TP/SL.

    For SELL, ask is approximated by bid + spread at signal; future actual
    spreads are unknown. If both levels hit in one candle, mark ambiguous.
    """
    pos = {int(epoch): idx for idx, epoch in enumerate(closed["epoch"])}
    changed = False
    oldest = int(closed["epoch"].iloc[0])
    for idx, row in log[log["symbol"] == symbol].iterrows():
        if row["status"] != "PENDING":
            continue
        start = pos.get(int(row["epoch"]))
        if start is None:
            if int(row["epoch"]) < oldest:
                log.at[idx, "status"] = "NO_DATA"
                log.at[idx, "result"] = "UNKNOWN"
                log.at[idx, "note"] = "Qirinjt historike dolen jashte MT5 lookback"
                changed = True
            continue
        end = min(len(closed), start+MAX_EVAL_BARS+1)
        sl = float(row["sl"])
        tp = float(row["tp"])
        direction = str(row["signal"])
        spread = float(row["spread_snapshot"])
        for i in range(start+1, end):
            bar = closed.iloc[i]
            low = float(bar["low"]) + (spread if direction == "SELL" else 0)
            high = float(bar["high"]) + (spread if direction == "SELL" else 0)
            hit_tp = (high >= tp) if direction == "BUY" else (low <= tp)
            hit_sl = (low <= sl) if direction == "BUY" else (high >= sl)
            if hit_tp or hit_sl:
                if hit_tp and hit_sl:
                    outcome, note = "AMBIGUOUS", "TP dhe SL brenda te njejtit M1: rendi i panjohur"
                elif hit_tp:
                    outcome, note = "TP", "TP u prek sipas OHLC M1; jo transaksion real"
                else:
                    outcome, note = "SL", "SL u prek sipas OHLC M1; jo transaksion real"
                log.at[idx, "status"] = "EVALUATED"
                log.at[idx, "result"] = outcome
                log.at[idx, "resolved_epoch"] = int(bar["epoch"])
                log.at[idx, "note"] = note
                changed = True
                break
        else:
            if len(closed)-1-start >= MAX_EVAL_BARS:
                log.at[idx, "status"] = "EXPIRED"
                log.at[idx, "result"] = "TIMEOUT"
                log.at[idx, "resolved_epoch"] = int(closed.iloc[start+MAX_EVAL_BARS]["epoch"])
                log.at[idx, "note"] = f"As TP as SL brenda {MAX_EVAL_BARS} qirinjve"
                changed = True
    return log, changed


def live_feed_status(label, tick_timestamp, closed_m1_timestamp, forming_m1_timestamp):
    """Check MT5 data with MT5-relative candle times and observed tick progression.

    Comparing MT5 broker timestamps directly to time.time() can incorrectly
    reject a live feed when the broker/terminal timestamp clock is offset.
    Do not trust relative timestamps alone: require a tick update actually
    observed in this Streamlit session, then expire it if updates stop.
    """
    now = time.time()
    tick_ts = int(tick_timestamp)
    last_closed = int(closed_m1_timestamp)
    forming = int(forming_m1_timestamp)
    closed_lag = tick_ts - last_closed
    forming_lag = tick_ts - forming

    if not (0 <= closed_lag <= 210 and -5 <= forming_lag <= 90):
        return False, ("Qirinjte M1 nuk perputhen me tick-un e MT5 "
                       f"(closed lag {closed_lag}s; current lag {forming_lag}s)")

    key = f"beast_live_tick_{label}"
    prev = st.session_state.get(key)
    if prev is None or tick_ts < prev["tick"]:
        st.session_state[key] = {"tick": tick_ts, "last_changed": now, "verified": False}
        return False, "Po presim tick te ri per me verifiku live feed-in e MT5"

    if tick_ts > prev["tick"]:
        prev = {"tick": tick_ts, "last_changed": now, "verified": True}
        st.session_state[key] = prev

    if not prev["verified"]:
        return False, "Po presim tick te ri per me verifiku live feed-in e MT5"

    idle = now - prev["last_changed"]
    if idle > 30:
        return False, f"Nuk ka tick te ri te verifikuar qe {idle:.0f}s"
    return True, "Tick dhe qirinj M1 live te verifikuar"


def analyze(symbol, label, tick, df, df5, log, eur_rate):
    closed, closed5 = df.iloc[:-1].copy(), df5.iloc[:-1].copy()
    last, last5 = closed.iloc[-1], closed5.iloc[-1]
    price = float(last["close"])
    atr = float(last["ATR14"])
    atr5 = float(last5["ATR14"])
    spread = max(0., float(tick.ask-tick.bid))
    previous_m5 = closed5.iloc[-37:-1]
    support = float(previous_m5["low"].min())
    resistance = float(previous_m5["high"].max())
    zone_width = max(.3*atr5, .5*atr)
    near_support = abs(price-support) <= zone_width
    near_resistance = abs(price-resistance) <= zone_width
    shooting, hammer, bull_engulf, bear_engulf = candle_patterns(closed)
    bull_fvg, bull_zone = nearby_fvg(closed,"BUY",atr)
    bear_fvg, bear_zone = nearby_fvg(closed,"SELL",atr)
    bos_up,bos_down,choch_up,choch_down=market_features(closed)
    highs=closed.iloc[-13:-1]["high"]
    lows=closed.iloc[-13:-1]["low"]
    swept_high=bool(last["high"]>highs.max() and last["close"]<highs.max())
    swept_low=bool(last["low"]<lows.min() and last["close"]>lows.min())
    bullish={"Bullish FVG":bull_fvg,"Hammer":hammer and near_support,
             "Bullish Engulfing":bull_engulf,"BOS bullish":bos_up,
             "CHoCH proxy bullish":choch_up,"Liquidity sweep poshte":swept_low,
             "Support zone":near_support}
    bearish={"Bearish FVG":bear_fvg,"Shooting Star":shooting and near_resistance,
             "Bearish Engulfing":bear_engulf,"BOS bearish":bos_down,
             "CHoCH proxy bearish":choch_down,"Liquidity sweep lart":swept_high,
             "Resistance zone":near_resistance}
    bull_score=sum(bool(v) for k,v in bullish.items() if not k.startswith("CHoCH"))
    bear_score=sum(bool(v) for k,v in bearish.items() if not k.startswith("CHoCH"))
    trend5=("BULLISH" if last5["EMA20"]>last5["EMA50"] else "BEARISH" if last5["EMA20"]<last5["EMA50"] else "NEUTRAL")
    old_liquidity_ok=bool(math.isfinite(atr) and atr>0 and spread<=.35*atr)
    # Preserve old diagnostics as reference, not as the new entry gate.
    buy_conditions=[("EMA20 mbi EMA50 M1",bool(last["EMA20"]>last["EMA50"])),
                    ("RSI M1 midis 50-70",bool(50<last["RSI"]<70)),
                    ("Trendi M5 bullish",trend5=="BULLISH"),
                    (f"Price Action bullish >= {MIN_CONFLUENCES}",bull_score>=MIN_CONFLUENCES),
                    ("Jo prane Resistance",not near_resistance),
                    ("Spread / ATR sipas V6.1",old_liquidity_ok)]
    sell_conditions=[("EMA20 nen EMA50 M1",bool(last["EMA20"]<last["EMA50"])),
                     ("RSI M1 midis 30-50",bool(30<last["RSI"]<50)),
                     ("Trendi M5 bearish",trend5=="BEARISH"),
                     (f"Price Action bearish >= {MIN_CONFLUENCES}",bear_score>=MIN_CONFLUENCES),
                     ("Jo prane Support",not near_support),
                     ("Spread / ATR sipas V6.1",old_liquidity_ok)]

    epoch=int(last["epoch"])
    symlog=log[log["symbol"]==label]
    epochs=pd.to_numeric(symlog["epoch"],errors="coerce").dropna()
    already=(epoch in set(epochs.astype("int64"))) if not epochs.empty else False
    cooldown=epochs.empty or epoch-int(epochs.max())>=COOLDOWN_BARS*60
    market_fresh, feed_reason = live_feed_status(
        label, int(tick.time), epoch, int(df.iloc[-1]["epoch"])
    )
    signal="WAIT"
    entry=tp=sl=rr=gross_target_eur=None
    setup="NO SETUP"
    reason="Asnje nga setup-et (Trend Pullback, Break/Retest, Liquidity Reversal) nuk u formua"
    checks=[]
    if not market_fresh:
        reason=f"{feed_reason}; nuk regjistrohen sinjale"
    elif not math.isfinite(atr) or atr<=0:
        reason="ATR i pavlefshem"
    else:
        candidates=setup_candidates(closed,closed5,atr,bull_engulf,bear_engulf,hammer,shooting)
        if not candidates:
            checks.append("Asnje setup i konfirmuar M1")
        for direction, family, description, priority in candidates:
            candidate_entry=float(tick.ask if direction=="BUY" else tick.bid)
            calc, why=tp_for_eur(symbol,direction,candidate_entry,atr,spread,eur_rate)
            if calc is None:
                checks.append(f"{family}: {why}")
                continue
            # Both spread-vs-ATR and spread-vs-target should be viable.
            spread_allowed=(spread<=max(.65*atr,1e-12) and spread<=.25*calc["distance"])
            if not spread_allowed:
                checks.append(f"{family}: spread i larte kundrejt ATR ose TP")
                continue
            padding=max(.18*atr,1.2*spread)
            if direction=="BUY":
                structural_sl=float(closed.iloc[-13:]["low"].min())-padding
                min_stop=2*spread
                candidate_sl=min(structural_sl,candidate_entry-min_stop)
                risk=candidate_entry-candidate_sl
            else:
                structural_sl=float(closed.iloc[-13:]["high"].max())+padding
                min_stop=2*spread
                candidate_sl=max(structural_sl,candidate_entry+min_stop)
                risk=candidate_sl-candidate_entry
            candidate_rr=calc["distance"]/risk if risk>0 else 0
            if candidate_rr<MIN_RR:
                checks.append(f"{family}: R/R {candidate_rr:.2f} nen {MIN_RR:.1f}")
                continue
            if candidate_rr>15:
                checks.append(f"{family}: SL shume i ngushte kundrejt TP, verifiko volatilitetin")
                continue
            # Reference entry, TP and SL: NOT instructions sent to MT5.
            signal=direction
            setup=family
            reason=description
            entry=candidate_entry
            tp=calc["tp"]
            sl=round(candidate_sl,calc["digits"])
            rr=candidate_rr
            gross_target_eur=calc["gross_eur"]
            break
        if signal=="WAIT" and checks:
            reason="; ".join(checks[:3])
    return dict(symbol=symbol,label=label,tick=tick,df=df,closed=closed,last=last,last5=last5,
                price=price,atr=atr,spread=spread,support=support,resistance=resistance,
                width=zone_width,bullish=bullish,bearish=bearish,bull_score=bull_score,
                bear_score=bear_score,bull_fvg=bull_fvg,bear_fvg=bear_fvg,
                bull_zone=bull_zone,bear_zone=bear_zone,trend5=trend5,signal=signal,
                evidence=[reason],buy_checks=buy_conditions,sell_checks=sell_conditions,
                epoch=epoch,already=already,cooldown=cooldown,setup=setup,entry=entry,tp=tp,
                sl=sl,rr=rr,gross_target_eur=gross_target_eur,market_fresh=market_fresh)


def chart_for(x):
    view = x["df"].tail(160)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=view["chart_time"], open=view["open"], high=view["high"], low=view["low"], close=view["close"], name=x["label"]))
    fig.add_trace(go.Scatter(x=view["chart_time"], y=view["EMA20"], name="EMA20", line=dict(color="cyan", width=1.8)))
    fig.add_trace(go.Scatter(x=view["chart_time"], y=view["EMA50"], name="EMA50", line=dict(color="orange", width=1.8)))
    fig.add_hrect(y0=x["support"]-x["width"], y1=x["support"]+x["width"], fillcolor="green", opacity=.12, line_width=0)
    fig.add_hrect(y0=x["resistance"]-x["width"], y1=x["resistance"]+x["width"], fillcolor="red", opacity=.12, line_width=0)
    fig.add_hline(y=x["support"], line_color="limegreen", line_dash="dot")
    fig.add_hline(y=x["resistance"], line_color="tomato", line_dash="dot")
    right = view["chart_time"].iloc[-1]
    for active, zone, color in [
        (x["bull_fvg"], x["bull_zone"], "rgba(0,190,255,.20)"),
        (x["bear_fvg"], x["bear_zone"], "rgba(255,140,0,.20)"),
    ]:
        if active and zone:
            low, high, start = zone
            fig.add_shape(type="rect", x0=start, x1=right, y0=low, y1=high, fillcolor=color, line=dict(width=0), layer="below")
    fig.update_layout(title=f"{x['label']} | M1 / EMA / Support-Resistance / FVG", template="plotly_dark", height=350,
                      paper_bgcolor="#0a1829", plot_bgcolor="#0a1829", margin=dict(l=8,r=8,b=8,t=42),
                      font=dict(color="#b4d2df",size=10), xaxis=dict(gridcolor="#254257"),
                      yaxis=dict(gridcolor="#254257"), xaxis_rangeslider_visible=False)
    return fig


def rsi_for(x):
    view=x["df"].tail(160)
    fig=go.Figure(go.Scatter(x=view["chart_time"],y=view["RSI"],name="RSI 14",line=dict(color="#f4d44d",width=1.8)))
    fig.add_hline(y=70,line_dash="dash",line_color="red")
    fig.add_hline(y=30,line_dash="dash",line_color="limegreen")
    fig.update_layout(title="RSI 14",template="plotly_dark",height=155,margin=dict(l=8,r=8,b=8,t=32),
                      paper_bgcolor="#0a1829",plot_bgcolor="#0a1829",font=dict(size=10),
                      yaxis=dict(range=[0,100],gridcolor="#254257"),xaxis=dict(gridcolor="#254257"))
    return fig


def fmt(v, x):
    digits = 2 if x["label"] == "XAUUSD" else 2 if x["label"] == "BTCUSD" else 5 if x["label"] == "GBPUSD" else 3
    return f"{float(v):.{digits}f}"


def display_pair(x):
    st.markdown(f"#### {'🟢' if x['signal']=='BUY' else '🔴' if x['signal']=='SELL' else '🟡'} {x['label']} — {x['signal']}")
    st.caption(f"MT5: {x['symbol']} | M5 trend: {x['trend5']} | {'; '.join(x['evidence'])}")
    m1,m2,m3,m4=st.columns(4)
    m1.metric("BUY ask",fmt(x["tick"].ask,x))
    m2.metric("SELL bid",fmt(x["tick"].bid,x))
    m3.metric("RSI 14",f"{x['last']['RSI']:.1f}")
    m4.metric("ATR14 M1",fmt(x["atr"],x))
    e1,e2,e3,e4=st.columns(4)
    e1.metric("EMA20",fmt(x["last"]["EMA20"],x))
    e2.metric("EMA50",fmt(x["last"]["EMA50"],x))
    e3.metric("Support M5",fmt(x["support"],x))
    e4.metric("Resistance M5",fmt(x["resistance"],x))
    st.caption(f"Price Action: {x['bull_score']} bullish / {x['bear_score']} bearish. Bullish: "
               + (", ".join(k for k,v in x["bullish"].items() if v) or "asnje")
               + "; Bearish: " + (", ".join(k for k,v in x["bearish"].items() if v) or "asnje"))
    st.markdown("**🔍 Signal Diagnostics**")
    bu,se=st.columns(2)
    with bu:
        st.caption("🟢 BUY CONDITIONS")
        for label,ok in x["buy_checks"]:
            st.markdown(("✅ " if ok else "❌ ")+label)
    with se:
        st.caption("🔴 SELL CONDITIONS")
        for label,ok in x["sell_checks"]:
            st.markdown(("✅ " if ok else "❌ ")+label)
    if x["signal"] in ("BUY", "SELL"):
        st.caption(f"🎯 SETUP: {x['setup']} | ENTRY {fmt(x['entry'],x)} | "
                   f"TP {fmt(x['tp'],x)} | SL {fmt(x['sl'],x)} | "
                   f"R/R {x['rr']:.2f} | TP ≈ €{x['gross_target_eur']:.2f} bruto per 0.01 lot")
    else:
        st.caption(f"🔎 SETUP WATCH: {x['evidence'][0]}")
    st.caption("Cooldown: " + ("gati" if x["cooldown"] else "aktiv") + " | Spread: " + fmt(x["spread"],x))
    st.plotly_chart(chart_for(x),use_container_width=True,key=f"chart_{x['label']}")
    st.plotly_chart(rsi_for(x),use_container_width=True,key=f"rsi_{x['label']}")


st.caption("Katër instrumente monitorohen pa ndërruar menytë. Vetëm sinjale eksperimentale; nuk hapen ose mbyllen pozita.")

if not mt5.initialize():
    st.error(f"MT5 nuk u lidh: {mt5.last_error()}")
    st.stop()

try:
    available = mt5.symbols_get()
    if available is None:
        st.error(f"Nuk po merret lista e instrumenteve nga MT5: {mt5.last_error()}")
        st.stop()
    names = [s.name for s in available]
    log = load_log()
    account = mt5.account_info()
    account_currency = str(account.currency) if account is not None else ""
    eur_rate, conversion_note = euro_conversion_rate(account_currency, names) if account_currency else (None, "MT5 account_info mungon")
    if eur_rate is None:
        st.warning(f"TP per 5 EUR nuk mund te llogaritet: {conversion_note}. Sinjalet mbeten WAIT deri ne zgjidhje.")
    assets = []
    changes = False
    problems = []

    for requested in WANTED:
        symbol = find_symbol(requested,names)
        if symbol is None:
            problems.append(f"{requested}: nuk gjendet ne listen e MT5. Kontrollo Market Watch te Vantage.")
            continue
        if not mt5.symbol_select(symbol,True):
            problems.append(f"{requested}: nuk mund te aktivizohet {symbol} ne Market Watch.")
            continue
        tick = mt5.symbol_info_tick(symbol)
        m1 = mt5.copy_rates_from_pos(symbol,mt5.TIMEFRAME_M1,0,600)
        m5 = mt5.copy_rates_from_pos(symbol,mt5.TIMEFRAME_M5,0,250)
        if tick is None or m1 is None or m5 is None or len(m1)<100 or len(m5)<80:
            problems.append(f"{requested}: te dhena te pamjaftueshme M1/M5 per {symbol}.")
            continue
        frame1,frame5=indicators(m1),indicators(m5)
        x=analyze(symbol,requested,tick,frame1,frame5,log,eur_rate)
        assets.append(x)
        if x["signal"] in ("BUY", "SELL") and not x["already"] and x["cooldown"] and x["market_fresh"]:
            new={
                "symbol":requested, "epoch":x["epoch"], "signal":x["signal"],
                "setup":x["setup"], "entry":round(x["entry"],8), "tp":round(x["tp"],8),
                "sl":round(x["sl"],8), "rr":round(x["rr"],3),
                "gross_target_eur":round(x["gross_target_eur"],3),
                "spread_snapshot":round(x["spread"],8), "reason":"; ".join(x["evidence"]),
                "status":"PENDING", "result":"PENDING", "resolved_epoch":None,
                "note":"Hipotetik; entry ne kuoten MT5; komisionet dhe slippage nuk perfshihen",
            }
            log=pd.concat([log,pd.DataFrame([new])],ignore_index=True)
            changes=True
        log,updated=evaluate_symbol(log,x["closed"],requested)
        changes=changes or updated

    if changes:
        try:
            tmp=LOG_FILE.with_suffix(".tmp")
            log.to_csv(tmp,index=False)
            tmp.replace(LOG_FILE)
        except OSError as exc:
            st.error(f"S'po mundet me u ruajt historiku: {exc}. Mbylle CSV nese eshte i hapur ne Excel.")

    for msg in problems:
        st.warning(msg)
    if not assets:
        st.error("Asnje instrument nuk eshte ngarkuar. Kontrollo lidhjen MT5 dhe Market Watch.")
        st.stop()

    st.success("🟢 MT5 CONNECTED | AUTO REFRESH 5 SEC | SIGNALS ONLY")
    overview=st.columns(4)
    by_label={x["label"]:x for x in assets}
    for col, label in zip(overview,WANTED):
        with col:
            if label not in by_label:
                st.metric(label,"NO DATA")
                st.caption("MT5 symbol unavailable")
            else:
                x=by_label[label]
                glyph={"BUY":"🟢","SELL":"🔴","WAIT":"🟡"}[x["signal"]]
                st.metric(label,fmt(x["price"],x))
                st.caption(f"{glyph} {x['signal']} | M5 {x['trend5']} | {x['setup']}")

    st.divider()
    st.subheader("🧠 BEAST SIGNAL ENGINE + DIAGNOSTICS | ALL MARKETS")
    # All four analyses visible, without changing tabs or clicking pair selectors.
    for i in range(0,len(WANTED),2):
        left,right=st.columns(2,gap="large")
        for col,label in [(left,WANTED[i]),(right,WANTED[i+1])]:
            with col:
                if label in by_label:
                    display_pair(by_label[label])
                else:
                    st.warning(f"{label} ende pa te dhena. Shiko paralajmerimin lart.")
        st.divider()

    st.subheader("📋 BEAST SIGNAL TRACKER | ALL PAIRS")
    tp_hits=int((log["result"]=="TP").sum()) if len(log) else 0
    sl_hits=int((log["result"]=="SL").sum()) if len(log) else 0
    pending=int((log["status"]=="PENDING").sum()) if len(log) else 0
    clear=tp_hits+sl_hits
    t1,t2,t3,t4=st.columns(4)
    t1.metric("Sinjale V6.2",len(log))
    t2.metric("TP touched",tp_hits)
    t3.metric("SL touched",sl_hits)
    t4.metric("TP hit rate",f"{100*tp_hits/clear:.1f}%" if clear else "N/A")
    st.caption(f"Pending: {pending} | TP dhe SL te simuluara nga M1 OHLC ne {MAX_EVAL_BARS} qirinj; "
               "ambiguous/timeouts nuk futen ne TP hit rate. Jo P/L real.")
    today_utc=pd.Timestamp.now(tz="UTC").date()
    if len(log):
        dates=pd.to_datetime(log["epoch"],unit="s",utc=True,errors="coerce").dt.date
    else:
        dates=pd.Series(dtype="object")
    cols=st.columns(4)
    for col,pair in zip(cols,WANTED):
        count=int(((log["symbol"]==pair) & (dates==today_utc)).sum()) if len(log) else 0
        with col:
            st.metric(f"{pair} sot (UTC)",f"{count} / 10")
    st.caption("10 sinjale/ditë/pair eshte objektiv per t'u matur, jo kuote qe prodhon sinjale te detyruara.")
    if len(log):
        display=log.tail(100).iloc[::-1].copy()
        display.insert(0,"Koha UTC",pd.to_datetime(display["epoch"],unit="s",utc=True).dt.strftime("%Y-%m-%d %H:%M"))
        st.dataframe(display.drop(columns=["epoch"]),use_container_width=True,hide_index=True)
    else:
        st.info("V6.2 ende nuk ka sinjale. Sinjale krijohen vetem gjate kuotimeve aktive.")
    st.caption("CSV i ri: beast_signals_multi_v62.csv | V6.1 ruhet i pandryshuar ne beast_signals_multi_v6.csv. "
               "TP = rreth €5 bruto per reference 0.01 lot sipas specifikave MT5. "
               "Komisionet, slippage, ndryshimet e spread-it dhe latenca nuk jane te llogaritura.")
    old=old_log_for_display()
    if old is not None:
        with st.expander(f"📁 Historiku i meparshem V6.1 ({len(old)} sinjale) - vetem lexim"):
            st.caption("V6.1 maste drejtimin pas 5 minutash; V6.2 teston TP/SL. "
                       "Statistikat nuk duhet te perzihen.")
            st.dataframe(old.tail(100).iloc[::-1],use_container_width=True,hide_index=True)
    st.caption("Vetem analize edukative/demo. Asnje pozite nuk hapet automatikisht. "
               "As TP i shenuar nuk garanton ekzekutim real apo fitim neto.")
finally:
    mt5.shutdown()
