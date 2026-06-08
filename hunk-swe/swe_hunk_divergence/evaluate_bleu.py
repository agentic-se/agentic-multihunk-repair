from nltk.tokenize import word_tokenize
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from typing import List
import nltk

nltk.download('punkt_tab')

def compute_bleu_score(reference_code: str, candidate_code: str) -> float:
    """
    Tokenizes code using NLTK's word_tokenize and computes BLEU score.
    """
    reference_tokens = word_tokenize(reference_code)
    candidate_tokens = word_tokenize(candidate_code)
    smoother = SmoothingFunction().method4
    return sentence_bleu([reference_tokens], candidate_tokens, smoothing_function=smoother)

if __name__ == "__main__":
    reference_code = """
    int total = 0;
    for (int i = 0; i < 10; i++) {
        total += i;
    }
    """

    candidate_code = """
    int total = 0;
    for (int i = 0; i < 10; i++) {
        total += i;
    }
    """

    score = compute_bleu_score(reference_code, candidate_code)
    print(f"BLEU Score: {score:.4f}")
