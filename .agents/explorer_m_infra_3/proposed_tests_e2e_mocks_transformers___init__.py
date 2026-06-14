class MockPipeline:
    def __init__(self, task, model=None):
        self.task = task
        self.model = model
        
    def __call__(self, text, **kwargs):
        # Analyze text for simple keywords to return mock sentiment
        if isinstance(text, list):
            return [self._analyze_single(t) for t in text]
        return [self._analyze_single(text)]

    def _analyze_single(self, text):
        t_lower = text.lower()
        if any(w in t_lower for w in ["strong", "record", "growth", "buy", "bullish"]):
            return {'label': 'positive', 'score': 0.85}
        elif any(w in t_lower for w in ["drop", "loss", "sell", "bearish", "investigation"]):
            return {'label': 'negative', 'score': 0.85}
        else:
            return {'label': 'neutral', 'score': 0.9}

def pipeline(task, model=None, *args, **kwargs):
    return MockPipeline(task, model)

class AutoTokenizer:
    @classmethod
    def from_pretrained(cls, name):
        return cls()

class AutoModelForSequenceClassification:
    @classmethod
    def from_pretrained(cls, name):
        return cls()
