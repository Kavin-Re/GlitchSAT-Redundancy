import itertools
G=[(1<<0)|(1<<3)|(1<<6),(1<<1)|(1<<4)|(1<<7),(1<<2)|(1<<5)]
def pop(x): return bin(x).count('1')
def pred(m,good=0x96,legit=(0xF0,0xCC)):
    best=min(pop((s^good)&m) for s in legit)
    for r in range(4):
        for S in itertools.combinations(range(3),r):
            g=0
            for j in S: g|=G[j]
            best=min(best,len(S)+pop(~g&m&0xFF))
    return best
