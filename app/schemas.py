from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .catalog import BY_KIND


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CreateSimulation(StrictModel):
    profile_id: Literal['textbook', 'jingzhou2025'] = 'textbook'
    name: str = Field(min_length=1, max_length=60)
    seed: int = Field(default=20260906, ge=0, le=2**32-1, strict=True)
    initial_months: int = Field(default=0, ge=0, le=12, strict=True)
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        v = v.strip()
        if not v or any(ord(x)<32 for x in v): raise ValueError('请输入有效账套名称')
        return v


class Mutation(StrictModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    expected_version: int = Field(ge=0, strict=True)


class Advance(Mutation):
    months: int = Field(default=1, ge=1, le=12, strict=True)


class RunControl(Mutation):
    running: bool
    interval: int = Field(default=8, ge=3, le=60, strict=True)
    pause_at_year: bool = True


class EventInput(Mutation):
    kind: str
    entity: Literal['fiscal', 'hospital', 'school', 'police', 'soe']
    amount: Decimal = Field(default=Decimal(0), ge=0, le=Decimal('1000000000'), max_digits=12, decimal_places=2)
    event_id: str | None = Field(default=None, max_length=80, pattern=r'^[\w\-.:\u4e00-\u9fff]+$')
    project: Literal['运行','资本性','工资','商品服务'] = '运行'
    fund: Literal['self','fiscal'] = 'self'
    product: Literal['供电','供水','汽车'] = '供电'
    name: str = Field(default='仿真设备', min_length=1, max_length=60)
    life: int = Field(default=60, ge=1, le=1200, strict=True)

    @field_validator('amount', mode='before')
    @classmethod
    def no_bool(cls, value):
        if isinstance(value, bool): raise ValueError('金额或人数不能为布尔值')
        return value

    @model_validator(mode='after')
    def valid_event(self):
        c = BY_KIND.get(self.kind)
        if not c: raise ValueError('未知业务类型')
        if self.entity not in c['entities']: raise ValueError('该业务不适用于所选主体')
        if c['unit']=='人' and (self.amount!=self.amount.to_integral_value() or self.amount>100000):
            raise ValueError('人数须为不超过100000的整数')
        if c['unit']=='无' and self.amount!=0: raise ValueError('本事件自动计算金额，无需输入')
        if c['unit']!='无' and self.amount<=0: raise ValueError('金额或人数必须大于零')
        if any(ord(x)<32 for x in self.name): raise ValueError('资产名称不能含控制字符')
        return self
