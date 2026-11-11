import json
import re
from pathlib import Path

from tests.conftest import register_verified_tokens

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ROOT / "content" / "reconciliation" / "tradition_variants.jsonl"
REF = re.compile(r"^RV\.(\d{2})\.(\d{3})\.(\d{2,3})$")


def _representative_references() -> dict[str, dict[int, str]]:
    choices = {profile: {} for profile in ("Kanchi", "Sringeri")}
    with VARIANTS.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            profile, identity = row.get("profile"), row.get("identity_key", "")
            match = REF.fullmatch(identity)
            if profile in choices and match and int(match.group(2)) > 0:
                mandala = int(match.group(1))
                choices[profile].setdefault(mandala, identity)
    return choices


def test_profile_index_exposes_all_documented_mandalas_and_counts(client):
    headers = {"Authorization": f"Bearer {register_verified_tokens(client, 'corpus-index@example.com')['access_token']}"}
    for profile in ("Kanchi", "Sringeri"):
        response = client.get(f"/api/recitation/library-index?profile={profile}", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "awaiting_reviewed_corpus"
        assert body["expected_total_suktas"] == 1028
        assert body["expected_total_mantras"] == 10552
        assert len(body["mandalas"]) == 10
        assert [m["mandala"] for m in body["mandalas"]] == list(range(1, 11))
        assert body["available_mantra_count"] == 0


def test_representative_reference_from_each_mandala_and_profile_stays_unavailable(client):
    choices = _representative_references()
    assert all(set(choices[p]) == set(range(1, 11)) for p in choices), choices
    headers = {"Authorization": f"Bearer {register_verified_tokens(client, 'corpus-coverage@example.com')['access_token']}"}
    for profile, mandalas in choices.items():
        for mandala, reference in sorted(mandalas.items()):
            learning = client.get(f"/api/recitation/{reference}/learning?profile={profile}", headers=headers)
            assert learning.status_code == 200, f"{profile} {mandala} {reference}: {learning.text}"
            body = learning.json()
            assert body["status"] == "unavailable"
            assert body["words"] == []
            assert body["evaluation_available"] is False

            audio = client.get(f"/api/recitation/{reference}/audio?profile={profile}", headers=headers)
            assert audio.status_code == 200, f"{profile} {mandala} {reference}: {audio.text}"
            audio_body = audio.json()
            assert audio_body["full_mantra"]["available"] is False
            assert audio_body["full_mantra"]["audio_url"] is None
            assert audio_body["word_audio"] == []

