import pytest
from evaluation.compare import compare

def report(variant,mode='live',case='parking',faithful=1):
    return {'prompt_variant':variant,'mode':mode,'runs':[{'id':case,'seconds':2,
        'metrics':{'faithfulness':faithful,'verified':faithful},
        'events':[{'step':'provider'}]}]}

def test_comparison_requires_matched_live_context():
    with pytest.raises(ValueError,match='same model mode'):
        compare(report('v5a'),report('v5b','stub'))
    with pytest.raises(ValueError,match='identical scenario IDs'):
        compare(report('v5a'),report('v5b',case='collision'))

def test_comparison_reports_both_prompt_outcomes():
    comparison=compare(report('v5a',faithful=0),report('v5b',faithful=1))
    assert comparison['case_count']==1
    assert comparison['summary']['v5b']['faithfulness']==1
    assert comparison['cases'][0]['provider_calls']=={'v5a':1,'v5b':1}
