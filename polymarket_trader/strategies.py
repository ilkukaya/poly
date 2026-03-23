"""
TRADING STRATEGIES
==================
Multi-category strategy engine for Polymarket paper trading.

Strategies:
1. PENNY_PICK   - Near-resolved markets with remaining edge
2. VALUE_BET    - Mispriced markets vs external signals
3. MOMENTUM     - Markets with strong directional movement
4. CALENDAR     - Time-decay plays on expiring markets
5. MEAN_REVERT  - Overreaction plays
6. SPREAD_ARB   - Related markets with inconsistent pricing
"""

from datetime import datetime, timezone, timedelta
from config import MIN_EDGE_PCT, HIGH_CONFIDENCE_EDGE, MIN_LIQUIDITY
import api


class Signal:
    """A trading signal with all necessary info."""
    def __init__(self, market, side, edge, confidence, strategy, notes="", cap_efficiency=1.0):
        self.market = market
        self.side = side              # "YES" or "NO"
        self.edge = edge              # Expected edge (0.05 = 5%)
        self.confidence = confidence  # 0-1 score
        self.strategy = strategy      # Strategy name
        self.notes = notes
        self.cap_efficiency = cap_efficiency  # Capital efficiency multiplier
        self.entry_price = market['yes_price'] if side == "YES" else market['no_price']
        self.estimated_prob = self.entry_price + edge if side == "YES" else self.entry_price + edge
    
    def __repr__(self):
        return (f"Signal({self.strategy} | {self.side} @ {self.entry_price:.3f} | "
                f"Edge: {self.edge:.1%} | Conf: {self.confidence:.0%} | "
                f"{self.market['question'][:50]})")
    
    def to_dict(self):
        return {
            "market_id": self.market['id'],
            "question": self.market['question'],
            "slug": self.market.get('slug', ''),
            "side": self.side,
            "entry_price": self.entry_price,
            "edge": self.edge,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "category": self.market.get('category', 'other'),
            "liquidity": self.market.get('liquidity', 0),
            "volume_24h": self.market.get('volume_24h', 0),
            "notes": self.notes,
        }


def scan_penny_picks(markets):
    """
    PENNY PICK STRATEGY
    Find markets where outcome is nearly certain but price hasn't fully converged.
    
    Logic: Markets with YES price between 85-97¢ (or NO between 85-97¢)
    where the outcome is very likely known. Buy at 93¢, collect 7¢ when
    it resolves to 100¢. Quick turnaround, low risk per trade.
    
    Best for: Sports (games in progress or about to end), 
              Politics (elections with clear winner),
              Events with known outcomes pending resolution
    
    CAPITAL EFFICIENCY: Heavily penalize markets > 14 days to resolution.
    """
    signals = []
    now = datetime.now(timezone.utc)
    
    for m in markets:
        q = m['question'].lower()
        yes_p = m['yes_price']
        no_p = m['no_price']
        liq = m['liquidity']
        vol24 = m['volume_24h']
        end_date = m.get('end_date', '')
        
        # Calculate days to resolution
        days_left = 999
        if end_date:
            try:
                if 'T' in end_date:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                else:
                    end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                days_left = max((end_dt - now).total_seconds() / 86400, 0.1)
            except:
                pass
        
        # CRITICAL: Skip markets resolving > 21 days out (capital efficiency)
        if days_left > 21:
            continue
        
        # Skip low liquidity
        if liq < 3000:
            continue
        
        # HIGH YES scenario (85-97¢) - likely YES outcome
        if 0.85 <= yes_p <= 0.97:
            # Conservative edge: we don't think it's 100%, just higher than market
            # Scale edge based on how high the price already is
            raw_gap = 1.0 - yes_p
            edge = raw_gap * 0.6  # We capture ~60% of the gap conservatively
            # Higher confidence if high volume and tight spread
            conf = min(0.55 + (vol24 / 1000000) * 0.25 + (1 - m['spread'] / 0.05) * 0.15, 0.92)
            
            if edge >= 0.02:  # At least 2¢ edge
                # Capital efficiency bonus: faster resolution = higher score
                cap_eff = min(7.0 / max(days_left, 0.1), 2.0)  # Bonus for <7 day markets
                signals.append(Signal(
                    market=m, side="YES", edge=edge, confidence=conf,
                    strategy="PENNY_PICK",
                    notes=f"Near-resolved YES at {yes_p:.3f}. Est. edge {edge:.1%} (gap: {raw_gap:.1%}). {days_left:.1f}d left.",
                    cap_efficiency=cap_eff,
                ))
        
        # HIGH NO scenario - likely NO outcome  
        if 0.85 <= no_p <= 0.97:
            raw_gap = 1.0 - no_p
            edge = raw_gap * 0.6
            conf = min(0.55 + (vol24 / 1000000) * 0.25 + (1 - m['spread'] / 0.05) * 0.15, 0.92)
            
            if edge >= 0.02:
                cap_eff = min(7.0 / max(days_left, 0.1), 2.0)
                signals.append(Signal(
                    market=m, side="NO", edge=edge, confidence=conf,
                    strategy="PENNY_PICK",
                    notes=f"Near-resolved NO at {no_p:.3f}. Est. edge {edge:.1%} (gap: {raw_gap:.1%}). {days_left:.1f}d left.",
                    cap_efficiency=cap_eff,
                ))
    
    return signals


