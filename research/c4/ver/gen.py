import random, json, sys, os, subprocess
OUT='/tmp/work_ver/gen'
def expr_pool(r, leaves, n):
    """random expression list over leaves; returns list of verilog expr strings"""
    pool=list(leaves); ex=[]
    for _ in range(n):
        a,b,c=r.choice(pool),r.choice(pool),r.choice(pool)
        op=r.choice(['&','|','^','^','~&','m','n'])
        if op in '&|^': e=f'({a} {op} {b})'
        elif op=='~&': e=f'(~({a} & {b}))'
        elif op=='m': e=f'({c} ? {a} : {b})'
        else: e=f'(~{a})'
        pool.append(e); ex.append(e)
    return pool
def cmp_mod(name,W,key,r):
    st=r.choice(['eq','xor','and'])
    if st=='eq': body=f"assign m = (a == {W}'h{key:x});"
    elif st=='xor': body=f"assign m = ~|(a ^ {W}'h{key:x});"
    else: body="assign m = "+' & '.join(f"{'a['+str(i)+']' if (key>>i)&1 else '~a['+str(i)+']'}" for i in range(W))+";"
    return f"(* keep_hierarchy *) module {name}(input [{W-1}:0] a, output m);\n  {body}\nendmodule\n"
def gen_rc(seed):
    r=random.Random(seed); W=r.choice([4,6,8]); OW=r.choice([4,6,8]); key=r.getrandbits(W)
    acc=r.getrandbits(OW); bad=(acc^r.getrandbits(OW)) or 1
    ns=r.randint(3,6); n=r.choice([1,2,2,3,3]); comb=r.choice(['and','vote','or_and','and']) if n>1 else 'and'
    ctr=r.choice(['count','shift','rand'])
    s=[f's[{i}]' for i in range(ns)]
    v=''
    for i in range(n): v+=cmp_mod(f'cm{i}_{seed}',W,key,r)
    v+=f"module t{seed}(input clk, input [{W-1}:0] sig, output [{OW-1}:0] boot_word);\n"
    v+=f"  (* keep *) reg [{ns-1}:0] s; initial s = {ns}'d{r.getrandbits(ns)};\n  (* keep *) reg [{OW-1}:0] o; initial o = {OW}'d{r.getrandbits(OW)};\n"
    for i in range(n): v+=f"  wire m{i}; cm{i}_{seed} c{i}(.a(sig), .m(m{i}));\n"
    if n==1: v+="  wire m = m0;\n"
    elif comb=='and': v+="  wire m = "+' & '.join(f'm{i}' for i in range(n))+";\n"
    elif comb=='vote' and n==3: v+="  wire m = (m0&m1)|(m0&m2)|(m1&m2);\n"
    elif comb=='vote': v+="  wire m = m0 & m1;\n"
    else: v+="  wire m = (m0 & m1) & (m0 | m1 "+("| m2" if n>2 else "")+");\n"
    # phase: decode of state
    if ctr=='count':
        v+=f"  wire [{ns-1}:0] sn = s + 1;\n"; sn='sn'
    elif ctr=='shift':
        v+=f"  wire [{ns-1}:0] sn = {{s[{ns-2}:0], ~s[{ns-1}]}};\n"; sn='sn'
    else:
        ex=expr_pool(r,s,ns+2); v+=f"  wire [{ns-1}:0] sn = {{"+', '.join(r.choice(ex) for _ in range(ns))+"};\n"; sn='sn'
    # phase tap value: run the counter from init to find phase state reachable at cycle 2..4 (pre-simulate)
    s0=int(v.split("initial s = ")[1].split("'d")[1].split(";")[0])
    mod=1<<ns
    def nxt(x):
        if ctr=='count': return (x+1)%mod
        if ctr=='shift': return ((x<<1)&(mod-1))|(0 if (x>>(ns-1))&1 else 1)
        return None
    if ctr=='rand': tgt=r.getrandbits(ns)
    else:
        x=s0; seq=[x]
        for _ in range(5): x=nxt(x); seq.append(x)
        tgt=seq[r.randint(1,3)]
    mw=r.choice([ns,ns,max(2,ns-1)])
    v+=f"  wire ph = (s[{mw-1}:0] == {mw}'d{tgt & ((1<<mw)-1)});\n"
    v+=f"  wire [{OW-1}:0] good = {OW}'d{acc}, badw = {OW}'d{bad};\n"
    hold=r.choice(['hold','bad'])
    v+=f"  always @(posedge clk) begin\n    s <= {sn};\n"
    v+=f"    if (ph) o <= m ? good : badw;\n"+(f"    else o <= o;\n" if hold=='hold' else f"    else o <= badw;\n")+"  end\n"
    v+="  assign boot_word = o;\nendmodule\n"
    return v,f't{seed}',dict(W=W,OW=OW,key=key,acc=acc)
