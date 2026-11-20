import subprocess, threading, json, os, time, sys, glob
FB='/tmp/work_rt3/venv/bin/faultbound-wt'
os.chdir('/tmp/work_rt3/t')
tgt='/tmp/work_rt3/t/race.json'
for f in glob.glob('race*'): os.remove(f)
stop=False; bad=[0]; reads=[0]
def reader():
    while not stop:
        try:
            s=open(tgt).read()
        except FileNotFoundError: continue
        reads[0]+=1
        try: json.loads(s)
        except Exception as e: bad[0]+=1; open('bad_%d.txt'%bad[0],'w').write(s[:500])
t=threading.Thread(target=reader); t.start()
rounds=6; badrc=0
for r in range(rounds):
    ps=[]
    for i in range(20):
        cyc=2+(i%5)
        ps.append(subprocess.Popen([FB,'analyze','pin.v','--top','pin','--config','pin.toml','--cycles',str(cyc),'--report',tgt,'--report','race.sarif','--badge','race.badge.json'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
    for p in ps:
        rc=p.wait()
        if rc not in (0,1): badrc+=1
stop=True; t.join()
left=[f for f in os.listdir('.') if f.startswith('.') or 'tmp' in f.lower()]
print('reads',reads[0],'invalid_reads',bad[0],'bad_rc',badrc,'leftover_tmp',left)
json.load(open(tgt)); json.load(open('race.sarif')); json.load(open('race.badge.json')); print('final files valid')