def scan_value_bets(markets):
    """
    VALUE BET STRATEGY
    Find markets where Polymarket price significantly deviates from 
    what we estimate the true probability to be.
    
    For now, uses heuristics. Later can integrate external odds APIs.
    
    Key heuristics:
    - High competitive score + unusual price = possible mispricing
    - Large price change in last hour without obvious catalyst
    - Spread markets vs moneyline inconsistencies
    """
    signals = []
    
    for m in markets:
        yes_p = m['yes_price']
        change_1h = m.get('price_change_1h', 0)
        change_1d = m.get('price_change_1d', 0)
        competitive = m.get('competitive', 0)
        liq = m['liquidity']
        vol24 = m['volume_24h']
        
        if liq < MIN_LIQUIDITY:
            continue
        
        # Pattern 1: Sharp recent move that might be overextended
        # If price moved >10% in 1h but market is highly competitive
        if abs(change_1h) > 0.10 and competitive > 0.8:
            # The market moved fast - if it's competitive, it might revert
            # But we need to be careful - it might have moved for good reason
            pass  # Reserved for later with more data
        
        # Pattern 2: Price between 40-60¢ with high volume
        # These are "coin flip" markets where small edges matter most
        if 0.40 <= yes_p <= 0.60 and vol24 > 100000 and liq > 50000:
            # Look for signals that give us a directional edge
            # Recent momentum (1d change) as a weak signal
            if change_1d > 0.03:
                edge = min(change_1d * 0.5, 0.08)  # Conservative: half the momentum
                signals.append(Signal(
                    market=m, side="YES", edge=edge, confidence=0.55,
                    strategy="VALUE_BET",
                    notes=f"Coin-flip market with positive momentum. 1d change: {change_1d:+.3f}"
                ))
            elif change_1d < -0.03:
                edge = min(abs(change_1d) * 0.5, 0.08)
                signals.append(Signal(
                    market=m, side="NO", edge=edge, confidence=0.55,
                    strategy="VALUE_BET",
                    notes=f"Coin-flip market with negative momentum. 1d change: {change_1d:+.3f}"
                ))
    
    return signals


