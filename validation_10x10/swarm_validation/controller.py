from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field

from .dataset import BenchmarkTask
from .models import EngineState, MemoryEntry, WorkingObservation

BASE_SYSTEM = """You are solving a Python function-completion benchmark. Return only executable Python code for the missing function body. Do not use Markdown fences, explanations, tests, imports unrelated to the task, files, network access, subprocesses, or external packages. Keep the solution concise and deterministic."""

STOP = {"def","return","the","and","for","with","from","that","this","function","python","given","should","into","using","write","which","where","when","then"}

def _keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text.lower())
    return sorted({word for word in words if word not in STOP and not any(ch.isdigit() for ch in word) and word not in {"value", "integer"}})[:48]

def _features(completion: str, entry_point: str) -> list[str]:
    wrapper = f"def {entry_point}(*args, **kwargs):\n" + (completion or "    pass\n")
    try: tree = ast.parse(wrapper)
    except SyntaxError: return ["direct construction"]
    feats=[]
    if any(isinstance(n,(ast.For,ast.While,ast.comprehension)) for n in ast.walk(tree)): feats.append("bounded iteration")
    if any(isinstance(n,(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)) for n in ast.walk(tree)): feats.append("comprehension")
    calls=[n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
    if entry_point in calls: feats.append("recursion with an explicit base case")
    if any(x in calls for x in ("sorted","min","max","sum","any","all")): feats.append("a standard deterministic reduction")
    if any(isinstance(n,(ast.Set,ast.Dict)) for n in ast.walk(tree)): feats.append("set or mapping membership")
    if any(isinstance(n,ast.If) for n in ast.walk(tree)): feats.append("early boundary checks")
    if any(isinstance(n,ast.Subscript) for n in ast.walk(tree)): feats.append("guarded indexing")
    if not feats: feats.append("a direct minimal transformation")
    return feats[:3]

def _generalize(task: BenchmarkTask, completion: str) -> tuple[str,list[str]]:
    keys=_keywords(task.prompt)
    keyset=set(keys)
    if keyset & {"sequence","list","array","sum","aggregate","values"}: domain="Sequence processing"
    elif keyset & {"graph","vertex","edge","path","tree"}: domain="Graph processing"
    elif keyset & {"string","text","word","character"}: domain="Text processing"
    elif keyset & {"number","numeric","digit","prime","factor"}: domain="Numeric processing"
    else: domain="Matching task structure"
    technique=_features(completion, task.entry_point)[0]
    lesson=f"{domain}: {technique}; boundary guards."
    return lesson[:120], keys

@dataclass
class SwarmController:
    agent_id: int
    cycle_length: int = 8
    max_intuitive_entries: int = 4
    max_prompt_memory_entries: int = 1
    min_keyword_overlap: int = 2
    min_jaccard: float = 0.08
    state: EngineState = field(default_factory=EngineState)
    intuitive_memory: list[MemoryEntry] = field(default_factory=list)
    working_memory: list[WorkingObservation] = field(default_factory=list)
    transient_failures: list[str] = field(default_factory=list)
    pending_intuitive: list[MemoryEntry] = field(default_factory=list)
    phase_history: list[str] = field(default_factory=list)

    def _cross_threshold_40(self) -> None:
        if self.state.phase != "40": return
        merged = self.intuitive_memory + self.pending_intuitive
        dedup: dict[str, MemoryEntry] = {}
        for entry in merged:
            old=dedup.get(entry.lesson)
            if old is None or (entry.confidence,entry.cycle_index) > (old.confidence,old.cycle_index): dedup[entry.lesson]=entry
        self.intuitive_memory=sorted(dedup.values(),key=lambda e:(e.confidence,e.cycle_index),reverse=True)[:self.max_intuitive_entries]
        self.pending_intuitive.clear(); self.working_memory.clear(); self.transient_failures.clear()
        self.state.cycle_index += 1; self.state.tasks_in_cycle=0; self.state.phase="ACTIVE"; self.state.state="A"
        self.state.fuel=max(0.75,min(1.25,self.state.fuel)); self.state.memory=min(2.0,sum(e.confidence for e in self.intuitive_memory)/max(1,len(self.intuitive_memory)))
        self.phase_history.append("40→NEW_CYCLE")

    def _select(self, task: BenchmarkTask) -> list[MemoryEntry]:
        task_words=set(_keywords(task.prompt + " " + task.entry_point)); scored=[]
        for entry in self.intuitive_memory:
            words=set(entry.keywords); overlap=len(task_words & words); union=len(task_words | words) or 1; jaccard=overlap/union
            if overlap < self.min_keyword_overlap or jaccard < self.min_jaccard: continue
            scored.append((overlap,jaccard,entry.confidence,entry.cycle_index,entry))
        scored.sort(reverse=True,key=lambda x:x[:4])
        return [x[-1] for x in scored[:self.max_prompt_memory_entries]]

    def system_prompt(self, task: BenchmarkTask) -> str:
        self._cross_threshold_40()
        selected=self._select(task)
        if not selected: return BASE_SYSTEM
        memory="\n".join(f"- {e.lesson}" for e in selected)
        return BASE_SYSTEM+"\n\nPrior-cycle intuition:\n"+memory

    def retry_system_prompt(self, task: BenchmarkTask) -> str:
        return BASE_SYSTEM

    def _close_cycle(self) -> None:
        self.state.phase="ROZPAD_II"; self.phase_history.append("ROZPAD_II")
        self.state.phase="3"; self.phase_history.append("3")
        residue=[o for o in self.working_memory if o.passed]
        self.state.phase="6"; self.phase_history.append("6")
        # State 6 destroys failures and noise completely. Only successful, generalized information survives.
        grouped: dict[str,list[WorkingObservation]]={}
        for obs in residue:
            if not obs.lesson or "return " in obs.lesson or "traceback" in obs.lesson.lower(): continue
            grouped.setdefault(obs.lesson,[]).append(obs)
        cleaned=[]
        for lesson,items in grouped.items():
            keys=sorted(set().union(*(set(i.keywords) for i in items)))[:48]
            confidence=min(1.0,0.62+0.08*(len(items)-1))
            cleaned.append(MemoryEntry(items[-1].task_id,keys,lesson,True,self.state.cycle_index,confidence,len(items)))
        cleaned.sort(key=lambda e:(e.confidence,e.evidence_count),reverse=True)
        self.transient_failures.clear()
        self.state.phase="28"; self.phase_history.append("28")
        self.pending_intuitive=cleaned[:self.max_intuitive_entries]
        self.state.spiral_level += sum(e.confidence for e in self.pending_intuitive)
        self.state.phase="40"; self.phase_history.append("40")
        # No reset here. 40 is the threshold. Reset occurs only when the next cycle is entered.

    def observe(self, task: BenchmarkTask, passed: bool, completion: str, final_error: str) -> None:
        w=1.0 if passed else 0.0
        if passed:
            self.state.fuel += (0.9 - 0.6*abs(w-self.state.previous_w))*0.25
            self.state.solved_count += 1; self.state.state="A"
            lesson,keys=_generalize(task,completion)
            self.working_memory.append(WorkingObservation(task.task_id,keys,lesson,True,"passed",self.state.cycle_index))
        else:
            self.state.fuel -= (1.4 + 0.6*abs(w-self.state.previous_w))*0.25
            self.state.entropy=min(2.0,self.state.entropy+0.2); self.state.state="Q"
            self.transient_failures.append(task.task_id)
            self.working_memory.append(WorkingObservation(task.task_id,_keywords(task.prompt),"",False,"failed",self.state.cycle_index))
        self.state.fuel=max(0.0,min(2.0,self.state.fuel)); self.state.previous_w=w; self.state.tasks_in_cycle += 1
        if self.state.tasks_in_cycle >= self.cycle_length: self._close_cycle()

@dataclass
class StatelessController:
    agent_id: int
    def system_prompt(self, task: BenchmarkTask) -> str: return BASE_SYSTEM
    def retry_system_prompt(self, task: BenchmarkTask) -> str: return BASE_SYSTEM
    def observe(self, task: BenchmarkTask, passed: bool, completion: str, final_error: str) -> None: return None
