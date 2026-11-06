
from dataclasses import dataclass, asdict

BPS = 10_000


@dataclass
class TransactionFeatures:
    amount: float
    provider_capacity: float
    provider_reversal_rate: float
    taker_dispute_rate: float
    account_age_days: int
    transactions_last_hour: int
    payment_method_risk: float


@dataclass
class RiskResult:
    approved: bool
    risk_score_bps: int
    max_amount: int
    spread_bps: int
    collateral_bps: int
    reasons: list[str]

    def to_dict(self):
        return asdict(self)


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def evaluate_risk(features: TransactionFeatures) -> RiskResult:
    if features.amount <= 0:
        raise ValueError("Transaction amount must be positive")

    if features.provider_capacity <= 0:
        raise ValueError("Provider capacity must be positive")

    if not 0 <= features.provider_reversal_rate <= 1:
        raise ValueError("Invalid provider reversal rate")

    if not 0 <= features.taker_dispute_rate <= 1:
        raise ValueError("Invalid taker dispute rate")

    if not 0 <= features.payment_method_risk <= 1:
        raise ValueError("Invalid payment method risk")

    if features.account_age_days < 0:
        raise ValueError("Invalid account age")

    if features.transactions_last_hour < 0:
        raise ValueError("Invalid transaction velocity")

    score = 0
    reasons = []

    reversal_score = int(features.provider_reversal_rate * 3000)
    score += reversal_score

    if reversal_score >= 750:
        reasons.append("Elevated provider reversal history")

    dispute_score = int(features.taker_dispute_rate * 2500)
    score += dispute_score

    if dispute_score >= 500:
        reasons.append("Elevated taker dispute history")

    if features.account_age_days < 7:
        score += 1500
        reasons.append("Very new account")
    elif features.account_age_days < 30:
        score += 800
        reasons.append("Limited account history")

    if features.transactions_last_hour > 20:
        score += 1500
        reasons.append("Unusually high transaction velocity")
    elif features.transactions_last_hour > 10:
        score += 800
        reasons.append("Elevated transaction velocity")

    payment_score = int(features.payment_method_risk * 1500)
    score += payment_score

    if payment_score >= 500:
        reasons.append("Elevated payment method risk")

    capacity_ratio = features.amount / features.provider_capacity

    if capacity_ratio > 0.8:
        score += 1000
        reasons.append("High provider capacity utilization")
    elif capacity_ratio > 0.5:
        score += 500
        reasons.append("Moderate provider capacity utilization")

    score = clamp(score, 0, BPS)
    approved = score < 7000

    spread_bps = clamp(50 + score // 20, 50, 550)
    collateral_bps = clamp(500 + score, 500, 7500)

    max_amount = (
    max(int(features.amount), int(features.provider_capacity * 0.5))
    if approved else 0
)

    return RiskResult(
        approved=approved,
        risk_score_bps=score,
        max_amount=max_amount,
        spread_bps=spread_bps,
        collateral_bps=collateral_bps,
        reasons=reasons
    )
