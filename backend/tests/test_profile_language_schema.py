import pytest
from pydantic import ValidationError

from app.api.profiles import PreferredLanguageIn, ProfileIn


def test_profile_accepts_gotra_and_all_content_language_codes():
    accepted = {"sa", "kn", "hi", "en", "te", "ta", "ml", "mr", "bn", "gu", "pa", "or"}
    for code in accepted:
        profile = ProfileIn.model_validate({"name": "Learner", "gotra": "Bharadwaja", "preferred_language": code})
        assert profile.gotra == "Bharadwaja"
        assert PreferredLanguageIn.model_validate({"preferred_language": code}).preferred_language == code


def test_profile_rejects_unsupported_content_language():
    with pytest.raises(ValidationError):
        ProfileIn.model_validate({"name": "Learner", "preferred_language": "xx"})
