import layout_fi as L
M=L.M
bad=[]
for init in range(256):
    L.HON[0]=0
    g=L.run(6,set(),init)
    if g: bad.append(hex(init))
print('power-up inits that boot a wrong key with ZERO faults (T=6):',bad)
# availability: honest key C3, single fault, is boot_word==0x96 at final cycle 5 ?
T=6
def final_ok(fs):
    # re-run capturing final word for lane 0xC3
    st={c[2]['Q']:(M if (L.INIT>>i)&1 else 0) for i,c in enumerate(sorted(L.dffs,key=lambda c:int(L.re.search(r'\d+',c[2]['Q'].split('[')[1]).group())))}
    for t in range(T):
        val=dict(L.sigv); val.update(st)
        for q in list(st):
            if (t,q) in fs: val[q]^=M
        for c in L.order:
            o=L.res(c[2][L.outpin(c)]); v=L.evalcell(c,val)
            if (t,o) in fs: v^=M
            val[o]=v
        st={c[2]['Q']:val[L.res(c[2]['D'])] for c in L.dffs}
    w=M
    for i in range(8):
        b=val[f'boot_word[{i}]']; w&= b if (0x96>>i)&1 else (~b)&M
    return (w>>0xC3)&1
fails=[(t,s) for t in range(T) for s in L.sites if not final_ok({(t,s)})]
print('single faults that make the LEGIT key fail to be at 0x96 at cycle 5:',len(fails),'of',T*len(L.sites))
