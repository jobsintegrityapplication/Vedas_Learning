from pydantic import BaseModel, EmailStr, Field, field_validator
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_verified_user
from app.db.session import get_db
from app.models import LearningEvent, Profile, User

router = APIRouter(prefix="/api/profile", tags=["profile"])

SUPPORTED_PROFILE_LANGUAGES = {"sa", "kn", "hi", "en", "te", "ta", "ml", "mr", "bn", "gu", "pa", "or"}


def _validate_supported_language(value: str) -> str:
    if value not in SUPPORTED_PROFILE_LANGUAGES:
        raise ValueError("preferred_language must be one of the supported content languages")
    return value


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    age: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=40)
    rashi: str = Field(default="", max_length=80)
    nakshatra: str = Field(default="", max_length=80)
    gotra: str = Field(default="", max_length=120)
    profession: str = Field(default="", max_length=120)
    date_of_birth: str = Field(default="", max_length=10)
    gender: str = Field(default="", max_length=40)
    preferred_language: str = Field(default="en", min_length=2, max_length=5)

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, value: str) -> str:
        return _validate_supported_language(value)


class PreferredLanguageIn(BaseModel):
    preferred_language: str = Field(default="en", min_length=2, max_length=5)

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, value: str) -> str:
        return _validate_supported_language(value)


class ProfileOut(BaseModel):
    user_id: str
    name: str
    email: str = ""
    age: str = ""
    phone: str = ""
    rashi: str = ""
    nakshatra: str = ""
    gotra: str = ""
    profession: str = ""
    date_of_birth: str = ""
    gender: str = ""
    preferred_language: str = "en"


def _out(user: User, profile: Profile | None) -> ProfileOut:
    return ProfileOut(
        user_id=str(user.id),
        name=(profile.name if profile and profile.name else user.name),
        email=user.email or "",
        age=profile.age if profile else "",
        phone=profile.phone if profile else "",
        rashi=profile.rashi if profile else "",
        nakshatra=profile.nakshatra if profile else "",
        gotra=profile.gotra if profile else "",
        profession=profile.profession if profile else "",
        date_of_birth=profile.date_of_birth if profile else "",
        gender=profile.gender if profile else "",
        preferred_language=profile.preferred_language if profile else "en",
    )


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    return _out(user, db.get(Profile, user.id))


@router.post("", response_model=ProfileOut)
def save_profile(body: ProfileIn, user: User = Depends(get_verified_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    profile.name = body.name
    profile.email = user.email
    profile.age = body.age
    profile.phone = body.phone
    profile.rashi = body.rashi
    profile.nakshatra = body.nakshatra
    profile.gotra = body.gotra
    profile.profession = body.profession
    profile.date_of_birth = body.date_of_birth
    profile.gender = body.gender
    profile.preferred_language = body.preferred_language
    user.name = body.name
    db.add(LearningEvent(user_id=user.id, event_type="profile_updated"))
    db.commit()
    db.refresh(profile)
    return _out(user, profile)


@router.post("/preferred-language", response_model=ProfileOut)
def save_preferred_language(
    body: PreferredLanguageIn,
    user: User = Depends(get_verified_user),
    db: Session = Depends(get_db),
):
    profile = db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, name=user.name, email=user.email or "")
        db.add(profile)
    profile.preferred_language = body.preferred_language
    db.add(LearningEvent(user_id=user.id, event_type="profile_updated"))
    db.commit()
    db.refresh(profile)
    return _out(user, profile)