def scan_calendar_plays(markets):
    """
    CALENDAR / TIME DECAY STRATEGY
    Markets expiring soon where the probability should be moving
    toward 0 or 100 as time runs out.
    
    Logic: If "Will X happen by March 31?" is at 10¢ with 7 days left
    and no signs of X happening, selling YES (buying NO) at 90¢ collects
    10¢ when time expires. The key is identifying markets where time
    is working strongly in one direction.
    """
    signals = []
    now = datetime.now(timezone.utc)
    
    for m in markets:
        end_str = m.get('end_date', '')
        if not end_str:
            continue
        
        try:
            if 'T' in end_str:
                end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            else:
                end_date = datetime.strptime(end_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except:
            continue
        
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        days_left = (end_date - now).days
        
        if days_left < 1 or days_left > 30:
            continue
        
        yes_p = m['yes_price']
        no_p = m['no_price']
        liq = m['liquidity']
        q = m['question'].lower()
        
        if liq < 5000:
            continue
        
        # Pattern: "Will X happen by [date]?" with low YES price and time running out
        # If YES is < 15¢ and < 7 days left → likely NO. Buy NO.
        if yes_p <= 0.15 and days_left <= 7:
            edge = yes_p * 0.7  # Conservative: assume 70% of YES price is edge
            conf = min(0.6 + (0.15 - yes_p) * 3 + (7 - days_left) / 7 * 0.2, 0.90)
            
            signals.append(Signal(
                market=m, side="NO", edge=edge, confidence=conf,
                strategy="CALENDAR",
                notes=f"Time decay play. YES at {yes_p:.3f} with {days_left}d left. "
                      f"Collect ~{yes_p*100:.1f}¢ if nothing happens."
            ))
        
        # Pattern: YES is > 85¢ and < 7 days → likely YES. Buy YES if edge exists.
        if yes_p >= 0.85 and days_left <= 7:
            edge = (1 - yes_p) * 0.6
            conf = min(0.6 + (yes_p - 0.85) * 3 + (7 - days_left) / 7 * 0.2, 0.90)
            
            if edge >= 0.02:
                signals.append(Signal(
                    market=m, side="YES", edge=edge, confidence=conf,
                    strategy="CALENDAR",
                    notes=f"Time decay play. YES at {yes_p:.3f} with {days_left}d left."
                ))
    
    return signals


def scan_momentum(markets):
    """
    MOMENTUM STRATEGY
    Markets with strong directional movement across multiple timeframes.
    
    Logic: If 1h change AND 1d change are both positive and significant,
    momentum is building. Enter in the direction of momentum.
    
    Works best for: Geopolitics (escalation/de-escalation),
                    Crypto (price levels), Sports futures
    """
    signals = []
    
    for m in markets:
        change_1h = m.get('price_change_1h', 0)
        change_1d = m.get('price_change_1d', 0)
        change_1w = m.get('price_change_1w', 0)
        yes_p = m['yes_price']
        liq = m['liquidity']
        vol24 = m['volume_24h']
        
        if liq < 10000 or vol24 < 50000:
            continue
        
        # Skip near-resolved
        if yes_p > 0.90 or yes_p < 0.10:
            continue
        
        # Strong bullish momentum: both 1h and 1d positive, significant
        if change_1h > 0.02 and change_1d > 0.05:
            edge = min(change_1d * 0.3, 0.10)  # Conservative fraction of momentum
            conf = min(0.50 + abs(change_1d) * 2, 0.75)
            
            signals.append(Signal(
                market=m, side="YES", edge=edge, confidence=conf,
                strategy="MOMENTUM",
                notes=f"Bullish momentum. 1h: {change_1h:+.3f}, 1d: {change_1d:+.3f}, 1w: {change_1w:+.3f}"
            ))
        
        # Strong bearish momentum
        elif change_1h < -0.02 and change_1d < -0.05:
            edge = min(abs(change_1d) * 0.3, 0.10)
            conf = min(0.50 + abs(change_1d) * 2, 0.75)
            
            signals.append(Signal(
                market=m, side="NO", edge=edge, confidence=conf,
                strategy="MOMENTUM",
                notes=f"Bearish momentum. 1h: {change_1h:+.3f}, 1d: {change_1d:+.3f}, 1w: {change_1w:+.3f}"
            ))
    
    return signals


def scan_mean_reversion(markets):
    """
    MEAN REVERSION STRATEGY
    Markets that overreacted to news/events and are likely to revert.
    
    Logic: If 1w change is very large but 1h change is reversing,
    the initial reaction was overdone.
    
    Best for: Geopolitics (panic spikes), Crypto (BTC dip markets)
    """
    signals = []
    
    for m in markets:
        change_1h = m.get('price_change_1h', 0)
        change_1d = m.get('price_change_1d', 0)
        change_1w = m.get('price_change_1w', 0)
        yes_p = m['yes_price']
        liq = m['liquidity']
        
        if liq < 20000:
            continue
        if yes_p > 0.90 or yes_p < 0.10:
            continue
        
        # Pattern: Large weekly move but hourly reversal starting
        if change_1w > 0.15 and change_1h < -0.01:
            edge = min(abs(change_1w) * 0.15, 0.08)
            conf = 0.55
            
            signals.append(Signal(
                market=m, side="NO", edge=edge, confidence=conf,
                strategy="MEAN_REVERT",
                notes=f"Potential overreaction. 1w: {change_1w:+.3f}, 1h reversal: {change_1h:+.3f}"
            ))
        
        elif change_1w < -0.15 and change_1h > 0.01:
            edge = min(abs(change_1w) * 0.15, 0.08)
            conf = 0.55
            
            signals.append(Signal(
                market=m, side="YES", edge=edge, confidence=conf,
                strategy="MEAN_REVERT",
                notes=f"Potential overreaction. 1w: {change_1w:+.3f}, 1h reversal: {change_1h:+.3f}"
            ))
    
    return signals


def run_all_strategies(markets):
    """Run all strategies and return ranked signals."""
    all_signals = []
    
    # Run each strategy
    strategies = [
        ("PENNY_PICK", scan_penny_picks),
        ("VALUE_BET", scan_value_bets),
        ("CALENDAR", scan_calendar_plays),
        ("MOMENTUM", scan_momentum),
        ("MEAN_REVERT", scan_mean_reversion),
    ]
    
    for name, func in strategies:
        try:
            signals = func(markets)
            all_signals.extend(signals)
        except Exception as e:
            print(f"[STRATEGY ERROR] {name}: {e}")
    
    # Remove duplicates (same market, keep highest edge)
    seen = {}
    for s in all_signals:
        key = f"{s.market['id']}_{s.side}"
        if key not in seen or s.edge > seen[key].edge:
            seen[key] = s
    
    unique_signals = list(seen.values())
    
    # Rank by composite score: edge * confidence * liquidity_factor * cap_efficiency
    for s in unique_signals:
        liq_factor = min(s.market.get('liquidity', 0) / 100000, 1.0)
        cap_eff = getattr(s, 'cap_efficiency', 1.0)
        s.score = s.edge * s.confidence * (0.5 + 0.5 * liq_factor) * cap_eff
    
    unique_signals.sort(key=lambda s: s.score, reverse=True)
    
    return unique_signals


def filter_signals(signals, portfolio, min_edge=None):
    """Filter signals based on portfolio constraints."""
    from config import get_phase
    
    eq = portfolio.equity()
    phase = get_phase(eq)
    _min_edge = min_edge or MIN_EDGE_PCT
    
    filtered = []
    open_markets = set(portfolio.positions.keys())
    closed_markets = set(portfolio.state.get("closed_markets", []))
    
    for s in signals:
        # Skip if already in this market or already traded it
        if str(s.market['id']) in open_markets:
            continue
        if str(s.market['id']) in closed_markets:
            continue
        
        # Skip below edge threshold
        if s.edge < _min_edge:
            continue
        
        # Skip if max positions reached
        if len(open_markets) + len(filtered) >= phase["max_open"]:
            break
        
        # Skip if insufficient cash
        size = portfolio.get_position_sizing(s.edge, s.entry_price + s.edge)
        if size < 1.0:  # Min $1 position
            continue
        
        s.suggested_size = size
        filtered.append(s)
    
    return filtered
