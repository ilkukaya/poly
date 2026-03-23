"""
POLYMARKET API WRAPPER
Handles all communication with Polymarket's Gamma and CLOB APIs.
"""

import requests
import json
import time
from datetime import datetime, timezone
from config import GAMMA_API, CLOB_API, MIN_LIQUIDITY

session = requests.Session()
session.headers.update({"User-Agent": "PolyPaperTrader/1.0"})

def _safe_json_field(val, default=None):
    """Parse a field that might be a JSON string or already parsed."""
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except:
            return default
    return default


def fetch_active_markets(limit=500, min_volume_24h=100, min_liquidity=None):
    """Fetch all active, tradeable markets sorted by 24h volume."""
    min_liq = min_liquidity or MIN_LIQUIDITY
    
    url = f"{GAMMA_API}/markets"
    params = {
        "limit": limit,
        "active": True,
        "closed": False,
        "order": "volume24hr",
        "ascending": False,
    }
    
    try:
        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        raw_markets = resp.json()
    except Exception as e:
        print(f"[API ERROR] fetch_active_markets: {e}")
        return []
    
    markets = []
    for m in raw_markets:
        # Parse prices
        outcomes = _safe_json_field(m.get('outcomes'), [])
        prices = _safe_json_field(m.get('outcomePrices'), [])
        token_ids = _safe_json_field(m.get('clobTokenIds'), [])
        
        if not prices or not outcomes:
            continue
        
        yes_price = float(prices[0]) if prices else 0
        no_price = float(prices[1]) if len(prices) > 1 else 1 - yes_price
        
        vol24 = float(m.get('volume24hr', 0) or 0)
        liquidity = float(m.get('liquidityClob', 0) or 0)
        spread = float(m.get('spread', 0) or 0)
        
        # Filter
        if vol24 < min_volume_24h:
            continue
        if liquidity < min_liq:
            continue
        
        # Skip already-resolved (>98% or <2%)
        if yes_price > 0.98 or yes_price < 0.02:
            continue
        
        market = {
            "id": m.get('id'),
            "question": m.get('question', ''),
            "slug": m.get('slug', ''),
            "end_date": m.get('endDateIso', ''),
            "outcomes": outcomes,
            "yes_price": yes_price,
            "no_price": no_price,
            "token_ids": token_ids,
            "volume_24h": vol24,
            "volume_1wk": float(m.get('volume1wk', 0) or 0),
            "liquidity": liquidity,
            "spread": spread,
            "best_bid": float(m.get('bestBid', 0) or 0),
            "best_ask": float(m.get('bestAsk', 0) or 0),
            "price_change_1d": float(m.get('oneDayPriceChange', 0) or 0),
            "price_change_1h": float(m.get('oneHourPriceChange', 0) or 0),
            "price_change_1w": float(m.get('oneWeekPriceChange', 0) or 0),
            "competitive": float(m.get('competitive', 0) or 0),
            "description": m.get('description', '')[:500],
            "condition_id": m.get('conditionId', ''),
            "neg_risk": m.get('negRisk'),
            "order_min_size": float(m.get('orderMinSize', 5) or 5),
            "tick_size": float(m.get('orderPriceMinTickSize', 0.01) or 0.01),
        }
        
        # Try to get tags from events
        events = _safe_json_field(m.get('events'), [])
        tags = []
        if events:
            for ev in events:
                ev_tags = _safe_json_field(ev.get('tags'), [])
                for t in ev_tags:
                    if isinstance(t, dict):
                        tags.append(t.get('label', ''))
                    else:
                        tags.append(str(t))
        market['tags'] = tags
        market['category'] = _categorize_market(market)
        
        markets.append(market)
    
    return markets


