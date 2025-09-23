from src.generator.model_loader import load_embedding_model
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib

class DenseEncoder:
    def __init__(self):
        self.model = load_embedding_model()

    def encode(self, texts: list[str]) -> list[list[float]]:
        return self.model.embed_documents(texts)

class TfidfEncoder:
    def __init__(self, vectorizer_path=None, max_features=50000):
        if vectorizer_path:
            self.vectorizer = joblib.load(vectorizer_path)
        else:
            self.vectorizer = TfidfVectorizer(max_features=max_features)

    def fit(self, corpus: list[str], save_path=None):
        """Fit TF-IDF on corpus (all docs)"""
        self.vectorizer.fit(corpus)
        if save_path:
            joblib.dump(self.vectorizer, save_path)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Transform texts into fixed-length vectors"""
        arr = self.vectorizer.transform(texts).toarray()
        return arr.tolist()
