import sys,json,subprocess,os
sys.path.insert(0,'/tmp/work_ledger/pre'); import predictor
env=dict(os.environ,PYTHONPATH='/tmp/work_ledger/tree/product/src')
for v in sys.argv[1:]:
    p=f'/tmp/work_ledger/pre/fresh/{v}.json'
    r=predictor.predict(p,v)
    out=f'/tmp/work_ledger/pre/fresh/{v}_rep.json'
    for k in (3,):
        subprocess.run(['python3','-m','faultbound_wt.cli','analyze',p,'--top',v,'--max-flips','3','--cycles','6','--report',out,'--exit-zero'],env=env,capture_output=True,timeout=300,cwd='/tmp/work_ledger/tree')
    d=json.load(open(out))
    print(v,'pred',r['pred'],'lb',r['lb'],'est',r['est'],r['flag'],'solver',d['verdict'],d.get('min_faults'))
