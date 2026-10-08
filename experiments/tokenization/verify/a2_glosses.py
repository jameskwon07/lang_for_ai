"""attempt_2: the 20 test messages as morpheme-key sequences (before form assignment).

Keys in CAPS are function words, d<N> are number words, lowercase keys are content lemmas that must exist in the
general (G) or domain (D) block of the lexicon. ("RAW", text) is a raw span introduced by QT.
CLASS gives the lexical class of every content key used here (one class per entry):
  N noun, A property (modifier before a noun, or predicate after a subject), D adverb (clause-final adjunct),
  V0 / V1 / V2 verbs with 0/1/2 object slots after the verb, VC verb whose object is a clause.
"""

CLASS = {
    # V
    "find": "V1", "affect": "V1", "return": "V2", "draft": "V1", "reject": "V1", "suggest": "V1", "search": "V1",
    "read": "V1", "choose": "V1", "cover": "V1", "lack": "V1", "own": "V1", "change": "V1", "add": "V1", "keep": "V1",
    "give": "V2", "trust": "V1", "open": "V1", "move": "V2", "switch": "V1", "put": "V1", "fix": "V1", "update": "V1",
    "upgrade": "V2", "raise": "V2", "split": "V1", "clean": "V1", "handle": "V1", "merge": "V1", "agree": "V1",
    "cite": "V1", "support": "V1", "limit": "V1", "check": "V1", "apply": "V1", "fall": "V0", "take": "V1",
    "need": "V1", "think": "VC", "say": "VC", "review": "V1", "write": "V1", "cause": "V1", "test": "V1",
    "conflict": "V0", "prefer": "V1", "like": "V1", "ask": "V1", "run": "V1",
    # A
    "recent": "A", "peerreviewed": "A", "relevant": "A", "friendly": "A", "other": "A", "first": "A", "complete": "A",
    "missing": "A", "new": "A", "old": "A", "different": "A", "previous": "A", "wrong": "A", "minimum": "A",
    "strong": "A", "second": "A", "third": "A", "final": "A", "correct": "A", "extra": "A", "original": "A",
    "late": "A", "high": "A", "enough": "A", "sure": "A", "reliable": "A", "low": "A", "next": "A", "short": "A",
    "fixed": "A", "ready": "A",
    # D
    "later": "D", "directly": "D", "mostly": "D", "twice": "D", "again": "D",
    # N
    "study": "N", "sleep": "N", "loss": "N", "workingmemory": "N", "sentence": "N", "summary": "N", "answer": "N",
    "meeting": "N", "request": "N", "time": "N", "week": "N", "literature": "N", "paper": "N", "blocker": "N",
    "report": "N", "version": "N", "background": "N", "method": "N", "result": "N", "discussion": "N", "file": "N",
    "scan": "N", "duplicate": "N", "column": "N", "value": "N", "address": "N", "field": "N", "company": "N",
    "directory": "N", "billing": "N", "service": "N", "backup": "N", "oncall": "N", "function": "N",
    "compatibility": "N", "source": "N", "document": "N", "deadline": "N", "folder": "N", "dataset": "N",
    "figure": "N", "table": "N", "deprecation": "N", "warning": "N", "work": "N", "data": "N", "visualization": "N",
    "name": "N", "argument": "N", "claim": "N", "calculation": "N", "error": "N", "step": "N", "tax": "N",
    "amount": "N", "rest": "N", "frontend": "N", "task": "N", "day": "N", "part": "N", "date": "N", "gpu": "N",
    "hour": "N", "estimate": "N", "measurement": "N", "logging": "N", "config": "N", "disk": "N", "slowdown": "N",
    "profiler": "N", "output": "N", "option": "N", "confidence": "N", "context": "N", "agent": "N", "user": "N",
    "design": "N", "color": "N", "layout": "N", "budget": "N", "human": "N", "approval": "N", "confirmation": "N",
}

