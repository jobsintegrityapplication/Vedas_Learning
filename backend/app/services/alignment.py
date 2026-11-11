from dataclasses import dataclass, asdict


@dataclass
class AlignmentResult:
    reference_tokens: list[str]
    hypothesis_tokens: list[str]
    skipped: list[str]
    substituted: list[dict[str, str]]
    extra: list[str]
    matched: int

    def as_dict(self) -> dict:
        return asdict(self)


def align_tokens(reference: list[str], hypothesis: list[str]) -> AlignmentResult:
    """Levenshtein alignment of hypothesized tokens against Guru tokens.

    This operates on already-transcribed words. It does not listen to audio,
    compare voices, or infer Vedic svara.
    """
    n, m = len(reference), len(hypothesis)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if reference[i - 1] == hypothesis[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

    skipped: list[str] = []
    substituted: list[dict[str, str]] = []
    extra: list[str] = []
    matched = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and reference[i - 1] == hypothesis[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            matched += 1
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            substituted.append({"expected": reference[i - 1], "actual": hypothesis[j - 1]})
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            skipped.append(reference[i - 1])
            i -= 1
        else:
            extra.append(hypothesis[j - 1])
            j -= 1

    skipped.reverse()
    substituted.reverse()
    extra.reverse()
    return AlignmentResult(reference, hypothesis, skipped, substituted, extra, matched)


def score_alignment(result: AlignmentResult, threshold_percent: float = 90.0) -> dict:
    """Score exact transcript token matches; this is not a phonetic score."""
    denominator = max(len(result.reference_tokens), len(result.hypothesis_tokens), 1)
    match_percent = round(result.matched * 100.0 / denominator, 2)
    return {
        "matched": result.matched,
        "reference_word_count": len(result.reference_tokens),
        "recognized_word_count": len(result.hypothesis_tokens),
        "match_percent": match_percent,
        "pass_threshold_percent": threshold_percent,
        "meets_threshold": match_percent >= threshold_percent,
    }
