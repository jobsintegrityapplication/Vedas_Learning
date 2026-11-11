from __future__ import annotations

import numpy as np


class AlignmentError(ValueError):
    pass


def forced_align(log_probs: np.ndarray, target_ids: list[int], blank_id: int = 0) -> list[int]:
    """Return the best CTC state at each frame for the given known labels.

    The state sequence alternates blank and target labels. Returned values are
    indices into that expanded sequence, so repeated target symbols remain
    distinguishable. `log_probs` must be [time, classes] log probabilities.
    """
    if log_probs.ndim != 2 or not target_ids:
        raise AlignmentError("CTC alignment requires frame logits and at least one target label")
    frame_count, class_count = log_probs.shape
    if frame_count == 0 or any(label < 0 or label >= class_count or label == blank_id for label in target_ids):
        raise AlignmentError("CTC target contains an invalid or blank label")

    expanded = [blank_id]
    for label in target_ids:
        expanded.extend((label, blank_id))
    state_count = len(expanded)
    scores = np.full((frame_count, state_count), -np.inf, dtype=np.float64)
    backpointers = np.full((frame_count, state_count), -1, dtype=np.int32)
    scores[0, 0] = float(log_probs[0, blank_id])
    scores[0, 1] = float(log_probs[0, target_ids[0]])

    for frame in range(1, frame_count):
        for state, label in enumerate(expanded):
            candidates = [(scores[frame - 1, state], state)]
            if state > 0:
                candidates.append((scores[frame - 1, state - 1], state - 1))
            if (state > 1 and label != blank_id and label != expanded[state - 2]):
                candidates.append((scores[frame - 1, state - 2], state - 2))
            best_score, best_state = max(candidates, key=lambda pair: pair[0])
            scores[frame, state] = best_score + float(log_probs[frame, label])
            backpointers[frame, state] = best_state

    final_states = [state_count - 1, state_count - 2]
    state = max(final_states, key=lambda candidate: scores[-1, candidate])
    if not np.isfinite(scores[-1, state]):
        raise AlignmentError("Audio is too short or the known text cannot be aligned")
    path = [state]
    for frame in range(frame_count - 1, 0, -1):
        state = int(backpointers[frame, state])
        if state < 0:
            raise AlignmentError("CTC alignment path is incomplete")
        path.append(state)
    path.reverse()
    return path