R = "RAW"
MESSAGES = [
    ("m02", ["IMP", "find", "recent", "peerreviewed", "study", "ABOUT", "sleep", "loss", "affect", "workingmemory",
             "return", "MOST", "relevant", "d5", "WITH", "d1", "sentence", "summary", "EACH"],
     "[request mode] Find recent peer-reviewed studies about [how] sleep loss affects working memory. Return the five "
     "most relevant, each with a one-sentence summary."),
    ("m04", ["IMP", "draft", "friendly", "answer", "REL", "reject", "meeting", "request", "ET", "suggest", "d2", "other",
             "time", "later", "IN", "THIS", "week"],
     "[request mode] Draft a friendly (polite) answer that rejects the meeting request and suggests two other times, later "
     "in this week."),
    ("m06", ["search", "literature", "PROG", "read", "choose", "paper", "d0", "blocker", "SOFAR"],
     "[I] searched the literature [completed]. [I am] now reading the chosen (shortlisted) papers. Zero blockers so "
     "far."),
    ("m08", ["first", "report", "version", "REL", "cover", "background", "ET", "method", "ET", "result", "complete",
             "discussion", "STILL", "missing"],
     "The first report version (first draft), which covers background, methods and results, is complete. The "
     "discussion is still missing."),
    ("m10", ["file", "scan", "find", "d0", "duplicate", "d3", "column", "lack", "value", "MOSTLY", "IN", "address",
             "field"],
     "The file scan found zero duplicates. Three columns lack values, mostly in the address field."),
    ("m12", ["FROM", "company", "directory", "QT", (R, "Maria Lopez"), "own", "billing", "service", "QT",
             (R, "Kenji Sato"), "EQ", "backup", "oncall"],
     "[frame for whole message:] From the company directory: Maria Lopez owns the billing service; Kenji Sato is the "
     "backup on-call [engineer]."),
    ("m14", ["DELIB", "change", "QT", (R, "parse_config()"), "directly", "OR", "add", "new", "function", "ET",
             "keep", "old", "FOR", "compatibility"],
     "[should-I question mode] Should I change parse_config() directly, or add a new function and keep the old "
     "[one] for (backward) compatibility?"),
    ("m16", ["d2", "source", "document", "give", "different", "deadline", "MUST", "trust", "WHICH"],
     "The two source documents give different deadlines. Which [one] should I trust (treat as authoritative)?"),
    ("m18", ["CANNOT", "open", "QT", (R, "data/2024/q3_sales.csv"), "BECAUSE", "file", "missing", "Q",
             "PASS", "move", "other", "folder"],
     "I could not open data/2024/q3_sales.csv because the file is missing (does not exist). [question mode] Was [it, "
     "the previous clause's subject] moved to another folder?"),
    ("m20", ["MY", "previous", "answer", "wrong", "BECAUSE", "switch", "d2", "dataset", "put", "fix", "figure", "IN",
             "update", "table"],
     "My previous answer is wrong because I switched (mixed up) the two datasets. [I] put the fixed (corrected) figures "
     "in the updated table."),
    ("m22", ["HORT", "upgrade", "QT", (R, "numpy"), "d2", "POINT", "d1", "fix", "deprecation", "warning",
             "raise", "minimum", "QT", (R, "Python"), "d3", "POINT", "d1", "d1"],
     "[proposal mode: let's] Upgrade numpy to 2.1, [then] fix the deprecation warnings, [then] raise the minimum "
     "Python to 3.11. [juxtaposed events are in the order written]"),
    ("m24", ["SUGQ", "split", "work", "I", "clean", "data", "YOU", "handle", "visualization", "merge", "result",
             "LASTLY", "agree", "column", "name", "FIRSTLY"],
     "[proposal-asking-agreement mode: shall we ... OK?] Split the work: I clean the data, you handle the "
     "visualizations, [we] merge the results at the end; [we] agree on column names first. [Is that OK with you?]"),
    ("m26", ["argument", "strong", "BUT", "d0", "cite", "source", "support", "second", "claim", "IMP", "add",
             "source", "OR", "limit", "claim"],
     "The argument is strong (persuasive), but zero cited sources support the second claim. [request mode] Add a "
     "source or limit (soften) the claim."),
    ("m28", ["check", "YOUR", "calculation", "third", "step", "wrong", "tax", "PASS", "apply",
             "TWICE", "final", "amount", "MUST", "fall", "rest", "correct"],
     "I checked your calculation. The third step is wrong (has the error): the tax was applied twice. The final "
     "amount should fall (be lower). The rest is correct."),
    ("m30", ["CAN", "take", "frontend", "task", "BUT", "need", "d2", "extra", "day", "THAN", "suggest", "CAN",
             "give", "part", "BYTIME", "original", "date", "IF", "THAT", "TOO", "late"],
     "I can take the frontend tasks, but I need two extra days than the suggestion (what was proposed). I can give (deliver) a "
     "part (partial version) by the original date if that is too late."),
    ("m32", ["think", "YOUR", "d40", "gpu", "hour", "estimate", "high", "MY", "measurement", "say", "d20", "d5",
             "enough", "SUGQ", "agree", "d30", "ET", "review", "AFTER", "first", "run"],
     "I think your 40 GPU-hour estimate is high. My measurement says 25 is enough. [shall we] agree on 30 (compromise) "
     "and review (revisit) [it] after the first run?"),
    ("m34", ["new", "logging", "config", "REL", "write", "EVERY", "request", "TO", "disk", "PROB", "cause",
             "slowdown", "I", "FAIRLY", "sure", "FROM", "profiler", "output", "BUT", "NOTYET", "test", "fix"],
     "The new logging config, which writes every request to disk, probably causes the slowdown. I am fairly sure, "
     "from (based on) the profiler output, but I have not yet tested a fix."),
    ("m36", ["CANNOT", "find", "reliable", "answer", "d2", "source", "conflict", "MORE", "new", "support",
             "second", "option", "BUT", "confidence", "low"],
     "I could not find a reliable answer. The two sources conflict; the newer [one] supports the second option, but "
     "[my] confidence is low."),
    ("m38", ["context", "FOR", "next", "agent", "PD", "user", "prefer", "short", "answer", "THEY", "reject", "first",
             "d2", "design", "THEY", "like", "third", "design", "color", "NEG", "layout",
             "IMP", "NEG", "ask", "fixed", "budget", "again"],
     "Context for the next agent. The user prefers short answers. They rejected the first two designs. They like the "
     "third design's color [scheme], not [its] layout. [request mode] Do not ask about the fixed budget again (the "
     "budget is fixed)."),
    ("m40", ["return", "task", "YOU", "BECAUSE", "IT", "need", "human", "approval", "ALL", "ready", "ONLY", "final",
             "confirmation", "missing"],
     "I return (pass back) the task to you because it needs human approval. Everything is ready (prepared); only the "
     "final confirmation is missing."),
]