def _categorize_market(market):
    """Categorize market based on question text and tags."""
    q = market['question'].lower()
    tags_lower = [t.lower() for t in market.get('tags', [])]
    
    # Sports
    sport_keywords = ['win on 202', 'spread:', 'o/u ', 'both teams to score',
                      'aggies', 'wildcats', 'bruins', 'huskies', 'warriors',
                      'lakers', 'celtics', 'nuggets', 'nets', 'kings', 'suns',
                      'nba', 'nhl', 'nfl', 'mlb', 'mls', 'ncaa', 'stanley cup',
                      'world cup', 'champions league', 'premier league',
                      'serie a', 'bundesliga', 'la liga']
    if any(k in q for k in sport_keywords) or any('sport' in t for t in tags_lower):
        return 'sports'
    
    # Esports
    esport_keywords = ['counter-strike', 'dota', 'league of legends', 'valorant',
                       'blast', 'esl', 'bo3', 'bo5', 'esport']
    if any(k in q for k in esport_keywords) or any('esport' in t for t in tags_lower):
        return 'esports'
    
    # Crypto
    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol',
                       'crypto', 'token', 'blockchain', 'defi', 'nft']
    if any(k in q for k in crypto_keywords) or any('crypto' in t for t in tags_lower):
        return 'crypto'
    
    # Geopolitics
    geo_keywords = ['iran', 'ceasefire', 'invasion', 'military', 'regime',
                    'taiwan', 'ukraine', 'russia', 'nato', 'troops', 'war']
    if any(k in q for k in geo_keywords) or any('geopolitic' in t for t in tags_lower):
        return 'geopolitics'
    
    # Politics/Elections
    pol_keywords = ['election', 'president', 'nomination', 'congress', 'senate',
                    'governor', 'party', 'democrat', 'republican', 'seats',
                    'fed ', 'interest rate', 'trump', 'biden']
    if any(k in q for k in pol_keywords) or any('politic' in t or 'election' in t for t in tags_lower):
        return 'politics'
    
    # Finance
    fin_keywords = ['fed ', 'interest rate', 'gdp', 'inflation', 'tariff',
                    'stock', 's&p', 'nasdaq', 'treasury']
    if any(k in q for k in fin_keywords) or any('finance' in t for t in tags_lower):
        return 'finance'
    
    # Culture/Entertainment
    cult_keywords = ['oscar', 'grammy', 'box office', 'movie', 'album',
                     'tv show', 'netflix', 'spotify', 'tiktok']
    if any(k in q for k in cult_keywords):
        return 'entertainment'
    
    return 'other'


def fetch_order_book(token_id):
    """Fetch order book for a specific token."""
    url = f"{CLOB_API}/book"
    params = {"token_id": token_id}
    
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[API ERROR] fetch_order_book: {e}")
        return None


def fetch_price_history(token_id, interval="1d", fidelity=60):
    """Fetch price history for a token."""
    url = f"{CLOB_API}/prices-history"
    params = {"market": token_id, "interval": interval, "fidelity": fidelity}
    
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get('history', [])
    except Exception as e:
        print(f"[API ERROR] fetch_price_history: {e}")
        return []


def get_market_by_slug(slug):
    """Fetch a specific market by slug."""
    url = f"{GAMMA_API}/markets"
    params = {"slug": slug, "limit": 1}
    
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        markets = resp.json()
        return markets[0] if markets else None
    except Exception as e:
        print(f"[API ERROR] get_market_by_slug: {e}")
        return None


def get_current_price(market):
    """Get best available price for a market, accounting for spread."""
    # Use best_bid/best_ask if available, otherwise use mid price
    if market.get('best_bid') and market.get('best_ask'):
        return {
            "yes_bid": market['best_bid'],
            "yes_ask": market['best_ask'],
            "yes_mid": (market['best_bid'] + market['best_ask']) / 2,
            "no_bid": 1 - market['best_ask'],
            "no_ask": 1 - market['best_bid'],
            "no_mid": 1 - (market['best_bid'] + market['best_ask']) / 2,
            "spread": market['best_ask'] - market['best_bid'],
        }
    else:
        return {
            "yes_bid": market['yes_price'] - market['spread'] / 2,
            "yes_ask": market['yes_price'] + market['spread'] / 2,
            "yes_mid": market['yes_price'],
            "no_bid": market['no_price'] - market['spread'] / 2,
            "no_ask": market['no_price'] + market['spread'] / 2,
            "no_mid": market['no_price'],
            "spread": market['spread'],
        }


def fetch_events_with_markets(limit=100):
    """Fetch events with their sub-markets for multi-outcome analysis."""
    url = f"{GAMMA_API}/events"
    params = {
        "limit": limit,
        "active": True,
        "closed": False,
        "order": "volume24hr",
        "ascending": False,
    }
    
    try:
        resp = session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[API ERROR] fetch_events_with_markets: {e}")
        return []


def fetch_market_by_id(market_id):
    """Fetch a specific market by ID, including closed/resolved markets.
    Returns the market dict with resolved outcome info, or None."""
    url = f"{GAMMA_API}/markets"
    params = {"id": market_id}
    
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        markets = resp.json()
        if markets:
            m = markets[0]
            # Parse prices
            prices = _safe_json_field(m.get('outcomePrices'), [])
            outcomes = _safe_json_field(m.get('outcomes'), [])
            
            result = {
                "id": m.get('id'),
                "question": m.get('question', ''),
                "closed": m.get('closed', False),
                "active": m.get('active', True),
                "outcomes": outcomes,
                "prices": prices,
            }
            
            # Determine resolved outcome
            if m.get('closed') and prices:
                yes_price = float(prices[0]) if prices else 0
                no_price = float(prices[1]) if len(prices) > 1 else 0
                
                if yes_price >= 0.99:
                    result["resolved_winner"] = "YES"
                elif no_price >= 0.99:
                    result["resolved_winner"] = "NO"
                else:
                    result["resolved_winner"] = None
            else:
                result["resolved_winner"] = None
            
            return result
    except Exception as e:
        print(f"[API ERROR] fetch_market_by_id({market_id}): {e}")
    
    return None
