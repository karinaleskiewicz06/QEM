"""Frame-to-frame variance of <O> per twirl arm, w01 nights A+B (exploratory, H3 follow-up)."""
import json,sys,collections,statistics as st,math
groups=collections.defaultdict(list)
for w in ['w01A','w01B']:
    for line in open(f'runs/odra_campaign/{w}/counts.jsonl'):
        d=json.loads(line)
        if d.get('kind')!='cdr': continue
        arm=f"{d['arm']}:{d['train_set']}"
        if arm not in ('twirl_logical:shared_random','twirl_native:shared_random','twirl_native:near_target','off_copies:near_target'): continue
        c=d['counts']; n=sum(c.values()); co=d['coeffs']
        m1=m2=0.0
        for bits,k in c.items():
            # bit string: rightmost = qubit 0
            v=sum(co[i]*(1-2*int(bits[::-1][i])) for i in range(len(co)))
            m1+=k*v; m2+=k*v*v
        m1/=n; m2/=n
        shotvar=(m2-m1*m1)/n
        key=(d['rung'],arm,d['eval_index'] if d['train_set']=='near_target' or d['role']=='target' else -1,d['role'],d['train_index'])
        groups[key].append((d['repeat_index'],d['expval'],shotvar))
res=collections.defaultdict(lambda: collections.defaultdict(list))
for (rung,arm,ei,role,ti),v in groups.items():
    # dedupe shared_random training circuits measured once per point? keep all reps
    vals=[x[1] for x in v]
    if len(vals)<2: continue
    fv=st.variance(vals); sv=st.mean(x[2] for x in v)
    res[(rung,role)][arm].append((fv,sv,len(vals)))
order=['star','linear','circular','all_to_all']
for role in ['train','target']:
    print('\n== role',role,' (median frame-var / shot-var; median frame SD)')
    for rung in order:
        out=[]
        for arm in ['off_copies:near_target','twirl_logical:shared_random','twirl_native:shared_random','twirl_native:near_target']:
            L=res[(rung,role)].get(arm,[])
            if not L: out.append(f'{arm.split(":")[0][:13]:>13} -'); continue
            r=st.median(f/s for f,s,_ in L); sd=st.median(math.sqrt(f) for f,_,_ in L)
            out.append(f'{arm:>28} n={len(L):3d} M={L[0][2]} ratio={r:6.1f} sd={sd:.4f}')
        print(rung); [print('   ',o) for o in out]
