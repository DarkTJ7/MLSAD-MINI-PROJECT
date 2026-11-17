from datetime import date
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator,field_validator

class Kind(str, Enum):
    own_damage = 'own_damage'
    third_party = 'third_party'
    theft = 'theft'
    total_loss = 'total_loss'

class FNOL(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    policy_number: str = Field(min_length=3, max_length=60, pattern=r'^[A-Za-z0-9/-]+$')
    vehicle_registration: str = Field(min_length=4, max_length=20, pattern=r'^[A-Z0-9 -]+$')
    insurer: str = Field(default='HDFC ERGO', max_length=100)
    product: str = Field(default='private_car_package', max_length=100)
    policy_start: date = Field(strict=False)
    policy_end: date = Field(strict=False)
    loss_date: date = Field(strict=False)
    reported_date: date = Field(strict=False)
    description: str = Field(min_length=12, max_length=4000)
    location: str = Field(min_length=2, max_length=200)
    country: str = Field(default='India', max_length=60)
    vehicle_use: str = Field(default='personal', pattern=r'^(personal|commute|business|delivery|hire_reward|unknown)$')
    estimated_repair: float = Field(ge=0, le=100000000, allow_inf_nan=False)
    idv: float = Field(gt=0, le=100000000, allow_inf_nan=False)
    network_garage: bool = False
    driver_licensed: Optional[bool] = None
    intoxicated: Optional[bool] = None
    third_party_involved: bool = False
    police_report: bool = False
    retrieval_version: Literal['v5'] = 'v5'

    @field_validator('vehicle_registration', mode='before')
    @classmethod
    def normalise_registration(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator('vehicle_use', mode='before')
    @classmethod
    def normalise_vehicle_use(cls, value):
        return value.strip().casefold().replace('-', '_').replace(' ', '_') if isinstance(value, str) else value

    @field_validator('policy_start','policy_end','loss_date','reported_date',mode='before')
    @classmethod
    def date_wire_format(cls,value):
        import re
        if isinstance(value,date):return value
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            raise ValueError('Date must be an ISO YYYY-MM-DD string')
        return value

    @model_validator(mode='after')
    def chronology(self):
        if self.policy_end < self.policy_start:
            raise ValueError('policy_end must follow policy_start')
        if self.loss_date > self.reported_date or self.reported_date > date.today():
            raise ValueError('loss_date <= reported_date <= today is required')
        return self

class Feedback(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True)
    satisfactory: bool
    reason: str = Field(min_length=3, max_length=1000)

class Citation(BaseModel):
    clause_id: str
    document: str
    page: int
    quote: str

class Recommendation(BaseModel):
    recommendation_only: Literal[True] = True
    classification: Kind
    coverage_position: Literal['potentially_covered','coverage_concern','insufficient_evidence']
    queue: str = Field(pattern=r'^(fast-track|surveyor assignment|investigation)$')
    reason: str
    requires_human: Literal[True] = True
    escalation: Optional[str] = None
    citations: list[Citation]
    verified: bool
    prompt_version: str
    limitations: list[str]