def gen_rand(seed):
    r=random.Random(seed); W=r.choice([4,6,8]); OW=r.choice([4,6,8]); nf=r.randint(3,8); ng=r.randint(10,60)
    key=r.getrandbits(W); acc=r.getrandbits(OW)
    sig=[f'sig[{i}]' for i in range(W)]; q=[f'q[{i}]' for i in range(nf)]
    pool=sig+q; gates=[]
    v=f"module t{seed}(input clk, input [{W-1}:0] sig, output [{OW-1}:0] boot_word);\n  (* keep *) reg [{nf-1}:0] q; initial q = {nf}'d{r.getrandbits(nf)};\n"
    for i in range(ng):
        a,b,c=[r.choice(pool[-12:] if r.random()<0.6 else pool) for _ in range(3)]
        op=r.choice(['&','|','^','^','m','n'])
        e={'&':f'{a} & {b}','|':f'{a} | {b}','^':f'{a} ^ {b}','m':f'{c} ? {a} : {b}','n':f'~{a}'}[op]
        v+=f"  wire g{i} = {e};\n"; pool.append(f'g{i}')
    g=[f'g{i}' for i in range(ng)]
    v+="  always @(posedge clk) q <= {"+', '.join(r.choice(g) for _ in range(nf))+"};\n"
    # redundant copy: dup of a random gate cone via independent re-expression is skipped (abc merges); output bits = random gates/flops
    v+="  assign boot_word = {"+', '.join(r.choice(g[-ng//2:]+q) for _ in range(OW))+"};\nendmodule\n"
    return v,f't{seed}',dict(W=W,OW=OW,key=key,acc=acc)
def gen_crc(seed):
    r=random.Random(seed); W=r.choice([4,6,8]); poly=r.getrandbits(W)|1; tgt=r.getrandbits(W); kind=r.choice(['crc','lfsr','par'])
    nc=r.choice([1,2,3]); OW=r.choice([1,1,4,8]); acc=(1 if OW==1 else r.getrandbits(OW)|1)
    v=f"module t{seed}(input clk, input [{W-1}:0] sig, output [{OW-1}:0] boot_word);\n  reg [{W-1}:0] w; initial w=0;\n  reg [{OW-1}:0] o; initial o={OW}'d0;\n"
    v+="  always @(posedge clk) w <= sig;\n"
    if kind=='crc':
        v+=f"  function [{W-1}:0] crc(input [{W-1}:0] d); integer i; reg [{W-1}:0] c; begin c={W}'hff; for(i=0;i<{W};i=i+1) c = (c[{W-1}]^d[i]) ? ((c<<1)^{W}'h{poly:x}) : (c<<1); crc=c; end endfunction\n"
        # choose tgt equal crc of a key so honest passes
        key=r.getrandbits(W)
        x=0xff&((1<<W)-1); c=(1<<W)-1
        for i in range(W):
            fb=((c>>(W-1))&1)^((key>>i)&1); c=((c<<1)&((1<<W)-1))^(poly if fb else 0)
        tgt=c
        chk=[f"(crc(w) == {W}'h{tgt:x})" for _ in range(nc)]
    elif kind=='lfsr':
        key=tgt
        v+=f"  reg [{W-1}:0] l; initial l={W}'d{r.getrandbits(W)|1};\n  always @(posedge clk) l <= {{l[{W-2}:0], ^(l & {W}'h{poly:x})}};\n"
        chk=[f"((w ^ l) == {W}'h{r.getrandbits(W):x})" for _ in range(1)]*nc
        chk=[f"(w == {W}'h{tgt:x})" for _ in range(nc)]
    else:
        key=tgt
        chk=[f"((^(w & {W}'h{poly:x})) == 1'b{r.getrandbits(1)})" for _ in range(nc)]
        pk=r.getrandbits(1)
        chk=[f"((^(w & {W}'h{poly:x})) == 1'b{pk}) & (w[0] == 1'b{tgt&1})" for _ in range(nc)]
        key=None
    v+="  wire m = "+(' & ' if r.random()<0.7 else ' | ').join(chk)+";\n"
    v+=f"  always @(posedge clk) o <= m ? {OW}'d{acc} : {OW}'d{(acc^1) if OW>1 else 0};\n  assign boot_word = o;\nendmodule\n"
    return v,f't{seed}',dict(W=W,OW=OW,key=(key if key is not None else r.getrandbits(W)),acc=acc)
FAM={'rc':gen_rc,'rand':gen_rand,'crc':gen_crc}
if __name__=='__main__':
    man=[]
    plan=[('rc',s,f) for s in range(100,128) for f in ['plain','opt'][s%2:s%2+1]]+[('rand',s,f) for s in range(200,214) for f in ['plain']]+[('crc',s,f) for s in range(300,322) for f in ['plain','opt'][s%2:s%2+1]]
    for fam,s,flow in plan:
        v,top,meta=FAM[fam](s)
        base=f'{OUT}/{fam}{s}'
        open(base+'.v','w').write(v)
        rc=subprocess.run(['sh','scripts/synth.sh',base+'.v',top,f'{base}_{flow}.json',flow],capture_output=True,text=True,timeout=120)
        if rc.returncode: print('synth fail',fam,s,rc.stderr[:200]); continue
        man.append(dict(fam=fam,seed=s,flow=flow,top=top,json=f'{base}_{flow}.json',**meta))
    json.dump(man,open('/tmp/work_ver/manifest.json','w'),indent=1); print(len(man))
