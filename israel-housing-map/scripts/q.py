# over.org.il append-dataset SQL endpoint. Results are capped at 1,000 rows (pack with string_agg).
# The endpoint allows 20 requests per minute per IP (since 2026-10): requests are paced to 18 a minute
# across threads, and a 429 waits out the server's retry time without using up a try.
import json, sys, urllib.request, urllib.error, time, threading, re
_lock = threading.Lock(); _sent = []
def _pace(per_min=18):
    with _lock:
        while True:
            now = time.time()
            while _sent and now - _sent[0] > 60: _sent.pop(0)
            if len(_sent) < per_min: _sent.append(now); return
            time.sleep(60 - (now - _sent[0]) + 0.2)
def sql(ds, q, tries=4):
    i = 0
    while i < tries:
        _pace()
        try:
            r = urllib.request.Request(f'https://www.over.org.il/api/append/{ds}/sql', data=json.dumps({'sql': q}).encode(),
                                       headers={'content-type': 'application/json'})
            return json.load(urllib.request.urlopen(r, timeout=600))
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            if e.code == 429:
                m = re.search(r'(\d+) שניות', msg); time.sleep((int(m.group(1)) if m else 20) + 1); continue
            print('ERR', msg, file=sys.stderr)
            if 'timeout' not in msg.lower() and i > 0: raise
        except Exception as e: print('ERR', e, file=sys.stderr)
        time.sleep(2**i); i += 1
    raise RuntimeError
PAR = 'ff3176b1-aafc-49c2-976d-ba25571e3564'
