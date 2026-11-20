from nb import *
# T1 persistent SEU: q holds (D=Q direct), s0<=q,s1<=s0,s2<=s1; out=AND(q,s2) x2
b=base(); q=b.dffq(); b.dffat(q,q,0); s0=b.dff(q); s1=b.dff(s0); s2=b.dff(s1)
o0=b.gate('AND',A=q,B=s2); o1=b.gate('AND',A=q,B=s2); b.out('boot_word',[o0,o1]); b.save('t1.json')
# T2 edge detector, time-varying input needed. a0<=sig0 (init1), a1<=a0 (init1); out=a0&!a1 twice
b=base(); a0=b.dff(b.sig[0],1); a1=b.dff(a0,1); n=b.gate('NOT',A=a1); o0=b.gate('AND',A=a0,B=n); o1=b.gate('AND',A=a0,B=n); b.out('boot_word',[o0,o1]); b.save('t2.json')
# T3 same net two cycles: g=XOR(sig0,sig0)=0 ; r<=g; out=AND(r,g) x2 ; min 2
b=base(); g=b.gate('XOR',A=b.sig[0],B=b.sig[0]); r=b.dff(g); o0=b.gate('AND',A=r,B=g); o1=b.gate('AND',A=r,B=g); b.out('boot_word',[o0,o1]); b.save('t3.json')
# T4 toggle flop: q<=NOT q init0 ; boot_word=q (1 bit, goal 1) ; k=0 attack first at cycle 1
b=base(); q=b.dffq(); n=b.gate('NOT',A=q); b.dffat(q,n,0); b.out('boot_word',[q]); b.save('t4.json')
# T5 flop with D tied to a primary input: out=q0&q1 both captured from sig? q0<=sig0, q1<=sig1 : attack with k=0 as sig not key (sanity)
# T6: 1-fault attack hidden behind a net with fanout>1 where branch matters: out0=XOR(n,m) out1=XOR(n,m) with m=BUF-like(n) = AND(n,n)...
b=base(); n=b.gate('AND',A=b.sig[0],B=b.sig[0]); m=b.gate('AND',A=n,B=n); o0=b.gate('XOR',A=n,B=m); o1=b.gate('XOR',A=n,B=m); b.out('boot_word',[o0,o1]); b.save('t6.json')
