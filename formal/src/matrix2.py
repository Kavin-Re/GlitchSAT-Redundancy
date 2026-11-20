import sys; sys.path.insert(0,'src')
import matrix, json
for nl, top in [('w0','v0'),('w1','v1'),('w2','v2'),('w2o','v2')]:
    for k in (0,1,2,3): matrix.run(nl, top, k)
json.dump(matrix.rows, open('runs/bmc_matrix2.json','w'), indent=1)
