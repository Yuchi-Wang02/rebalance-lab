#!/usr/bin/env python3
"""Capture the fixed baseline issuer cohort and its paid inputs privately.

The key is read from the process environment or non-echoing stdin. It is sent
only in an HTTPS header to data.nasdaq.com, never saved in manifests or URLs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_key():
    key = os.environ.get('NASDAQ_DATA_LINK_API_KEY')
    if key:
        return key
    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()
    import termios
    original = termios.tcgetattr(sys.stdin.fileno())
    muted = original.copy()
    muted[3] &= ~(termios.ECHO | termios.ECHONL)
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, muted)
    print('Ready for hidden API-key input', flush=True)
    try:
        return sys.stdin.readline().strip()
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, original)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start:start + size]


class Capture:
    def __init__(self, key, output):
        self.key = key
        self.output = output
        self.receipts = []
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())

    def table(self, label, table, params):
        rows = []
        cursor = None
        for page in range(50):
            query = dict(params)
            query['qopts.per_page'] = 10000
            if cursor:
                query['qopts.cursor_id'] = cursor
            url = 'https://data.nasdaq.com/api/v3/datatables/SHARADAR/' + table + '.json?' + urllib.parse.urlencode(query)
            request = urllib.request.Request(url, headers={
                'x-api-token': self.key, 'Accept': 'application/json',
                'User-Agent': 'SPMO-Fast-Lab private issuer-cohort research capture'})
            try:
                with self.opener.open(request, timeout=40) as response:
                    body = response.read(32 * 1024 * 1024 + 1)
                    status = response.status
            except urllib.error.HTTPError as error:
                raise RuntimeError(f'{label}: HTTP {error.code}') from None
            except (OSError, urllib.error.URLError):
                raise RuntimeError(f'{label}: transport failure') from None
            if len(body) > 32 * 1024 * 1024:
                raise RuntimeError(f'{label}: response size limit')
            # Reject a credential echo rather than retaining it in an artifact.
            if self.key.encode() in body:
                raise RuntimeError(f'{label}: credential echo refused')
            obj = json.loads(body)
            if 'datatable' not in obj:
                raise RuntimeError(f'{label}: invalid table response')
            columns = [column['name'] for column in obj['datatable']['columns']]
            values = obj['datatable']['data']
            rows.extend(dict(zip(columns, value)) for value in values)
            path = self.output / f'{label}.{page:02d}.json'
            with path.open('xb') as stream:
                stream.write(body)
            path.chmod(0o400)
            cursor = obj.get('meta', {}).get('next_cursor_id')
            self.receipts.append({'label':label,'table':table,'page':page,'url':url,
                'status':status,'rows':len(values),'bytes':len(body),
                'sha256':hashlib.sha256(body).hexdigest(),'file':path.name,
                'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                'has_next_page':bool(cursor)})
            write_json(self.output / f'receipt.{len(self.receipts):03d}.json', self.receipts[-1])
            print(json.dumps({'label':label,'page':page,'rows':len(values),'more':bool(cursor)}),flush=True)
            if not cursor:
                return rows
            time.sleep(.15)
        raise RuntimeError(f'{label}: pagination safety limit')


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--baseline-tickers', required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    # Acquisition is bound to the original numeric design. The current config
    # only corrects the description of Yahoo's corporate-action price proxy.
    config_bytes = (ROOT/'configs/stock-pilot.design-freeze.json').read_bytes()
    config = json.loads(config_bytes)
    tickers = json.loads(args.baseline_tickers.read_text())
    key = read_key()
    if not key:
        raise SystemExit('No API credential was received')
    capture = Capture(key,args.output_dir)
    caps = []
    metadata = []
    for i, group in enumerate(chunks(tickers,100)):
        caps.extend(capture.table(f'baseline-caps-{i}','DAILY',{
            'ticker':','.join(group),'date':config['cohort']['baseline'],
            'qopts.columns':'ticker,date,marketcap'}))
        metadata.extend(capture.table(f'metadata-{i}','TICKERS',{
            'table':'SEP','ticker':','.join(group),
            'qopts.columns':'table,permaticker,ticker,name,relatedtickers,firstpricedate,lastpricedate,isdelisted,currency'}))
    cap_by_ticker = {row['ticker']:row for row in caps}
    meta_by_ticker = {row['ticker']:row for row in metadata}
    if len(cap_by_ticker) != len(caps) or len(meta_by_ticker) != len(metadata):
        raise RuntimeError('Duplicate baseline keys')
    missing = sorted(set(tickers)-set(cap_by_ticker))
    known_classes = {'GOOG':'GOOGL','FOX':'FOXA','NWS':'NWSA'}
    unexpected = [ticker for ticker in missing if known_classes.get(ticker) not in cap_by_ticker]
    if unexpected:
        write_json(args.output_dir/'unexpected-missing-baseline-caps.json',unexpected)
        raise RuntimeError('Unexpected baseline capitalization gaps; cohort not selected')
    candidates = [row for row in caps if isinstance(row['marketcap'],(int,float)) and row['marketcap']>0]
    candidates.sort(key=lambda row:(-row['marketcap'],row['ticker']))
    if len(candidates)<config['cohort']['size']:
        raise RuntimeError('Insufficient baseline issuer candidates')
    cohort = []
    for rank,row in enumerate(candidates[:config['cohort']['size']],1):
        meta = meta_by_ticker.get(row['ticker'])
        if not meta or meta['permaticker'] is None:
            raise RuntimeError('Missing stable identifier')
        cohort.append({**meta,'security_id':str(meta['permaticker']),
            'baseline_rank':rank,'baseline_marketcap_usd':row['marketcap']*1_000_000})
    write_json(args.output_dir/'cohort.json',cohort)
    write_json(args.output_dir/'baseline-caps.json',caps)
    write_json(args.output_dir/'baseline-metadata.json',metadata)
    write_json(args.output_dir/'secondary-classes.json',[{'ticker':ticker,'representative':known_classes[ticker]} for ticker in missing])
    symbols = sorted({row['ticker'].replace('.','-') for row in cohort} | set(config['benchmarks']))
    write_json(args.output_dir/'price-symbols.json',symbols)
    print(json.dumps({'cohort_ready':str(args.output_dir/'cohort.json'),'price_symbols':str(args.output_dir/'price-symbols.json'),'cohort_size':len(cohort),'baseline_secondary_classes':missing}),flush=True)
    history=[]
    for i,group in enumerate(chunks([r['ticker'] for r in cohort],20)):
        history.extend(capture.table(f'cohort-caps-{i}','DAILY',{
            'ticker':','.join(group),'date.gte':config['initial_signal'],'date.lte':config['report_end'],
            'qopts.columns':'ticker,date,marketcap'}))
    actions=capture.table('cohort-actions','ACTIONS',{
        'ticker':','.join(r['ticker'] for r in cohort),
        'date.gte':config['initial_signal'],'date.lte':config['report_end']})
    write_json(args.output_dir/'capitalizations.json',history)
    write_json(args.output_dir/'actions.json',actions)
    write_json(args.output_dir/'manifest.json',{
        'schema_version':1,'provider':'SHARADAR','config_sha256':hashlib.sha256(config_bytes).hexdigest(),
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'credential_stored':False,
        'http_requests':len(capture.receipts),'captures':capture.receipts,
        'cohort_count':len(cohort),'capitalization_rows':len(history),'action_rows':len(actions),
        'publication':'private source data; publish aggregate derived research only'})
    print(json.dumps({'capture_complete':str(args.output_dir/'manifest.json'),'cap_rows':len(history),'action_rows':len(actions)}),flush=True)


if __name__=='__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError) as error:
        # Only controlled error text is public; no request URL, token or response body.
        if isinstance(error, RuntimeError):
            print(str(error),file=sys.stderr)
        else:
            print('Invalid source schema; capture stopped',file=sys.stderr)
        raise SystemExit(1)
