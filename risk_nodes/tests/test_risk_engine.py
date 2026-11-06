
import pytest

from nodes.risk_engine import TransactionFeatures, evaluate_risk


def normal_transaction():
    return TransactionFeatures(
        amount=200,
        provider_capacity=1000,
        provider_reversal_rate=0.02,
        taker_dispute_rate=0.01,
        account_age_days=180,
        transactions_last_hour=3,
        payment_method_risk=0.10
    )


def test_normal_transaction_is_approved():
    result = evaluate_risk(normal_transaction())

    assert result.approved is True
    assert result.risk_score_bps < 7000


def test_high_risk_transaction_is_rejected():
    features = TransactionFeatures(
        amount=900,
        provider_capacity=1000,
        provider_reversal_rate=0.90,
        taker_dispute_rate=0.90,
        account_age_days=1,
        transactions_last_hour=30,
        payment_method_risk=0.90
    )

    result = evaluate_risk(features)

    assert result.approved is False
    assert result.risk_score_bps >= 7000
    assert result.max_amount == 0


def test_invalid_amount_is_rejected():
    features = normal_transaction()
    features.amount = 0

    with pytest.raises(ValueError):
        evaluate_risk(features)


def test_risk_score_is_bounded():
    result = evaluate_risk(normal_transaction())

    assert 0 <= result.risk_score_bps <= 10000


def test_higher_reversal_rate_increases_risk():
    low = normal_transaction()
    high = normal_transaction()

    low.provider_reversal_rate = 0.01
    high.provider_reversal_rate = 0.50

    low_result = evaluate_risk(low)
    high_result = evaluate_risk(high)

    assert high_result.risk_score_bps > low_result.risk_score_bps
