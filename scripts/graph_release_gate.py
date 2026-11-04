"""Evaluate explicit acceptance conditions. Never promotes/deploys an image."""
import argparse
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--required-concurrency',type=int,default=30)
p.add_argument('--baseline',required=True)
p.add_argument('--knowledge',required=True)
p.add_argument('--general',required=True)
p.add_argument('--lms',required=True)
p.add_argument('--quality',required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
load=lambda f:json.loads(Path(f).read_text())
b,k,g,l,q=map(load,(a.baseline,a.knowledge,a.general,a.lms,a.quality))
base=b['summary']['knowledge']['p95_first_content']
new=k['summary']['knowledge']['p95_first_content']
runs=k['runs']
valid=[r for r in runs if r.get('done',{}).get('verified') and r.get('done',{}).get('finish_reason')=='stop' and 'knowledge' in r.get('done',{}).get('routes',[])]
all_valid=len(runs)>=30 and len(valid)==len(runs)
checks={
 'requested_concurrency_exercised':k.get('concurrency',0)>=a.required_concurrency,
 'general_first_content_p95_le_0_5':g['summary']['general']['p95_first_content'] <= .5,
 'lms_total_p95_le_2':l['summary']['lms']['p95_total'] <= 2,
 'knowledge_first_content_p95_le_10':all_valid and new <= 10,
 'knowledge_improves_at_least_40_percent':all_valid and new <= base*.6,
 'knowledge_30_complete_without_fallback':len(runs)>=30 and all(r.get('done',{}).get('verified') and r.get('done',{}).get('finish_reason')=='stop' and 'knowledge' in r.get('done',{}).get('routes',[]) for r in runs),
 'focused_knowledge_quality_at_least_90_percent':k.get('quality_rate',0)>=.9,
 'full_ai_regression_quality_at_least_90_percent':q.get('summary',{}).get('quality_rate',0)>=.9,
 'real_ai_no_answer_leaks':q.get('summary',{}).get('answer_leaks',1)==0,
}
result={'checks':checks,'performance_and_ai_gate_passed':all(checks.values()),'rollout':'requires all automated checks plus reviewed security/test evidence; no deployment performed','baseline_caution':'Baseline requests with missing first content are failures, not fast successes.'}
Path(a.output).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
