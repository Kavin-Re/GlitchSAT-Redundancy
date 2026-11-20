# Re-run of Exp A at width 1 ns after fixing a measure-at-tstop artifact (tran now runs 1 ns past the sample time).
import sys,json; sys.path.insert(0,'/home/user/project/research/c2/el1_spice')
import expA
expA.TAG='_wd1n'; expA.WD=[1e-9]
jobs=[(c,t,d,p) for c,t in expA.CORNERS for d in (1,) for p in (0,1) if c=='tt' or p==0]
print(len(sum(expA.pmap(expA.run,jobs,4),[])))
