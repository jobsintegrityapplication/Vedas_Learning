from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    identifier: str | None = Field(default=None, max_length=320)
    email: EmailStr | None = None

    def start_id(self) -> str:
        return (self.identifier or (str(self.email) if self.email else "")).strip()

    @model_validator(mode="after")
    def require_id(self):
        if not self.start_id():
            raise ValueError("Enter an email address or mobile number")
        return self


class DirectRegisterRequest(BaseModel):
    email: EmailStr
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if len(self.password.encode("utf-8")) > 72:
            raise ValueError("Password exceeds the 72-byte limit")
        return self


class VerifyRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class CompleteSignupRequest(BaseModel):
    identifier: str | None = Field(default=None, max_length=320)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=200)
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    username: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    verification_token: str = Field(min_length=32, max_length=128)

    def start_id(self) -> str:
        return (self.identifier or (str(self.email) if self.email else "")).strip()

    def display_name(self) -> str:
        if self.full_name and self.full_name.strip():
            return self.full_name.strip()
        parts = [part for part in [self.first_name, self.last_name] if part and part.strip()]
        return " ".join(parts).strip()

    @model_validator(mode="after")
    def require_profile(self):
        if not self.start_id():
            raise ValueError("Enter an email address or mobile number")
        if not self.display_name():
            raise ValueError("Enter your full name")
        if "@" not in self.start_id():
            raise ValueError("Create an account with your email address")
        return self


class VerifyEmailLinkRequest(BaseModel):
    email: EmailStr
    verification_token: str = Field(min_length=32, max_length=128)


class LoginRequest(BaseModel):
    identifier: str | None = Field(default=None, max_length=320)
    email: EmailStr | None = None
    password: str = Field(min_length=1, max_length=72)

    @model_validator(mode="after")
    def require_login_id(self):
        if not (self.identifier or self.email):
            raise ValueError("Enter email or mobile number")
        return self

    def login_id(self) -> str:
        if self.identifier and self.identifier.strip():
            return self.identifier.strip()
        return str(self.email)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=72)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class TokenResponse(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    verified: bool = True
    username: str | None = None


class MeResponse(BaseModel):
    user_id: str
    name: str
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str
    verified: bool
