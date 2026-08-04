import json,tempfile,unittest
from pathlib import Path
from swarm_validation.controller import SwarmController,BASE_SYSTEM
from swarm_validation.dataset import BenchmarkTask
from swarm_validation.models import ProviderResponse,Usage
from swarm_validation.protocol import ProtocolConfig
from swarm_validation.runner import BenchmarkRunner
from swarm_validation.evaluator import Evaluation


def task(i,topic='sequence list sum'):
    return BenchmarkTask(f't/{i}',f'def value_{i}():\n    """{topic}; return integer {i}."""\n',f'def check(candidate):\n    assert candidate() == {i}',f'value_{i}')



def fast_evaluate(task, completion, config=None):
    expected=int(task.task_id.split('/')[-1])
    passed=f"return {expected}" in completion
    return Evaluation(passed,'passed' if passed else 'failed',0.1,0 if passed else 1,'','' if passed else 'AssertionError')

class InspectProvider:
    def __init__(self): self.calls=[]
    def generate(self,*,model,system,messages,max_tokens,temperature,metadata=None):
        self.calls.append((metadata.copy(),system,[dict(x) for x in messages])); i=int(metadata['task_id'].split('/')[-1]); attempt=metadata['attempt']; text=f'    return {i if attempt>1 else i+1}\n'; chars=len(system)+sum(len(x['content']) for x in messages); return ProviderResponse(text,Usage(60+chars//4,8),model,'end_turn',1.0,'x')

class CycleMemoryTests(unittest.TestCase):
    def test_40_is_threshold_and_reset_occurs_only_on_next_cycle(self):
        c=SwarmController(0,cycle_length=2)
        c.observe(task(1),True,'    return 1\n',''); c.observe(task(2),True,'    return 2\n','')
        self.assertEqual(c.state.phase,'40'); self.assertEqual(c.state.tasks_in_cycle,2); self.assertTrue(c.working_memory); self.assertFalse(c.intuitive_memory)
        c.system_prompt(task(3))
        self.assertEqual(c.state.phase,'ACTIVE'); self.assertEqual(c.state.cycle_index,1); self.assertEqual(c.state.tasks_in_cycle,0); self.assertFalse(c.working_memory); self.assertTrue(c.intuitive_memory)
    def test_failures_are_destroyed_at_6(self):
        c=SwarmController(0,cycle_length=2); c.observe(task(1),False,'    return 9\n','AssertionError'); c.observe(task(2),True,'    return 2\n','')
        self.assertEqual(c.state.phase,'40'); self.assertFalse(c.transient_failures); self.assertTrue(all(e.task_id!='t/1' for e in c.pending_intuitive))
    def test_all_failure_cycle_creates_no_intuitive_memory(self):
        c=SwarmController(0,cycle_length=2)
        c.observe(task(1),False,'','AssertionError')
        c.observe(task(2),False,'','AssertionError')
        self.assertEqual(c.state.phase,'40')
        self.assertFalse(c.pending_intuitive)
        c.system_prompt(task(3))
        self.assertFalse(c.intuitive_memory)
        self.assertFalse(c.working_memory)
        self.assertFalse(c.transient_failures)

    def test_raw_code_never_becomes_intuitive_memory(self):
        c=SwarmController(0,cycle_length=1); c.observe(task(1),True,'    return 1\n',''); c.system_prompt(task(2))
        self.assertTrue(c.intuitive_memory); self.assertTrue(all('return 1' not in e.lesson for e in c.intuitive_memory))
    def test_memory_not_used_inside_same_cycle(self):
        c=SwarmController(0,cycle_length=2); c.observe(task(1),True,'    return 1\n','')
        self.assertEqual(c.system_prompt(task(2)),BASE_SYSTEM)
    def test_irrelevant_intuitive_memory_is_rejected(self):
        c=SwarmController(0,cycle_length=1); c.observe(task(1,'sequence list sum'),True,'    return 1\n',''); c.system_prompt(task(2,'sequence list sum'))
        self.assertEqual(c.system_prompt(task(3,'graph vertex edge traversal')),BASE_SYSTEM)
    def test_relevant_intuitive_memory_is_used_after_crossing_40(self):
        c=SwarmController(0,cycle_length=1); c.observe(task(1,'sequence list sum'),True,'    return 1\n',''); prompt=c.system_prompt(task(2,'sequence list sum'))
        self.assertIn('Prior-cycle intuition',prompt)
    def test_retry_drops_memory_but_keeps_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); tp=root/'tasks.jsonl'
            with tp.open('w') as h:
                for i in range(10):
                    t=task(i); h.write(json.dumps({'task_id':t.task_id,'prompt':t.prompt,'test':t.test,'entry_point':t.entry_point})+'\n')
            p=InspectProvider(); cfg=ProtocolConfig(tasks_per_agent=1,cycle_length=1,max_live_calls=60,bootstrap_samples=100)
            BenchmarkRunner(config=cfg,provider=p,tasks_path=tp,output_dir=root/'out',evaluator_fn=fast_evaluate).run()
            swarm_calls=[x for x in p.calls if x[0]['condition']=='swarm']
            retry=[x for x in swarm_calls if x[0]['attempt']==2][0]
            self.assertEqual(retry[1],BASE_SYSTEM); self.assertGreater(len(retry[2]),1)
    def test_success_increases_fuel_failure_decreases_fuel(self):
        a=SwarmController(0,cycle_length=9); before=a.state.fuel; a.observe(task(1),True,'    return 1\n',''); self.assertGreater(a.state.fuel,before)
        b=SwarmController(0,cycle_length=9); before=b.state.fuel; b.observe(task(1),False,'','x'); self.assertLess(b.state.fuel,before)

if __name__=='__main__': unittest.main()
